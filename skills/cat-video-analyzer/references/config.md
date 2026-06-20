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

## 配置文件模板

首次运行会自动生成（带注释）：

```toml
[nas]
litter_box = ""       # 猫砂盆摄像头视频目录（绝对路径）
feeder     = ""       # 喂食机摄像头视频目录（绝对路径）

[output]
reports_dir = ""      # 日报输出目录，留空则 ~/Documents/cat-reports
timezone    = "Asia/Shanghai"

[processing]
# 采样间隔（秒）：可写单一整数，也可按场景分段（见下）
frame_interval_seconds.litter_box = 6   # 猫砂盆：救黑猫 <24s 快速进出
frame_interval_seconds.feeder     = 12  # 喂食机：吃饭是长活动，12s 足够
event_merge_gap_seconds = 30   # 同类事件间隔小于此值则合并

# 代表帧长边像素上限（ffmpeg scale 降采样）。0 = 不降采样。
# 768 在 1 tile 内、单帧 token 比 1080p 省 ~6x，且不丢识别细节。
frame_max_side = 768

# 事件最短帧数（按场景分段）：单帧活动少于则丢弃
min_frames.litter_box = 1   # 猫砂盆：单帧 toileting 也记（快速进出兜底）
min_frames.feeder     = 2   # 喂食机：要求连续 2 帧过滤误判

# 预筛运动检测阈值：32×32 灰度相邻帧平均像素差 > 此值判定「有运动」
# 太小把光照噪声判成运动，太大漏轻微活动。首跑后按 skipped_silent 占比调
motion_threshold = 2.0

# 帧去重：相邻相似帧合并，只识别代表帧（需 pip install pillow；缺失时降级）
dedup_enabled = true
dedup_hamming_threshold = 5  # dHash 汉明距离 ≤ 此值则合并，越小越严格

[model]
provider = "anthropic"
name = "claude-sonnet-4-6"
max_concurrency = 4
```

## 向后兼容

`frame_interval_seconds` 和 `min_frames` 都支持两种写法：

- **单一整数**（老配置）：两个 context 都用它。如 `frame_interval_seconds = 12`。
- **分段表**（新写法）：按场景独立设置。如 `frame_interval_seconds.litter_box = 6`。

读到单一整数时自动展开为两个 context 同值，老配置无需修改即可升级。

## dotted key 写法

配置用 TOML 的 dotted key（`a.b = v`）表达分段表。本 skill 自带的 3.10 fallback
解析器也支持这种写法（解析为嵌套 dict）；3.11+ 用标准库 tomllib。

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
| `frame_interval_seconds.litter_box` | 漏短活动、省钱 | 更准、更贵 | 6（救快速进出） |
| `frame_interval_seconds.feeder` | 漏短活动、省钱 | 更准、更贵 | 12 |
| `event_merge_gap_seconds` | 把独立事件误并为一次 | 把一次事件拆成多次 | 30 |
| `frame_max_side` | 每帧更贵，细节更清 | 省 token，细节可能模糊 | 768 |
| `motion_threshold` | 漏轻微活动（多送模型） | 光照噪声误判为运动 | 2.0（按占比调） |
| `min_frames.litter_box` | 漏单帧快速进出 | 单帧误判混入 | 1 |
| `min_frames.feeder` | 过滤更多误判 | 漏短吃饭 | 2 |

## 模型选择

`name` 可填任何支持视觉的 Claude 模型（识别由 agent 自身完成，此处仅作记录/调度用）：

- `claude-sonnet-4-6`：性价比首选，视觉够用（默认）
- `claude-opus-4-8`：夜视/模糊画面下更准，成本约 5×

换其他厂商模型：在 `scripts/recognize.py` 的 `recognize()` 加一个 `elif` 分支。
