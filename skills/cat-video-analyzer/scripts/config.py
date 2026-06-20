"""跨平台配置加载。

设计
====
- 配置文件位置按平台惯例：
    * POSIX (macOS/Linux/WSL): ~/.config/cat-video-analyzer/config.toml
    * Windows: %APPDATA%/cat-video-analyzer/config.toml
  可被环境变量 CAT_VIDEO_ANALYZER_CONFIG 覆盖。
- 优先级（高→低）: 环境变量 > 配置文件 > 代码内默认值。
- 用标准库 tomllib（Python 3.11+）读 TOML；3.10 fallback 到一个极简解析器。
  （不强依赖 tomli，避免给用户增加 pip 负担。）

关键字段
========
[nas]
litter_box = "/path/to/猫砂盆摄像头视频"
feeder     = "/path/to/喂食机摄像头视频"

[output]
reports_dir = "/path/to/reports"
timezone    = "Asia/Shanghai"

[processing]
# 采样间隔：可写单一整数（两个 context 都用它），也可按场景分段
# 分段写法用于「猫砂盆收到 6s 救黑猫 <24s 快速进出、喂食机保持 12s」
frame_interval_seconds.litter_box = 6
frame_interval_seconds.feeder     = 12
event_merge_gap_seconds = 30  # 同一行为间隔小于此值则合并
frame_max_side = 768          # 代表帧长边像素上限；降采样省 6x token（见 references）
min_frames.litter_box = 1     # 猫砂盆单帧 toileting 也记录（快速进出兜底）
min_frames.feeder     = 2     # 喂食机要求连续 2 帧才成事件
motion_threshold = 2.0        # 预筛：32x32 灰度相邻帧平均像素差 > 此值判定有运动

[model]
provider    = "anthropic"     # 目前只实现 anthropic
name        = "claude-sonnet-4-6"
max_concurrency = 4
"""
from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field
from pathlib import Path

if sys.version_info >= (3, 11):
    import tomllib  # type: ignore
else:
    tomllib = None  # fallback 在 _load_toml 中处理


DEFAULT_CONFIG = {
    "output": {
        "reports_dir": str(Path.home() / "Documents" / "cat-reports"),
        "timezone": "Asia/Shanghai",
    },
    "processing": {
        "frame_interval_seconds": {"litter_box": 6, "feeder": 12},
        "event_merge_gap_seconds": 30,
        "dedup_enabled": True,
        "dedup_hamming_threshold": 5,
        "frame_max_side": 768,
        "min_frames": {"litter_box": 1, "feeder": 2},
        "motion_threshold": 2.0,
    },
    "model": {
        "provider": "anthropic",
        "name": "claude-sonnet-4-6",
        "max_concurrency": 4,
    },
}


def _resolve_interval(raw) -> dict[str, int]:
    """采样间隔归一化为 {context: seconds}。

    兼容两种写法：单一整数（两个 context 都用它）或 {litter_box, feeder} 表。
    """
    default = {"litter_box": 12, "feeder": 12}
    if isinstance(raw, dict):
        out = dict(default)
        out["litter_box"] = int(raw.get("litter_box", default["litter_box"]))
        out["feeder"] = int(raw.get("feeder", default["feeder"]))
        return out
    if isinstance(raw, (int, float)):
        n = int(raw)
        return {"litter_box": n, "feeder": n}
    return default


def _resolve_min_frames(raw) -> dict[str, int]:
    """min_frames 归一化为 {context: n}，兼容单一整数或表。"""
    default = {"litter_box": 1, "feeder": 2}
    if isinstance(raw, dict):
        out = dict(default)
        out["litter_box"] = int(raw.get("litter_box", default["litter_box"]))
        out["feeder"] = int(raw.get("feeder", default["feeder"]))
        return out
    if isinstance(raw, (int, float)):
        n = int(raw)
        return {"litter_box": n, "feeder": n}
    return default


@dataclass
class Config:
    litter_box_dir: Path = Path()
    feeder_dir: Path = Path()
    reports_dir: Path = Path.home() / "Documents" / "cat-reports"
    timezone: str = "Asia/Shanghai"
    # 采样间隔：按 context 分段（猫砂盆 6s 救快速进出，喂食机 12s）
    frame_interval_seconds: dict = field(default_factory=lambda: {"litter_box": 6, "feeder": 12})
    event_merge_gap_seconds: int = 30
    dedup_enabled: bool = True
    dedup_hamming_threshold: int = 5
    frame_max_side: int = 768            # 代表帧长边上限，降采样省 token
    min_frames: dict = field(default_factory=lambda: {"litter_box": 1, "feeder": 2})
    motion_threshold: float = 2.0        # 预筛运动检测阈值
    model_provider: str = "anthropic"
    model_name: str = "claude-sonnet-4-6"
    max_concurrency: int = 4
    raw: dict = field(default_factory=dict)

    def interval_for(self, context: str) -> int:
        """取某 context 的采样间隔（秒）。未知 context 回退 feeder。"""
        return int(self.frame_interval_seconds.get(context, self.frame_interval_seconds.get("feeder", 12)))

    def min_frames_for(self, context: str) -> int:
        """取某 context 的最短帧数。未知 context 回退 feeder。"""
        return int(self.min_frames.get(context, self.min_frames.get("feeder", 2)))


def config_dir() -> Path:
    env = os.environ.get("CAT_VIDEO_ANALYZER_CONFIG_DIR")
    if env:
        return Path(env)
    if sys.platform == "win32":
        base = os.environ.get("APPDATA") or str(Path.home())
        return Path(base) / "cat-video-analyzer"
    return Path.home() / ".config" / "cat-video-analyzer"


def config_path() -> Path:
    env = os.environ.get("CAT_VIDEO_ANALYZER_CONFIG")
    if env:
        return Path(env)
    return config_dir() / "config.toml"


def _deep_merge(base: dict, override: dict) -> dict:
    out = dict(base)
    for k, v in override.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def _load_toml(path: Path) -> dict:
    if not path.exists():
        return {}
    if tomllib is not None:
        with path.open("rb") as f:
            return tomllib.load(f)
    # 极简 fallback：只支持 key = "value" / 数字 / bool，够配置用。
    # 支持 dotted key（如 frame_interval_seconds.litter_box = 6）→ 嵌套 dict。
    parsed: dict = {}
    section = parsed
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.split("#", 1)[0].strip()
        if not line:
            continue
        if line.startswith("[") and line.endswith("]"):
            name = line[1:-1].strip()
            section = parsed.setdefault(name, {})
            continue
        if "=" not in line:
            continue
        k, v = line.split("=", 1)
        k, v = k.strip(), v.strip()
        if v.startswith('"') and v.endswith('"'):
            val: object = v[1:-1]
        elif v.lower() in ("true", "false"):
            val = v.lower() == "true"
        else:
            try:
                val = int(v)
            except ValueError:
                val = float(v) if "." in v else v
        # dotted key → 嵌套 dict（a.b.c = v → {a: {b: {c: v}}}）
        if "." in k:
            parts = k.split(".")
            node = section
            for p in parts[:-1]:
                node = node.setdefault(p, {})
            node[parts[-1]] = val
        else:
            section[k] = val
    return parsed


def ensure_default_config() -> Path:
    """首次运行：写一份带注释的默认配置，方便用户填写。"""
    path = config_path()
    if path.exists():
        return path
    path.parent.mkdir(parents=True, exist_ok=True)
    template = """# cat-video-analyzer 配置
# 路径跨平台：macOS/WSL 用 /，Windows 用 \\ 或 /（pathlib 都能识别）

[nas]
# 猫砂盆摄像头视频目录
litter_box = ""
# 喂食机摄像头视频目录
feeder = ""

[output]
reports_dir = ""
timezone = "Asia/Shanghai"

[processing]
# 采样间隔（秒）：可写单一整数，也可按场景分段。
# 分段：猫砂盆收 6s 救黑猫 <24s 快速进出，喂食机保持 12s（吃饭是长活动）。
frame_interval_seconds.litter_box = 6
frame_interval_seconds.feeder     = 12
event_merge_gap_seconds = 30
# 代表帧长边像素上限（ffmpeg scale 降采样）。0 = 不降采样。
# 768 在 1 tile 内、单帧 token 比 1080p 省 ~6x，且不丢识别细节。
frame_max_side = 768
# 事件最短帧数（按场景分段）：单帧活动少于则丢弃。
# 猫砂盆 = 1（快速进出兜底），喂食机 = 2（过滤单帧误判）。
min_frames.litter_box = 1
min_frames.feeder     = 2
# 预筛运动检测阈值：32x32 灰度相邻帧平均像素差 > 此值判定「有运动」。
# 太小会把光照噪声判成运动，太大漏掉轻微活动。首跑后按 skipped_silent 占比调。
motion_threshold = 2.0
# 帧去重：相邻相似帧合并，只识别代表帧，省 token（需 pip install pillow；缺失时自动降级）
dedup_enabled = true
# dHash 汉明距离阈值：相邻帧差异 ≤ 此值则合并。越小越严格（默认 5）

[model]
provider = "anthropic"
name = "claude-sonnet-4-6"
max_concurrency = 4
"""
    path.write_text(template, encoding="utf-8")
    return path


def load() -> Config:
    ensure_default_config()
    file_data = _load_toml(config_path())
    merged = _deep_merge(DEFAULT_CONFIG, file_data)

    nas = merged.get("nas", {})
    output = merged.get("output", {})
    proc = merged.get("processing", {})
    model = merged.get("model", {})

    # 环境变量覆盖（便于 cron/CI 注入，不必改文件）
    litter_box = os.environ.get("CAT_NAS_LITTER_BOX", nas.get("litter_box", ""))
    feeder = os.environ.get("CAT_NAS_FEEDER", nas.get("feeder", ""))
    reports_dir = os.environ.get("CAT_REPORTS_DIR", output.get("reports_dir", ""))

    return Config(
        litter_box_dir=Path(litter_box) if litter_box else Path(),
        feeder_dir=Path(feeder) if feeder else Path(),
        reports_dir=Path(reports_dir) if reports_dir else Path.home() / "Documents" / "cat-reports",
        timezone=output.get("timezone", "Asia/Shanghai"),
        frame_interval_seconds=_resolve_interval(proc.get("frame_interval_seconds", DEFAULT_CONFIG["processing"]["frame_interval_seconds"])),
        event_merge_gap_seconds=int(proc.get("event_merge_gap_seconds", 30)),
        dedup_enabled=bool(proc.get("dedup_enabled", True)),
        dedup_hamming_threshold=int(proc.get("dedup_hamming_threshold", 5)),
        frame_max_side=int(proc.get("frame_max_side", 768)),
        min_frames=_resolve_min_frames(proc.get("min_frames", DEFAULT_CONFIG["processing"]["min_frames"])),
        motion_threshold=float(proc.get("motion_threshold", 2.0)),
        model_provider=model.get("provider", "anthropic"),
        model_name=model.get("name", "claude-sonnet-4-6"),
        max_concurrency=int(model.get("max_concurrency", 4)),
        raw=merged,
    )


def validate(cfg: Config) -> list[str]:
    """返回错误信息列表；空列表表示配置可用。"""
    errs: list[str] = []
    # Path("") 与 Path(".") 相等且都解析到当前目录，单靠 exists() 无法区分"未配置"，
    # 故先按路径字符串判空，再检查目录是否存在。
    if str(cfg.litter_box_dir) == ".":
        errs.append("猫砂盆视频目录未配置：请在 config.toml 的 [nas] 段填写 litter_box")
    elif not cfg.litter_box_dir.exists():
        errs.append(f"猫砂盆视频目录不存在: {cfg.litter_box_dir}")
    if str(cfg.feeder_dir) == ".":
        errs.append("喂食机视频目录未配置：请在 config.toml 的 [nas] 段填写 feeder")
    elif not cfg.feeder_dir.exists():
        errs.append(f"喂食机视频目录不存在: {cfg.feeder_dir}")
    for ctx in ("litter_box", "feeder"):
        n = cfg.interval_for(ctx)
        if n < 1:
            errs.append(f"frame_interval_seconds.{ctx} 必须 ≥ 1，当前 {n}")
    if cfg.frame_max_side < 0:
        errs.append(f"frame_max_side 必须 ≥ 0（0 表示不降采样），当前 {cfg.frame_max_side}")
    return errs


if __name__ == "__main__":
    cfg = load()
    print(f"配置文件: {config_path()}")
    print(f"猫砂盆目录: {cfg.litter_box_dir}")
    print(f"喂食机目录: {cfg.feeder_dir}")
    print(f"报告目录:   {cfg.reports_dir}")
    print(f"时区:       {cfg.timezone}")
    for e in validate(cfg):
        print(f"⚠️  {e}")
