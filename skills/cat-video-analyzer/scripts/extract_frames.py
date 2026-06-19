"""用 ffmpeg 从视频抽帧。

为什么不自己解码
================
视频解码（H.264/H.265）用 Python 重写既慢又容易出问题；ffmpeg 是事实标准，
macOS (brew)、Linux (apt)、Windows (官方 exe / scoop) 都能用。这里只做
"找到 ffmpeg → 按间隔抽帧 → 返回帧路径列表"。

跨平台
======
- 优先用 PATH 中的 `ffmpeg`；找不到时回退到常见安装位置。
- 抽出的帧以 `frame_{相对秒数:06d}.jpg` 命名，相对秒数 = 该帧在视频内的偏移，
  这样上游不需要再解析 ffmpeg 输出就能拿到时间。
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


# 常见安装位置（按平台），仅在 PATH 找不到时回退
_FFMPEG_CANDIDATES = [
    "ffmpeg",
    "/usr/local/bin/ffmpeg",
    "/opt/homebrew/bin/ffmpeg",
    "/usr/bin/ffmpeg",
    # Windows
    r"C:\ffmpeg\bin\ffmpeg.exe",
    os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\WinGet\Packages\ffmpeg\bin\ffmpeg.exe"),
]


def ffmpeg_install_hint() -> str:
    """返回当前平台安装 ffmpeg 的命令（缺失时用于提示用户手动安装）。"""
    if sys.platform == "darwin":
        return "brew install ffmpeg"
    if sys.platform.startswith("linux"):
        return ("sudo apt install ffmpeg   # Debian/Ubuntu"
                "；Fedora: sudo dnf install ffmpeg；Arch: sudo pacman -S ffmpeg")
    if sys.platform == "win32":
        return ("winget install Gyan.FFmpeg   # 或 choco install ffmpeg / "
                "scoop install ffmpeg")
    return "见 https://ffmpeg.org/download.html"


def find_ffmpeg() -> str:
    found = shutil.which("ffmpeg")
    if found:
        return found
    for c in _FFMPEG_CANDIDATES:
        if c and Path(c).exists():
            return c
    raise FileNotFoundError(
        "找不到 ffmpeg。ffmpeg 是系统级依赖，本 skill 不会自动安装，请手动安装：\n"
        f"  {ffmpeg_install_hint()}\n"
        "装好后 ffmpeg 会出现在 PATH 中，重新运行即可。"
    )


@dataclass
class ExtractedFrame:
    path: Path
    offset_seconds: float  # 在源视频内的偏移


def extract(
    video_path: Path,
    out_dir: Path,
    *,
    interval_seconds: float = 12.0,
    ffmpeg: str | None = None,
) -> list[ExtractedFrame]:
    """抽帧。

    返回按 offset 升序排列的帧列表。out_dir 会被创建。
    interval_seconds=12 意味着每 12 秒一帧；1 分钟视频 → 约 5 帧。
    """
    ffmpeg = ffmpeg or find_ffmpeg()
    out_dir.mkdir(parents=True, exist_ok=True)

    # fps = 1/interval。用 fps 过滤比 -ss 切片更稳，且天然均匀。
    fps = 1.0 / float(interval_seconds)
    pattern = str(out_dir / "frame_%06d.jpg")

    cmd = [
        ffmpeg,
        "-hide_banner",
        "-loglevel", "error",
        "-i", str(video_path),
        "-vf", f"fps={fps}",
        "-q:v", "3",            # JPEG 质量（2-5 视觉好，体积适中）
        "-y",                   # 覆盖
        pattern,
    ]
    # Windows 上 subprocess 需要这个，否则可能弹窗
    res = subprocess.run(cmd, capture_output=True, text=True,
                         creationflags=_creation_flags())
    if res.returncode != 0:
        raise RuntimeError(
            f"ffmpeg 抽帧失败 ({video_path}):\n{res.stderr.strip()}"
        )

    frames: list[ExtractedFrame] = []
    for p in sorted(out_dir.glob("frame_*.jpg")):
        # 文件名 frame_000001.jpg → 第 1 帧 → 偏移 0s
        idx = int(p.stem.split("_")[1])
        offset = (idx - 1) * float(interval_seconds)
        frames.append(ExtractedFrame(path=p, offset_seconds=offset))
    return frames


def _creation_flags() -> int:
    """Windows 下避免弹出控制台窗口；其他平台返回 0。"""
    if sys.platform == "win32":
        CREATE_NO_WINDOW = 0x08000000
        return CREATE_NO_WINDOW
    return 0


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="抽帧自检")
    ap.add_argument("video", type=Path)
    ap.add_argument("--out", type=Path, default=Path("./frames_out"))
    ap.add_argument("--interval", type=float, default=12.0)
    a = ap.parse_args()
    fs = extract(a.video, a.out, interval_seconds=a.interval)
    print(f"抽出 {len(fs)} 帧到 {a.out}")
    for f in fs[:3]:
        print(f"  {f.path.name} @ {f.offset_seconds:.1f}s")
