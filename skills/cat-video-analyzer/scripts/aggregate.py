"""事件聚合：把"逐帧识别结果"合并成"行为事件"。

为什么需要这一步
================
抽帧 + 识别得到的是离散的快照（如 14:30:00 eating、14:30:12 eating、
14:30:24 idle、14:30:36 eating）。一只猫吃一次饭可能横跨多帧，中间有
一两帧识别抖动很正常。聚合规则把"连续的同类活动"收拢成一条事件，
并容忍短间隔。

规则（详见 references/aggregation-rules.md）
============================================
1. 按时间排序帧。
2. 同一 activity.type 连续出现，合并为一个候选事件。
3. 两个同类候选事件间隔 < event_merge_gap_seconds（默认 30s）→ 合并。
4. 事件最短帧数过滤：默认按场景分段——猫砂盆 1 帧（救黑猫 <24s 快速进出），
   喂食机 2 帧（过滤单帧误判）。少于则丢弃，避免把模型偶发的误判固化成事件。
5. 参与的猫 identity：取事件内出现频次最高的那个；频次相同取置信度最高。
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Iterable

from scripts.schema import FrameResult


@dataclass
class CatEvent:
    type: str                    # eating | toileting
    start_ts: str                # ISO8601
    end_ts: str                  # ISO8601
    duration_seconds: float
    identity: str                # tabby | black | unknown
    identity_confidence: float
    frame_count: int
    evidence_samples: list[str] = field(default_factory=list)


def _to_dt(ts: str) -> datetime:
    return datetime.fromisoformat(ts)


def _merge_candidates(
    cands: list[list[FrameResult]],
    gap: float,
) -> list[list[FrameResult]]:
    """合并同类、间隔小于 gap 的候选段。"""
    if not cands:
        return []
    merged: list[list[FrameResult]] = [cands[0]]
    for cur in cands[1:]:
        prev = merged[-1]
        prev_end = _to_dt(prev[-1].frame_ts)
        cur_start = _to_dt(cur[0].frame_ts)
        if (cur_start - prev_end).total_seconds() <= gap:
            merged[-1] = prev + cur
        else:
            merged.append(cur)
    return merged


def _pick_identity(frames: list[FrameResult]) -> tuple[str, float]:
    """事件内出现频次最高的猫 + 其最高置信度。"""
    ident_counter: Counter[str] = Counter()
    best_conf: dict[str, float] = {}
    for fr in frames:
        for c in fr.cats:
            ident = c.get("identity", "unknown")
            conf = float(c.get("confidence", 0.0))
            ident_counter[ident] += 1
            best_conf[ident] = max(best_conf.get(ident, 0.0), conf)
    if not ident_counter:
        return "unknown", 0.0
    # 频次优先；并列取置信度
    top = sorted(ident_counter.items(), key=lambda kv: (-kv[1], -best_conf.get(kv[0], 0)))
    identity = top[0][0]
    return identity, best_conf.get(identity, 0.0)


def aggregate(
    frames: Iterable[FrameResult],
    *,
    merge_gap_seconds: float = 30.0,
    min_frames: int | dict = 2,
) -> list[CatEvent]:
    """主聚合入口。

    min_frames：单一整数（所有 context 统一）或 {context: n} 映射（按场景分段，
    用于「猫砂盆 1 帧兜底快速进出、喂食机 2 帧过滤误判」）。
    """
    ordered = sorted(frames, key=lambda f: f.frame_ts)
    if not ordered:
        return []

    def _min_for(ctx: str) -> int:
        if isinstance(min_frames, dict):
            return int(min_frames.get(ctx, min_frames.get("feeder", 2)))
        return int(min_frames)

    # 1) 按 activity.type 切连续段
    segments: list[list[FrameResult]] = []
    cur_type: str | None = None
    for fr in ordered:
        a_type = fr.activity.get("type", "idle")
        if a_type in ("idle", "absent"):
            cur_type = None
            continue
        if a_type != cur_type:
            segments.append([fr])
            cur_type = a_type
        else:
            segments[-1].append(fr)

    # 只保留关心的活动类型
    segments = [s for s in segments
                if s[0].activity.get("type") in ("eating", "toileting")]

    # 2) 按 type 分组后做间隔合并（不同 type 之间不合并）
    by_type: dict[str, list[list[FrameResult]]] = {}
    for s in segments:
        by_type.setdefault(s[0].activity["type"], []).append(s)

    events: list[CatEvent] = []
    for a_type, cands in by_type.items():
        for seg in _merge_candidates(cands, merge_gap_seconds):
            # 最短帧数按该段所属 context 取（段内 context 理论一致，取首帧）
            ctx = seg[0].context
            if len(seg) < _min_for(ctx):
                continue
            start = _to_dt(seg[0].frame_ts)
            end = _to_dt(seg[-1].frame_ts)
            identity, conf = _pick_identity(seg)
            events.append(CatEvent(
                type=a_type,
                start_ts=start.isoformat(),
                end_ts=end.isoformat(),
                duration_seconds=round((end - start).total_seconds(), 1),
                identity=identity,
                identity_confidence=round(conf, 2),
                frame_count=len(seg),
                evidence_samples=[f.activity.get("evidence", "")
                                  for f in seg[:2]],
            ))

    events.sort(key=lambda e: e.start_ts)
    return events


# ---------- CLI 自检（用假帧数据）----------
if __name__ == "__main__":
    base = datetime(2026, 6, 11, 14, 30, 0)

    def fr(seconds: int, a_type: str, identity: str = "", ev: str = "") -> FrameResult:
        ts = (base + timedelta(seconds=seconds)).isoformat()
        cats = [{"identity": identity, "confidence": 0.9}] if identity else []
        return FrameResult(
            frame_ts=ts, context="feeder", cats=cats,
            activity={"type": a_type, "evidence": ev or a_type},
        )

    demo = [
        fr(0, "absent"),
        fr(12, "eating", "tabby", "狸花低头吃粮"),
        fr(24, "eating", "tabby"),
        fr(36, "idle"),
        fr(48, "eating", "tabby"),   # 间隔 24s < 30 → 应合并
        fr(60, "eating", "tabby"),
        fr(72, "absent"),
        fr(84, "eating", "black", "黑猫来吃"),  # 间隔 12s 但不同猫不同事件? 同 type 合并
    ]
    evs = aggregate(demo, merge_gap_seconds=30, min_frames=2)
    print(f"聚合出 {len(evs)} 个事件：")
    for e in evs:
        print(f"  [{e.type}] {e.start_ts[11:19]}-{e.end_ts[11:19]} "
              f"({e.duration_seconds}s, {e.identity}, {e.frame_count}帧)")
    # 期望：1 个 eating 事件（14:30:12 起，合并到 14:31:24），
    # identity 应为 tabby（频次更高）
