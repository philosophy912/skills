"""状态管理：基于"路径 + mtime + 大小"的指纹，避免重复处理。

设计原则
========
1. 状态文件存放在用户配置目录（默认 ~/.config/cat-video-analyzer/state.json）。
2. 每条记录形如：
     {"path": "/abs/path/to/clip.mp4",
      "mtime": 1718094612.123,        # 文件最后修改时间
      "size":  1234567,               # 字节数
      "processed_at": "2026-06-11T14:30:00+08:00",
      "result": {...}}                # 该文件的识别/聚合结果（可为空）
3. 判定"已处理"：state 中存在同 path 且 mtime+size 都一致 → 跳过。
   只比对 path 不够：NAS 上同名文件被覆盖时 mtime 会变，必须双键。
4. 状态文件必须可被并发写安全地追加（多进程/多 cron 重叠运行），用
   `fcntl`（POSIX）/ `msvcrt`（Windows）做文件锁，跨平台用一个轻量封装。

跨平台注意
==========
- 路径统一用 `pathlib.Path`，存储到 JSON 时转 `str(Path)`。
- Windows 路径大小写不敏感：指纹前 `Path.resolve()` 但**不**改大小写，
  因为同一逻辑路径可能以不同大小写出现，保留用户原始写法更稳。
- 文件锁实现见 `scripts/_filelock.py`。
"""
from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from scripts._filelock import file_lock


STATE_FILENAME = "state.json"


@dataclass
class FileRecord:
    path: str
    mtime: float
    size: int
    processed_at: str
    result: dict | None = None  # 预留：每文件的识别/聚合摘要
    tag: str | None = None      # 处理方式标记，如 "silent"（预筛判为无运动，静默跳过）


def state_path(config_dir: Path) -> Path:
    return config_dir / STATE_FILENAME


def _read_unlocked(path: Path) -> dict:
    if not path.exists():
        return {"version": 1, "records": {}}
    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError:
        # 状态文件损坏：备份 + 重建
        backup = path.with_suffix(f".corrupt-{int(time.time())}.json")
        path.rename(backup)
        return {"version": 1, "records": {}}
    if "records" not in data:
        data["records"] = {}
    return data


def _write_unlocked(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2, sort_keys=True)
    os.replace(tmp, path)


def load(config_dir: Path) -> dict:
    """线程/进程安全地读出整张状态表。"""
    with file_lock(state_path(config_dir)):
        return _read_unlocked(state_path(config_dir))


def save(config_dir: Path, data: dict) -> None:
    with file_lock(state_path(config_dir)):
        _write_unlocked(state_path(config_dir), data)


def fingerprint(p: Path) -> tuple[float, int]:
    """文件指纹 = (mtime, size)。文件不存在抛 FileNotFoundError。"""
    st = p.stat()
    return (st.st_mtime, st.st_size)


def is_processed(records: dict, p: Path, *, force: bool = False) -> bool:
    """是否应该跳过这个文件。force=True 时永远返回 False。"""
    if force:
        return False
    key = str(p)
    rec = records.get(key)
    if not rec:
        return False
    try:
        cur_mtime, cur_size = fingerprint(p)
    except FileNotFoundError:
        # 文件已删除/不可访问 → 视为已处理（不要让 skill 反复报错）
        return True
    return rec.get("mtime") == cur_mtime and rec.get("size") == cur_size


def mark_processed(
    config_dir: Path,
    p: Path,
    result: dict | None = None,
    *,
    tag: str | None = None,
) -> None:
    """把文件标记为已处理。读改写全程持锁。

    tag：处理方式标记。预筛判为「无运动」的段用 tag="silent" 标记——它们不进
    识别管线、不写 jsonl，但仍要标记，否则下次 scan 又会重列、预筛白跑。
    """
    mtime, size = fingerprint(p)
    rec = FileRecord(
        path=str(p),
        mtime=mtime,
        size=size,
        processed_at=datetime.now(timezone.utc).isoformat(),
        result=result,
        tag=tag,
    )
    with file_lock(state_path(config_dir)):
        data = _read_unlocked(state_path(config_dir))
        data["records"][str(p)] = asdict(rec)
        _write_unlocked(state_path(config_dir), data)


def silent_paths(config_dir: Path) -> set[str]:
    """返回所有被预筛标记为 silent（无运动）的文件路径。

    供 prefilter --recheck-silent 使用：只复检这些段，不动已识别的运动段。
    """
    data = load(config_dir)
    return {k for k, v in data.get("records", {}).items()
            if v.get("tag") == "silent"}


def clear_silent(config_dir: Path, paths: Iterable[str]) -> int:
    """从 state 中移除指定 silent 记录，使其重新进入待处理。返回移除条数。

    供 prefilter --recheck-silent 复检前清场：把上轮判为 silent 的段摘出来重判。
    持锁读改写。只删 tag=="silent" 的，避免误删真正识别过的记录。
    """
    targets = set(paths)
    removed = 0
    with file_lock(state_path(config_dir)):
        data = _read_unlocked(state_path(config_dir))
        for k in list(data.get("records", {}).keys()):
            if k in targets and data["records"][k].get("tag") == "silent":
                del data["records"][k]
                removed += 1
        if removed:
            _write_unlocked(state_path(config_dir), data)
    return removed


def filter_unprocessed(
    config_dir: Path,
    files: Iterable[Path],
    *,
    force: bool = False,
) -> list[Path]:
    """从候选文件列表中过滤出真正需要处理的文件。"""
    data = load(config_dir)
    records = data.get("records", {})
    return [f for f in files if not is_processed(records, f, force=force)]


# ---------- CLI 自检 ----------
if __name__ == "__main__":
    import argparse
    import tempfile

    ap = argparse.ArgumentParser(description="cat-video-analyzer state self-check")
    ap.add_argument("--tmp", action="store_true", help="在临时目录跑一遍自检")
    args = ap.parse_args()

    if args.tmp:
        with tempfile.TemporaryDirectory() as td:
            cd = Path(td) / "cfg"
            fake = cd / "fake.mp4"
            cd.mkdir(parents=True, exist_ok=True)
            fake.write_bytes(b"x" * 100)
            fake.touch()  # 触发新 mtime

            assert filter_unprocessed(cd, [fake]) == [fake], "首次应视为未处理"
            mark_processed(cd, fake, result={"events": 0})
            assert filter_unprocessed(cd, [fake]) == [], "处理后应被过滤"
            # 模拟文件被覆盖
            fake.write_bytes(b"y" * 200)
            assert filter_unprocessed(cd, [fake]) == [fake], "内容变化应重新处理"
            print("state self-check OK")
    else:
        ap.print_help()
