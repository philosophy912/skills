"""识别结果的数据结构定义。

本 skill 的执行者是 **agent**（Claude Code / OpenCode / Codex 等）。
逐帧识别由 agent 自身的多模态能力完成 —— 脚本不调用任何外部模型 API。
本模块只定义 agent 写回识别结果时必须遵循的数据结构，供
`aggregate` / `report` 使用。

识别"看什么、怎么判断"见 references/recognition-protocol.md。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


CatIdentity = Literal["tabby", "black", "unknown"]
ActivityType = Literal["eating", "toileting", "idle", "absent"]
SceneContext = Literal["litter_box", "feeder"]


@dataclass
class FrameResult:
    """单帧的识别结果。agent 识别完一帧后产出这个结构，由 ingest 写入 jsonl。

    若该帧是"代表帧"（extract 去重后代表一段相似帧），time_range 标明它覆盖的
    时间范围 [start, end]；ingest 会据此扩展为多个采样点写回 jsonl，聚合逻辑
    无需感知去重。None 表示普通单帧。
    """

    frame_ts: str          # ISO8601 带时区，该帧的绝对时间
    context: SceneContext  # 来源：litter_box / feeder
    cats: list[dict]       # [{"identity": "tabby"|"black"|"unknown", "confidence": 0.0-1.0}]
    activity: dict         # {"type": "eating"|"toileting"|"idle"|"absent", "evidence": "..."}
    time_range: tuple[str, str] | None = None  # 代表帧覆盖的 [start_ts, end_ts]
    raw_text: str = ""     # 可选，agent 的原始备注，便于排查


def validate_frame_result(d: dict) -> list[str]:
    """轻量校验 agent 回传的字典，返回错误信息列表（空=合法）。"""
    errs: list[str] = []
    if "frame_ts" not in d:
        errs.append("缺少 frame_ts")
    ctx = d.get("context")
    if ctx not in ("litter_box", "feeder"):
        errs.append(f"context 必须是 litter_box/feeder，得到 {ctx!r}")
    act = d.get("activity", {})
    if act.get("type") not in ("eating", "toileting", "idle", "absent"):
        errs.append(f"activity.type 非法：{act.get('type')!r}")
    for c in d.get("cats", []):
        if c.get("identity") not in ("tabby", "black", "unknown"):
            errs.append(f"cat.identity 非法：{c.get('identity')!r}")
    return errs
