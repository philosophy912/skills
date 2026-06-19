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
frame_interval_seconds = 12   # 每 N 秒抽一帧
event_merge_gap_seconds = 30  # 同一行为间隔小于此值则合并

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
        "frame_interval_seconds": 12,
        "event_merge_gap_seconds": 30,
    },
    "model": {
        "provider": "anthropic",
        "name": "claude-sonnet-4-6",
        "max_concurrency": 4,
    },
}


@dataclass
class Config:
    litter_box_dir: Path = Path()
    feeder_dir: Path = Path()
    reports_dir: Path = Path.home() / "Documents" / "cat-reports"
    timezone: str = "Asia/Shanghai"
    frame_interval_seconds: int = 12
    event_merge_gap_seconds: int = 30
    model_provider: str = "anthropic"
    model_name: str = "claude-sonnet-4-6"
    max_concurrency: int = 4
    raw: dict = field(default_factory=dict)


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
    # 极简 fallback：只支持 key = "value" / 数字，够配置用
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
            section[k] = v[1:-1]
        elif v.lower() in ("true", "false"):
            section[k] = v.lower() == "true"
        else:
            try:
                section[k] = int(v)
            except ValueError:
                section[k] = float(v) if "." in v else v
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
frame_interval_seconds = 12
event_merge_gap_seconds = 30

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
        frame_interval_seconds=int(proc.get("frame_interval_seconds", 12)),
        event_merge_gap_seconds=int(proc.get("event_merge_gap_seconds", 30)),
        model_provider=model.get("provider", "anthropic"),
        model_name=model.get("name", "claude-sonnet-4-6"),
        max_concurrency=int(model.get("max_concurrency", 4)),
        raw=merged,
    )


def validate(cfg: Config) -> list[str]:
    """返回错误信息列表；空列表表示配置可用。"""
    errs: list[str] = []
    if not cfg.litter_box_dir or not cfg.litter_box_dir.exists():
        errs.append(f"猫砂盆视频目录不存在或未配置: {cfg.litter_box_dir}")
    if not cfg.feeder_dir or not cfg.feeder_dir.exists():
        errs.append(f"喂食机视频目录不存在或未配置: {cfg.feeder_dir}")
    if cfg.frame_interval_seconds < 1:
        errs.append(f"frame_interval_seconds 必须 ≥ 1，当前 {cfg.frame_interval_seconds}")
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
