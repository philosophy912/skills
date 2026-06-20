"""帧去重：用 dHash 把相邻相似帧合并，降低送 agent 识别的帧数。

为什么需要
==========
抽帧是固定间隔（默认每 12s 一帧），但监控视频里大量相邻帧画面几乎相同
（猫没动、或根本没猫）。逐帧让 agent 识别这些冗余帧浪费 token。本模块对
相邻帧计算差异哈希（dHash），把汉明距离小于阈值的帧分到同一组，每组只
保留一个"代表帧"，agent 只需识别代表帧；ingest 再把结果扩展回整段时间。

依赖
====
需要 Pillow（``pip install pillow``）。Pillow 缺失时本模块不可用，调用方
应**降级为不去重**——skill 仍能正常运行，只是不省 token。Pillow 是可选
依赖，doctor 会检查并提示安装。

dHash 原理
==========
把图缩成 9×8 灰度，比较每个像素与其右邻的大小（大=1），得到 64 bit 指纹。
两张图的汉明距离越小越相似。阈值默认 5（64 bit 中 ≤5 位不同），适合监控
视频；越小越严格（只合并几乎完全相同的帧）。
"""
from __future__ import annotations

from dataclasses import dataclass

try:
    from PIL import Image  # type: ignore
    PILLOW_AVAILABLE = True
except ImportError:  # pragma: no cover - 依赖缺失的降级路径
    Image = None  # type: ignore
    PILLOW_AVAILABLE = False


def pillow_install_hint() -> str:
    return "pip install pillow"


def _dhash(path: str, size: int = 8) -> int:
    """计算一张图的 dHash（size*size bit）。需 Pillow。"""
    assert Image is not None
    im = Image.open(path).convert("L").resize((size + 1, size))
    px = list(im.getdata())
    bits = 0
    for r in range(size):
        for c in range(size):
            idx = r * (size + 1) + c
            if px[idx] > px[idx + 1]:
                bits |= 1 << (r * size + c)
    return bits


def _hamming(a: int, b: int) -> int:
    return bin(a ^ b).count("1")


@dataclass
class FrameGroup:
    """一组相邻相似帧。indices 为各帧在原始列表中的下标，首个即代表帧。"""
    indices: list[int]


def group_similar(frame_paths: list[str], threshold: int = 5) -> list[FrameGroup]:
    """把相邻、dHash 汉明距离 ≤ threshold 的帧分到一组。

    - 只合并相邻帧（保持时间顺序，不跨段合并）。
    - 每组首帧作为代表帧。
    - threshold 越小越严格。默认 5。
    """
    if not frame_paths:
        return []
    hashes = [_dhash(p) for p in frame_paths]
    groups: list[FrameGroup] = [FrameGroup([0])]
    for i in range(1, len(hashes)):
        prev_idx = groups[-1].indices[-1]  # 与当前组最后一帧比较
        if _hamming(hashes[i], hashes[prev_idx]) <= threshold:
            groups[-1].indices.append(i)
        else:
            groups.append(FrameGroup([i]))
    return groups
