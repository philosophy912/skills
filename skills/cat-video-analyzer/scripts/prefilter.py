"""运动检测预筛：在送模型识别前，用极低成本判定一段视频「有没有动过」。

为什么需要
==========
小米摄像头连续录像、NAS 上每分钟一个文件 → 每天 2880 段（2 摄像头 × 24h）。
其中绝大多数段是空场景或猫在睡觉不动。如果无差别地每段都抽帧送 agent
识别，token 会爆（见 references 里的 token 账）。本模块用 ffmpeg 抽极少数
缩略图 + Pillow 算相邻帧像素差，把「整段静止」的段判定为 silent——这些段
不进识别管线，直接在 state 里标记，下次 scan 跳过。

设计要点
========
- 对每个视频抽 3 帧（首 0s / 中 30s / 尾 60s）缩到 32×32 灰度。
- 用「相邻帧差」而非「对背景帧差」：光照渐变是低频全局变化，相邻 30s 几乎
  归零；猫的位移是高频局部变化仍能捕获——故红外夜视渐变不会把空场景误判
  成有运动。
- 阈值 motion_threshold（32×32 灰度相邻帧平均像素差，0-255）。默认 2.0，
  首跑后按 skipped_silent 占比和人工抽查调。
- 纯本地 CPU，不送模型，不消耗多模态 token。

依赖
====
ffmpeg（必需）+ Pillow（必需：预筛依赖它算像素差。Pillow 缺失时本模块不可用，
调用方应让 prefilter 报错提示安装——预筛不是可选优化，是连续录像场景的必需）。
"""
from __future__ import annotations

import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

from scripts.extract_frames import find_ffmpeg, _creation_flags

try:
    from PIL import Image  # type: ignore
    PILLOW_AVAILABLE = True
except ImportError:  # pragma: no cover
    Image = None  # type: ignore
    PILLOW_AVAILABLE = False


_THUMB_SIZE = 32  # 缩略图边长（32×32 灰度），足够判定有无运动，极小


@dataclass
class MotionResult:
    has_motion: bool
    max_diff: float        # 相邻帧最大平均像素差（调试用）
    diffs: list[float]     # 各相邻帧差值


def _extract_thumbs(video: Path, out_dir: Path, offsets: list[float]) -> list[Path]:
    """用 ffmpeg 在指定秒数各抽一帧 32×32 灰度 PNG。"""
    ffmpeg = find_ffmpeg()
    paths: list[Path] = []
    for i, off in enumerate(offsets):
        p = out_dir / f"thumb_{i:02d}.png"
        cmd = [
            ffmpeg, "-hide_banner", "-loglevel", "error",
            "-ss", f"{off:.2f}", "-i", str(video),
            "-frames:v", "1",
            "-vf", f"scale={_THUMB_SIZE}:{_THUMB_SIZE}:force_original_aspect_ratio=decrease,"
                   f"pad={_THUMB_SIZE}:{_THUMB_SIZE}:(ow-iw)/2:(oh-ih)/2,format=gray",
            "-y", str(p),
        ]
        res = subprocess.run(cmd, capture_output=True, text=True,
                             creationflags=_creation_flags())
        if res.returncode == 0 and p.exists():
            paths.append(p)
    return paths


def _avg_pixel_diff(a: Path, b: Path) -> float:
    """两张等大灰度图的平均绝对像素差（0-255）。"""
    assert Image is not None
    pa = list(Image.open(a).getdata())
    pb = list(Image.open(b).getdata())
    if len(pa) != len(pb) or not pa:
        return 0.0
    return sum(abs(x - y) for x, y in zip(pa, pb)) / len(pa)


def detect_motion(
    video: Path,
    *,
    threshold: float = 2.0,
    duration_seconds: float = 60.0,
) -> MotionResult:
    """判定一段视频是否有运动。

    抽首(0s)/中/尾三帧缩略图，算相邻帧平均像素差，最大差 > threshold → 有运动。
    duration_seconds 用于定位中帧/尾帧（小米录像默认 60s/段）。

    Pillow 缺失时抛 RuntimeError（预筛是连续录像场景的必需步骤，不静默降级）。
    """
    if not PILLOW_AVAILABLE:
        raise RuntimeError(
            "预筛需要 Pillow（pip install pillow）。连续录像场景下预筛是必需步骤，"
            "不能跳过——否则每段都送模型识别会导致 token 爆炸。")

    mid = duration_seconds / 2.0
    offsets = [0.0, mid, max(mid, duration_seconds - 0.1)]
    with tempfile.TemporaryDirectory(prefix="catva_pf_") as td:
        thumbs = _extract_thumbs(video, Path(td), offsets)
        if len(thumbs) < 2:
            # 抽不到足够帧（视频太短/损坏）→ 保守判定为有运动，交给后续流程
            return MotionResult(has_motion=True, max_diff=float("inf"), diffs=[])

        diffs = [_avg_pixel_diff(thumbs[i], thumbs[i + 1])
                 for i in range(len(thumbs) - 1)]
        max_diff = max(diffs) if diffs else 0.0
        return MotionResult(
            has_motion=max_diff > threshold,
            max_diff=round(max_diff, 3),
            diffs=[round(d, 3) for d in diffs],
        )
