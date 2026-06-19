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


def cmd_extract(args) -> int:
    cfg_obj = cfg.load()
    tz = _tz_from_name(cfg_obj.timezone)
    video = Path(args.video)
    if not video.exists():
        print(json.dumps({"error": f"视频不存在: {video}"}), file=sys.stderr)
        return 1

    out_dir = Path(args.out) if args.out else Path(tempfile.mkdtemp(prefix="catva_"))
    frames = extract(video, out_dir, interval_seconds=cfg_obj.frame_interval_seconds)
    file_start = parse_video_timestamp(video, tz)

    payload = [{
        "frame_path": str(f.path),
        "frame_ts": (file_start + timedelta(seconds=f.offset_seconds)).isoformat(),
        "context": args.context,
    } for f in frames]
    _emit({"video": str(video), "out_dir": str(out_dir), "frames": payload})
    return 0


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

    frames: list[FrameResult] = []
    errors: list[str] = []
    for i, d in enumerate(results):
        d = _apply_context_constraint(d)
        errs = validate_frame_result(d)
        if errs:
            errors.append(f"第 {i} 条: {'; '.join(errs)}")
            continue
        frames.append(FrameResult(
            frame_ts=d["frame_ts"],
            context=d["context"],
            cats=d.get("cats", []),
            activity=d.get("activity", {"type": "idle", "evidence": ""}),
        ))

    append_frames(state_dir, args.date, frames)
    state.mark_processed(state_dir, video, result={"frames": len(frames)})
    _emit({
        "video": str(video),
        "date": args.date,
        "ingested": len(frames),
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

    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
