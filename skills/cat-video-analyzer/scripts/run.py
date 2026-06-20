"""cat-video-analyzer 主入口（子命令式）。

为什么是子命令而不是一键脚本
============================
本 skill 的执行者是 **agent**。逐帧识别必须由 agent 的多模态能力完成，
所以流程不能是"一键黑盒"——中间有一步要 agent 介入（看图、判断、回传结果）。
把流程拆成子命令，agent 可以逐步驱动：

    scan     扫描 + 增量去重 → 输出待处理文件清单
    extract  对单个视频抽帧 → 输出帧路径 + 时间戳
    （agent 读图识别，按 references/recognition-protocol.md）
    ingest   把 agent 的识别结果写入 raw/日期.jsonl + 标记文件已处理
    report   聚合当日全部帧 → 生成 Markdown 报告

所有命令通过 stdout 输出 JSON，方便 agent 解析。
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

from scripts import config as cfg
from scripts import state
from scripts.aggregate import aggregate
from scripts.extract_frames import extract
from scripts.report import write_report
from scripts.schema import FrameResult, validate_frame_result


# ---------- 时间戳 ----------
_TS_PATTERNS = [
    re.compile(r"(\d{4})[-_]?(\d{2})[-_]?(\d{2})[_-]?(\d{2})[-_]?(\d{2})[-_]?(\d{2})"),
]


def _tz_from_name(name: str) -> timezone:
    try:
        from zoneinfo import ZoneInfo
        return ZoneInfo(name)  # type: ignore
    except Exception:
        if any(k in name for k in ("Shanghai", "Beijing", "China")):
            return timezone(timedelta(hours=8))
        return timezone.utc


def parse_video_timestamp(path: Path, tz) -> datetime:
    """优先从文件名解析时间；失败回退 mtime。"""
    name = path.stem
    for pat in _TS_PATTERNS:
        m = pat.search(name)
        if m:
            try:
                return datetime(int(m[1]), int(m[2]), int(m[3]),
                                int(m[4]), int(m[5]), int(m[6])).replace(tzinfo=tz)
            except ValueError:
                continue
    return datetime.fromtimestamp(path.stat().st_mtime, tz=tz)


def scan_date(directory: Path, date_str: str, tz) -> list[Path]:
    target = datetime.strptime(date_str, "%Y-%m-%d").date()
    out: list[Path] = []
    if not directory.exists():
        return out
    for p in directory.rglob("*"):
        if p.suffix.lower() not in (".mp4", ".mov", ".mkv", ".avi", ".ts"):
            continue
        try:
            ts = parse_video_timestamp(p, tz)
        except OSError:
            continue
        if ts.date() == target:
            out.append(p)
    return sorted(out)


# ---------- 逐帧结果 I/O ----------
def raw_frames_path(state_dir: Path, date_str: str) -> Path:
    return state_dir / "raw" / f"{date_str}.jsonl"


def append_frames(state_dir: Path, date_str: str, frames: list[FrameResult]) -> None:
    p = raw_frames_path(state_dir, date_str)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8") as f:
        for fr in frames:
            f.write(json.dumps({
                "frame_ts": fr.frame_ts,
                "context": fr.context,
                "cats": fr.cats,
                "activity": fr.activity,
            }, ensure_ascii=False) + "\n")


def load_frames(state_dir: Path, date_str: str) -> list[FrameResult]:
    p = raw_frames_path(state_dir, date_str)
    if not p.exists():
        return []
    out: list[FrameResult] = []
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            d = json.loads(line)
        except json.JSONDecodeError:
            continue
        out.append(FrameResult(
            frame_ts=d["frame_ts"],
            context=d["context"],
            cats=d.get("cats", []),
            activity=d.get("activity", {"type": "idle"}),
        ))
    return out


def _apply_context_constraint(d: dict) -> dict:
    """路径级硬约束：猫砂盆目录不允许 eating，喂食机目录不允许 toileting。"""
    ctx = d.get("context")
    a_type = d.get("activity", {}).get("type")
    if ctx == "litter_box" and a_type == "eating":
        d["activity"]["type"] = "idle"
    elif ctx == "feeder" and a_type == "toileting":
        d["activity"]["type"] = "idle"
    return d


def _emit(obj) -> None:
    """把结果打到 stdout，agent 解析用。"""
    print(json.dumps(obj, ensure_ascii=False))


# ---------- 子命令 ----------
def cmd_scan(args) -> int:
    cfg_obj = cfg.load()
    tz = _tz_from_name(cfg_obj.timezone)
    state_dir = cfg.config_dir()

    litter = scan_date(cfg_obj.litter_box_dir, args.date, tz)
    feeder = scan_date(cfg_obj.feeder_dir, args.date, tz)
    all_files = [(f, "litter_box") for f in litter] \
              + [(f, "feeder") for f in feeder]

    todo = state.filter_unprocessed(state_dir, [f for f, _ in all_files],
                                    force=args.force)
    todo_set = {str(f) for f in todo}
    todo_with_ctx = [{"path": str(f), "context": c}
                     for f, c in all_files if str(f) in todo_set]

    _emit({
        "date": args.date,
        "total": len(all_files),
        "skipped": len(all_files) - len(todo_with_ctx),
        "todo": todo_with_ctx,
    })
    return 0


def _extract_and_dedup(video: Path, context: str, cfg_obj, tz, out_dir=None) -> dict:
    """抽帧 + 可选去重，返回 frames/out_dir/warnings 等，供 extract / batch-extract 复用。

    去重需 Pillow；缺失或未启用时降级为输出全部帧（skill 仍可用，只是不省 token）。
    """
    from scripts import dedup

    od = Path(out_dir) if out_dir else Path(tempfile.mkdtemp(prefix="catva_"))
    frames = extract(video, od, interval_seconds=cfg_obj.frame_interval_seconds)
    file_start = parse_video_timestamp(video, tz)
    stamped = [(f, (file_start + timedelta(seconds=f.offset_seconds)).isoformat())
               for f in frames]

    warnings: list[str] = []
    payload: list[dict] = []

    if cfg_obj.dedup_enabled and dedup.PILLOW_AVAILABLE:
        groups = dedup.group_similar([str(f.path) for f in stamped],
                                     threshold=cfg_obj.dedup_hamming_threshold)
        for g in groups:
            rep_f, rep_ts = stamped[g.indices[0]]
            payload.append({
                "frame_path": str(rep_f.path),
                "frame_ts": rep_ts,
                "context": context,
                "time_range": [stamped[g.indices[0]][1], stamped[g.indices[-1]][1]],
                "represents": len(g.indices),
            })
    else:
        if cfg_obj.dedup_enabled and not dedup.PILLOW_AVAILABLE:
            warnings.append(
                "Pillow 未安装，跳过帧去重；本次输出全部帧。"
                "pip install pillow 可启用去重（预计省 40-70% 识别 token）。")
        for f, ts in stamped:
            payload.append({"frame_path": str(f.path), "frame_ts": ts, "context": context})

    return {
        "out_dir": str(od),
        "frame_count": len(stamped),
        "representative_count": len(payload),
        "frames": payload,
        "warnings": warnings,
    }


def cmd_extract(args) -> int:
    cfg_obj = cfg.load()
    tz = _tz_from_name(cfg_obj.timezone)
    video = Path(args.video)
    if not video.exists():
        print(json.dumps({"error": f"视频不存在: {video}"}), file=sys.stderr)
        return 1
    res = _extract_and_dedup(video, args.context, cfg_obj, tz, out_dir=args.out)
    _emit({"video": str(video), **res})
    return 0


def _expand_frame(fr: FrameResult, interval: int) -> list[FrameResult]:
    """若 fr 带时间范围（代表帧），按采样间隔扩展为多个时间点写回；否则原样返回。

    这样聚合逻辑无需感知去重——它看到的仍是完整时间序列。
    """
    tr = fr.time_range
    if not tr:
        return [fr]
    start = datetime.fromisoformat(tr[0])
    end = datetime.fromisoformat(tr[1])
    out = []
    cur = start
    while cur <= end:
        out.append(FrameResult(
            frame_ts=cur.isoformat(),
            context=fr.context,
            cats=fr.cats,
            activity=fr.activity,
        ))
        cur += timedelta(seconds=interval)
    return out or [fr]


def cmd_ingest(args) -> int:
    cfg_obj = cfg.load()
    state_dir = cfg.config_dir()
    video = Path(args.video)

    raw = args.results
    if raw.startswith("@"):
        raw = Path(raw[1:]).read_text(encoding="utf-8")
    results = json.loads(raw)

    if isinstance(results, dict):
        results = [results]

    interval = cfg_obj.frame_interval_seconds
    frames: list[FrameResult] = []
    errors: list[str] = []
    expanded = 0
    for i, d in enumerate(results):
        d = _apply_context_constraint(d)
        errs = validate_frame_result(d)
        if errs:
            errors.append(f"第 {i} 条: {'; '.join(errs)}")
            continue
        tr = d.get("time_range")
        time_range = tuple(tr) if (isinstance(tr, list) and len(tr) == 2) else None
        fr = FrameResult(
            frame_ts=d["frame_ts"],
            context=d["context"],
            cats=d.get("cats", []),
            activity=d.get("activity", {"type": "idle", "evidence": ""}),
            time_range=time_range,  # type: ignore[arg-type]
        )
        grown = _expand_frame(fr, interval)
        expanded += len(grown) - 1
        frames.extend(grown)

    append_frames(state_dir, args.date, frames)
    state.mark_processed(state_dir, video, result={"frames": len(frames)})
    _emit({
        "video": str(video),
        "date": args.date,
        "ingested": len(frames),
        "representatives": len(results) - len(errors),
        "expanded_by_dedup": expanded,
        "rejected": len(errors),
        "errors": errors,
    })
    return 0 if not errors else 1


def cmd_report(args) -> int:
    cfg_obj = cfg.load()
    state_dir = cfg.config_dir()
    all_frames = load_frames(state_dir, args.date)
    events = aggregate(all_frames,
                       merge_gap_seconds=cfg_obj.event_merge_gap_seconds)
    out = write_report(cfg_obj.reports_dir, args.date, events,
                       processed_files=0, skipped_files=0)
    _emit({
        "date": args.date,
        "frames": len(all_frames),
        "events": len(events),
        "report_path": str(out),
    })
    return 0


# ---------- 环境检查 ----------
def cmd_doctor(args) -> int:
    """检查运行环境：Python 版本、ffmpeg、配置；输出 JSON 供 agent 解析。

    全部就绪返回 0，任一缺失返回 1。ffmpeg 缺失时会附上当前平台的安装命令，
    方便 agent 直接提示用户手动安装（系统级依赖，本 skill 不自动安装）。
    """
    report: dict = {"checks": {}}

    py_ok = sys.version_info >= (3, 10)
    report["checks"]["python"] = {
        "ok": py_ok,
        "version": "%d.%d.%d" % sys.version_info[:3],
    }

    try:
        from scripts.extract_frames import find_ffmpeg, ffmpeg_install_hint
        report["checks"]["ffmpeg"] = {"ok": True, "path": find_ffmpeg()}
    except FileNotFoundError:
        report["checks"]["ffmpeg"] = {
            "ok": False,
            "install_hint": ffmpeg_install_hint(),
            "note": "系统级依赖，需手动安装；本 skill 不会自动安装",
        }

    try:
        cfg_obj = cfg.load()
        errs = cfg.validate(cfg_obj)
        report["checks"]["config"] = {
            "ok": not errs,
            "path": str(cfg.config_path()),
            "litter_box": str(cfg_obj.litter_box_dir),
            "feeder": str(cfg_obj.feeder_dir),
            "reports_dir": str(cfg_obj.reports_dir),
            "timezone": cfg_obj.timezone,
            "errors": errs,
        }
    except Exception as e:
        report["checks"]["config"] = {"ok": False, "errors": [f"配置加载失败: {e}"]}

    # Pillow：可选依赖，启用帧去重；缺失不阻断流程（extract 自动降级为不去重）
    try:
        from scripts.dedup import PILLOW_AVAILABLE, pillow_install_hint
        if PILLOW_AVAILABLE:
            import PIL
            report["checks"]["pillow"] = {
                "ok": True,
                "optional": True,
                "version": getattr(PIL, "__version__", "?"),
                "purpose": "帧去重（省 40-70% 识别 token）",
            }
        else:
            report["checks"]["pillow"] = {
                "ok": False,
                "optional": True,
                "install_hint": pillow_install_hint(),
                "note": "可选依赖；缺失时 extract 自动降级为不去重，skill 仍可用",
            }
    except Exception as e:
        report["checks"]["pillow"] = {"ok": False, "optional": True, "errors": [str(e)]}

    # overall 只看必需项（python / ffmpeg / config）；pillow 可选，不计入
    report["ok"] = all(report["checks"][k].get("ok")
                       for k in ("python", "ffmpeg", "config"))
    _emit(report)
    return 0 if report["ok"] else 1


# ---------- 批量抽帧（并行）----------
def cmd_batch_extract(args) -> int:
    """并行对当天所有待处理视频抽帧 + 去重，一次输出全部代表帧。

    用 ThreadPoolExecutor 并发跑 ffmpeg（子进程等待时释放 GIL）。相对逐个
    extract 加速明显；token 节省来自去重（与 extract 相同的去重逻辑）。
    """
    import concurrent.futures

    cfg_obj = cfg.load()
    tz = _tz_from_name(cfg_obj.timezone)
    state_dir = cfg.config_dir()

    litter = scan_date(cfg_obj.litter_box_dir, args.date, tz)
    feeder = scan_date(cfg_obj.feeder_dir, args.date, tz)
    all_files = [(f, "litter_box") for f in litter] + [(f, "feeder") for f in feeder]
    todo = state.filter_unprocessed(state_dir, [f for f, _ in all_files], force=False)
    todo_set = {str(f) for f in todo}
    targets = [(f, c) for f, c in all_files if str(f) in todo_set]

    results = []
    if targets:
        max_workers = min(len(targets), 4)
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as ex:
            fut_map = {ex.submit(_extract_and_dedup, f, c, cfg_obj, tz): (str(f), c)
                       for f, c in targets}
            for fut in concurrent.futures.as_completed(fut_map):
                vpath, ctx = fut_map[fut]
                try:
                    res = fut.result()
                    results.append({"video": vpath, "context": ctx, **res})
                except Exception as e:
                    results.append({"video": vpath, "context": ctx, "error": str(e)})

    results.sort(key=lambda r: (r["video"], r["context"]))
    _emit({
        "date": args.date,
        "videos": len(targets),
        "frame_count": sum(r.get("frame_count", 0) for r in results),
        "representative_count": sum(r.get("representative_count", 0) for r in results),
        "results": results,
    })
    return 0


# ---------- 入口 ----------
def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="cat-video-analyzer",
                                 description="猫咪监控视频分析（子命令式）")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_scan = sub.add_parser("scan", help="扫描指定日期的待处理视频")
    p_scan.add_argument("--date", required=True)
    p_scan.add_argument("--force", action="store_true")
    p_scan.set_defaults(func=cmd_scan)

    p_ex = sub.add_parser("extract", help="对单个视频抽帧")
    p_ex.add_argument("--video", required=True)
    p_ex.add_argument("--context", required=True,
                      choices=["litter_box", "feeder"])
    p_ex.add_argument("--out", default=None, help="帧输出目录，默认临时目录")
    p_ex.set_defaults(func=cmd_extract)

    p_in = sub.add_parser("ingest", help="写入 agent 识别的帧结果")
    p_in.add_argument("--video", required=True)
    p_in.add_argument("--date", required=True)
    p_in.add_argument("--results", required=True,
                      help="识别结果 JSON，或 @文件路径")
    p_in.set_defaults(func=cmd_ingest)

    p_rp = sub.add_parser("report", help="聚合并生成报告")
    p_rp.add_argument("--date", required=True)
    p_rp.set_defaults(func=cmd_report)

    p_doc = sub.add_parser("doctor", help="检查运行环境（Python / ffmpeg / 配置 / Pillow）")
    p_doc.set_defaults(func=cmd_doctor)

    p_be = sub.add_parser("batch-extract",
                          help="并行抽帧 + 去重（当天所有待处理视频）")
    p_be.add_argument("--date", required=True)
    p_be.set_defaults(func=cmd_batch_extract)

    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
