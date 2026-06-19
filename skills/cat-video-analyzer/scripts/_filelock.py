"""跨平台文件锁。

`fcntl` 在 Windows 上没有；`msvcrt` 在 POSIX 上没有。用 try/import 软依赖，
都没有就退化为无锁（仅适合单机单进程场景，state.py 的写会失去并发安全）。
"""
from __future__ import annotations

import contextlib
import os
from pathlib import Path


@contextlib.contextmanager
def file_lock(path: Path):
    """对 path 同级创建一个 .lock 哨兵文件并加锁。

    注意：调用方应当传入"已存在的目标文件路径"；本函数不会创建目标本身。
    """
    lock_path = path.with_suffix(path.suffix + ".lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(str(lock_path), os.O_CREAT | os.O_RDWR, 0o644)
    try:
        _lock_impl(fd)
        yield
    finally:
        try:
            _unlock_impl(fd)
        finally:
            os.close(fd)


# ---------- 平台实现 ----------
def _lock_impl(fd: int) -> None:
    try:
        import fcntl  # type: ignore
        fcntl.flock(fd, fcntl.LOCK_EX)
        return
    except ImportError:
        pass
    try:
        import msvcrt  # type: ignore
        # 锁 1 字节就够；偏移 0
        msvcrt.locking(fd, msvcrt.LK_LOCK, 1)
        return
    except ImportError:
        pass
    # 退化为无锁 —— 显式警告一次
    import warnings
    warnings.warn(
        "file_lock: 找不到 fcntl/msvcrt，回退为无锁模式（不推荐并发运行）",
        RuntimeWarning,
        stacklevel=2,
    )


def _unlock_impl(fd: int) -> None:
    try:
        import fcntl  # type: ignore
        fcntl.flock(fd, fcntl.LOCK_UN)
        return
    except ImportError:
        pass
    try:
        import msvcrt  # type: ignore
        msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
        return
    except ImportError:
        pass
