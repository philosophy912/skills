# 配置说明

配置文件位置（按平台自动选择，可用环境变量覆盖）：

| 平台 | 默认路径 |
|------|----------|
| macOS / Linux / WSL | `~/.config/cat-video-analyzer/config.toml` |
| Windows | `%APPDATA%\cat-video-analyzer\config.toml` |

覆盖用的环境变量：
- `CAT_VIDEO_ANALYZER_CONFIG`：直接指定配置文件完整路径
- `CAT_VIDEO_ANALYZER_CONFIG_DIR`：指定配置**目录**
- `CAT_NAS_LITTER_BOX` / `CAT_NAS_FEEDER`：视频目录（优先级高于配置文件）
- `CAT_REPORTS_DIR`：报告输出目录
- `ANTHROPIC_API_KEY`：多模态模型 API key（**不要**写进配置文件）

## 配置文件模板

首次运行 `python -m scripts.config` 会自动生成：

```toml
[nas]
litter_box = ""       # 猫砂盆摄像头视频目录（绝对路径）
feeder     = ""       # 喂食机摄像头视频目录（绝对路径）

[output]
reports_dir = ""      # 日报输出目录，留空则 ~/Documents/cat-reports
timezone    = "Asia/Shanghai"

[processing]
frame_interval_seconds = 12    # 每 N 秒抽一帧；越小越准越贵
event_merge_gap_seconds = 30   # 同类事件间隔小于此值则合并

[model]
provider = "anthropic"
name = "claude-sonnet-4-6"
max_concurrency = 4
```

## 路径写法（跨平台）

`pathlib` 同时接受 `/` 和 `\`，所以 Windows 上写正斜杠也行：

```toml
# macOS / WSL
litter_box = "/Volumes/nas/xiaomi/litter_box"
feeder = "/mnt/nas/xiaomi/feeder"

# Windows
litter_box = "Z:/xiaomi/litter_box"
feeder = "\\\\nas\\xiaomi\\feeder"
```

## 各参数调优建议

| 参数 | 调大的影响 | 调小的影响 | 推荐起点 |
|------|-----------|-----------|----------|
| `frame_interval_seconds` | 漏掉短事件、省钱 | 更准、更贵 | 12（1 分钟 5 帧） |
| `event_merge_gap_seconds` | 把独立事件误并为一次 | 把一次事件拆成多次 | 30 |
| `max_concurrency` | API 限流风险 | 慢 | 4（按你的 API 配额调） |

## 模型选择

目前只实现 `anthropic` provider。`name` 可填任何支持视觉的 Claude 模型：

- `claude-sonnet-4-6`：性价比首选，视觉够用（默认）
- `claude-opus-4-8`：夜视/模糊画面下更准，成本约 5×

换其他厂商模型：在 `scripts/recognize.py` 的 `recognize()` 加一个 `elif` 分支。
