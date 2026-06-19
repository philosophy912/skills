"""生成每日 Markdown 报告。

报告结构（详见 references/report-format.md）
==========================================
1. 标题 + 日期 + 汇总摘要
2. 每只猫的小节：吃饭次数/总时长、上厕所次数/总时长
3. 当日时间线：按时间排列的事件列表
4. 数据来源说明（处理了多少文件、跳过了多少）
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from pathlib import Path

from scripts.aggregate import CatEvent


_CAT_CN = {"tabby": "狸花猫", "black": "黑猫", "unknown": "未知猫"}
_ACT_CN = {"eating": "吃饭", "toileting": "上厕所"}


def summarize(events: list[CatEvent]) -> dict:
    """返回 {(identity, activity): {count, total_seconds}}。"""
    stats: dict[tuple[str, str], dict] = defaultdict(
        lambda: {"count": 0, "total_seconds": 0.0}
    )
    for e in events:
        stats[(e.identity, e.type)]["count"] += 1
        stats[(e.identity, e.type)]["total_seconds"] += e.duration_seconds
    return stats


def _fmt_duration(seconds: float) -> str:
    m, s = divmod(int(round(seconds)), 60)
    return f"{m}分{s:02d}秒"


def _fmt_ts(iso: str) -> str:
    try:
        return datetime.fromisoformat(iso).strftime("%H:%M:%S")
    except ValueError:
        return iso


def render(
    date_str: str,
    events: list[CatEvent],
    *,
    processed_files: int = 0,
    skipped_files: int = 0,
) -> str:
    stats = summarize(events)

    # 出现过的猫（保持稳定顺序：狸花→黑→未知）
    identities_seen = sorted(
        {e.identity for e in events},
        key=lambda i: ["tabby", "black", "unknown"].index(i) if i in ["tabby", "black", "unknown"] else 99,
    )

    lines: list[str] = []
    lines.append(f"# 猫咪行为日报 · {date_str}")
    lines.append("")
    lines.append(
        f"> 本报告由 cat-video-analyzer 自动生成。"
        f"共处理 **{processed_files}** 个视频文件，跳过已处理 **{skipped_files}** 个。"
    )
    lines.append("")

    # 汇总表
    total_eating = sum(s["count"] for (i, a), s in stats.items() if a == "eating")
    total_toilet = sum(s["count"] for (i, a), s in stats.items() if a == "toileting")
    lines.append("## 汇总")
    lines.append("")
    lines.append(f"- 🍚 吃饭事件：**{total_eating}** 次")
    lines.append(f"- 🚽 上厕所事件：**{total_toilet}** 次")
    lines.append("")

    # 每只猫
    if not identities_seen:
        lines.append("## 本日无活动")
        lines.append("")
        lines.append("今天没有识别到吃饭或上厕所事件。可能是猫咪休息日，"
                     "也可能是红外夜视/画面遮挡导致识别率下降，建议抽查原始视频。")
    else:
        for ident in identities_seen:
            cn = _CAT_CN.get(ident, ident)
            lines.append(f"## {cn}（{ident}）")
            lines.append("")
            lines.append("| 行为 | 次数 | 总时长 |")
            lines.append("|------|------|--------|")
            for act in ("eating", "toileting"):
                s = stats.get((ident, act), {"count": 0, "total_seconds": 0.0})
                lines.append(
                    f"| {_ACT_CN[act]} | {s['count']} | {_fmt_duration(s['total_seconds'])} |"
                )
            lines.append("")

    # 时间线
    if events:
        lines.append("## 时间线")
        lines.append("")
        lines.append("| 时间 | 行为 | 猫咪 | 时长 | 证据 |")
        lines.append("|------|------|------|------|------|")
        for e in sorted(events, key=lambda x: x.start_ts):
            evidence = (e.evidence_samples[0] if e.evidence_samples else "")[:40]
            lines.append(
                f"| {_fmt_ts(e.start_ts)}-{_fmt_ts(e.end_ts)} "
                f"| {_ACT_CN.get(e.type, e.type)} "
                f"| {_CAT_CN.get(e.identity, e.identity)} "
                f"| {_fmt_duration(e.duration_seconds)} "
                f"| {evidence} |"
            )
        lines.append("")

    lines.append("---")
    lines.append("")
    lines.append("*如需重新生成报告（不重新识别），运行 "
                 "`python -m scripts.run report --date {}`。*".format(date_str))
    return "\n".join(lines)


def write_report(
    reports_dir: Path,
    date_str: str,
    events: list[CatEvent],
    **kwargs,
) -> Path:
    reports_dir.mkdir(parents=True, exist_ok=True)
    out = reports_dir / f"{date_str}.md"
    out.write_text(render(date_str, events, **kwargs), encoding="utf-8")
    return out


if __name__ == "__main__":
    # 自检：用假事件渲染一份报告
    from datetime import timedelta
    fake = [
        CatEvent(type="eating", start_ts="2026-06-11T07:30:12+08:00",
                 end_ts="2026-06-11T07:34:00+08:00", duration_seconds=228,
                 identity="tabby", identity_confidence=0.93, frame_count=18,
                 evidence_samples=["狸花低头吃粮，鼻尖靠近金属碗"]),
        CatEvent(type="toileting", start_ts="2026-06-11T09:12:00+08:00",
                 end_ts="2026-06-11T09:14:30+08:00", duration_seconds=150,
                 identity="black", identity_confidence=0.88, frame_count=12,
                 evidence_samples=["黑猫蹲伏在砂盆内刨沙"]),
    ]
    print(render("2026-06-11", fake, processed_files=120, skipped_files=0))
