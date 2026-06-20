---
name: cat-video-analyzer
description: 定时或手动分析小米摄像头录制到 NAS 上的猫咪视频，识别狸花猫和黑猫在猫砂盆与喂食机区域的行为（吃饭、上厕所），按日输出 Markdown 报告。**只要用户提到"分析猫咪视频"、"分析猫砂盆/喂食机视频"、"猫粮统计"、"上厕所统计"、"猫的日报/周报"，或希望处理 NAS/小米摄像头中已录制的猫咪监控视频，就应该触发本 skill**，即便用户没有显式说出 skill 名称。已处理的视频会被状态文件记录，绝不重复识别。
---

# cat-video-analyzer

## 这是什么

一个分析猫咪监控视频的 skill。视频来自小米摄像头（一个拍猫砂盆、一个拍喂食机，
每段约 1 分钟），存放在 NAS 上。最终按天输出一份 Markdown 报告，统计每只猫
（**狸花猫 tabby** / **黑猫 black**）吃饭和上厕所的次数与时长。

## 你（agent）的角色

本 skill 的**执行者是你**。脚本只做确定性工作（扫描、抽帧、去重、聚合、报告）；
**逐帧识别由你的多模态能力完成**——你本来就能看图。所以流程中间有一步需要你
介入：读图、判断、把结构化结果回传给脚本。

这样的好处是 skill 不绑死任何模型 API，能在 Claude Code、OpenCode、Codex 等
任何"能读图 + 能跑 bash"的 agent 上工作。

## 调用约定

本 skill 随 `philosophy` 插件分发。所有子命令通过 Python 入口 `catva.py` 调用；
`${CLAUDE_PLUGIN_ROOT}` 会被 Claude Code 自动替换为插件安装目录的绝对路径：

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/skills/cat-video-analyzer/scripts/catva.py" <子命令> [...]
```

> 下文为简洁起见，用 **`CATVA`** 代表上面这整条命令（即
> `python3 "${CLAUDE_PLUGIN_ROOT}/skills/cat-video-analyzer/scripts/catva.py"`）。
> 本 skill 的参考文档位于 `${CLAUDE_PLUGIN_ROOT}/skills/cat-video-analyzer/references/`。

所有子命令通过 stdout 输出 JSON，方便你解析。

> 命令示例统一用 `python3`（Windows / Linux / macOS 通用）。Windows 上若
> `python3` 命令不存在（python.org 安装默认只提供 `python`），改用 `python` 即可。

## 环境检查（首次使用 / 换机器时先跑一次）

```bash
CATVA doctor
```

输出 JSON，逐项报告 `python` / `ffmpeg` / `config` / `pillow`（可选）的就绪状态：

- **ffmpeg 缺失** → 返回 `install_hint`（macOS `brew install ffmpeg` / Linux `apt install ffmpeg` / Windows `winget install Gyan.FFmpeg`）。系统级依赖，需手动装。
- **pillow 缺失**（可选）→ 返回 `pip install pillow`。装了才启用**帧去重**（省 40-70% 识别 token）；不装也能用，`extract` 自动降级为不去重。
- **config 未填** → 编辑返回的 `config.path`，填入 NAS 上猫砂盆与喂食机两个视频目录。

`doctor` 全部 `ok`（ffmpeg/config 就绪）才适合进入下面的工作流（退出码 0 = 就绪，1 = 有缺失）。pillow 是可选项，不影响退出码。

## 工作流（分 6 步）

> 连续录像下 token 优化靠四个杠杆咬合：**预筛**（砍无运动段，~2880→~300 段/天）、
> **降采样**（每帧长边 ≤768，单帧 token ÷6）、**采样间隔分段**（猫砂盆 6s 救黑猫快速进出）、
> **段内去重**（相邻相似帧合并）。单帧 token ≈ 宽×高/750，从原始 ~777 万 token/天 压到 ~40 万。
> 详见 `references/workflow.md`。

### 第 1 步：扫描当天待处理文件

```bash
CATVA scan --date 2026-06-11
```

输出 JSON：`todo` 是当天、且**尚未处理**的视频清单（已自动去重），每项含
`path` 和 `context`（`litter_box` / `feeder`）。`skipped` 是已处理被跳过的数量。

> 增量去重是自动的：`state.json` 按 `路径+mtime+大小` 记指纹。cron 每次跑只会
> 拿到新增/变化的文件，绝不会重复识别。详见 `references/workflow.md`。

如果 `todo` 为空且 `skipped > 0`，说明当天都处理过了，可直接跳到第 6 步出报告。

### 第 2 步：运动检测预筛（砍掉无运动段）

```bash
CATVA prefilter --date 2026-06-11
```

对 `todo` 里每个视频抽 3 帧（首/中/尾）缩到 32×32 灰度，算**相邻帧**像素差。
差值 > `motion_threshold` → 有运动，进 `motion_videos` 清单；否则标记 `silent`
（不写 jsonl，但要标记，否则下次 scan 重列、预筛白跑）。典型连续录像下
**静默跳过 85%+ 的段**——这是省 token 的最大杠杆。

调了阈值想复检上轮 silent 段？`CATVA prefilter --date D --recheck-silent` 只重判
silent 段，不动已识别的运动段。

> 预筛需 Pillow（`pip install pillow`）。连续录像场景下预筛是必需步骤，缺失时
> `prefilter` 直接报错（不静默降级）。

### 第 3 步：抽帧 + 降采样 + 去重（输出代表帧）

单个视频：

```bash
CATVA extract \
  --video /path/to/clip.mp4 \
  --context litter_box
```

或一次并行处理当天所有有运动视频（更快）：

```bash
CATVA batch-extract --date 2026-06-11
```

抽帧间隔**按 context 取**（猫砂盆 6s / 喂食机 12s），同时 ffmpeg `scale` 把代表帧
长边降到 `frame_max_side`（默认 768，单帧 token ÷6）。相邻、画面几乎相同的帧会被
合并（dHash 汉明距离 ≤ 阈值），每组只留一个**代表帧**，附带 `time_range`（覆盖时段）
和 `represents`（代表了几帧）。

> 去重省的是**帧数**，不是每帧 token。在预筛+降采样落地前，dedup 是唯一省 token 的
> 手段，但对连续录像的量级问题杯水车薪——预筛和降采样才是主杠杆。
> 去重需 Pillow；未装时输出全部帧（无 `time_range`），流程不变，只是不省 token。

### 第 4 步：你识别每张代表帧 ⬅️ 核心步骤

对返回的每个代表帧，用你的读图能力打开 `frame_path`（已降采样到 768px，足够识别），
按 **`references/recognition-protocol.md`**（完整路径
`${CLAUDE_PLUGIN_ROOT}/skills/cat-video-analyzer/references/recognition-protocol.md`）判断：

- 画面里有哪只猫（狸花 `tabby` / 黑猫 `black` / `unknown`）
- 在做什么（`eating` / `toileting` / `idle` / `absent`）

把每个代表帧产成一个 JSON 对象，**带 `time_range` 的要原样回传**。**建议一次
打开一个视频的全部代表帧、批量输出 JSON 数组**（省往返）。务必先读
`recognition-protocol.md`——里面有判断规则、路径级硬约束、输出 schema、time_range 回传要求。

### 第 5 步：把识别结果写回

一个视频的代表帧都识别完后：

```bash
CATVA ingest \
  --video /path/to/clip.mp4 \
  --date 2026-06-11 \
  --results '[{"frame_ts":"...","context":"litter_box","cats":[{"identity":"black","confidence":0.9}],"activity":{"type":"toileting","evidence":"..."},"time_range":["...","..."]}, ...]'
```

`--results` 也支持 `@文件路径`。`ingest` 会校验字段、应用路径级硬约束；
**带 `time_range` 的结果会按该 context 的采样间隔自动扩展为整段内的多个时间点**写入
`raw/日期.jsonl`、并把该视频标记为已处理。聚合逻辑无需感知去重。

对 `motion_videos` 里的每个文件重复第 3–5 步（或用 `batch-extract` 一次抽完，再逐个 ingest）。

### 第 6 步：生成报告

```bash
CATVA report --date 2026-06-11
```

聚合当天全部帧（跨视频文件全局聚合，`min_frames` 按 context 取：猫砂盆 1 / 喂食机 2）、
生成 `reports_dir/2026-06-11.md`。报告格式见 `references/report-format.md`。

改了报告格式想重出？直接再跑 `report`，零识别开销。

## 命令速查

下表中 **`CATVA`** = `python3 "${CLAUDE_PLUGIN_ROOT}/skills/cat-video-analyzer/scripts/catva.py"`。

| 命令 | 作用 |
|------|------|
| `CATVA scan --date D [--force]` | 列出日期 D 的待处理视频（已去重） |
| `CATVA prefilter --date D [--recheck-silent]` | 运动检测预筛，砍掉无运动段，输出有运动段清单 |
| `CATVA extract --video V --context C` | 抽帧 + 降采样 + 去重，输出代表帧（含 time_range） |
| `CATVA batch-extract --date D` | 并行抽帧 + 降采样 + 去重（当天所有待处理视频） |
| `CATVA ingest --video V --date D --results R` | 写入识别结果（自动按 time_range 扩展）+ 标记已处理 |
| `CATVA report --date D` | 聚合 + 生成 Markdown 报告 |
| `CATVA doctor` | 检查 Python / ffmpeg / 配置 / Pillow 是否就绪 |

## 何时触发

适用：
- "分析今天的猫咪视频 / 猫砂盆视频 / 喂食机视频"
- "统计一下这周猫吃饭 / 上厕所"
- "定时分析 / 增量分析 / 跑一下 cat-video-analyzer"
- "处理 NAS 里的小米摄像头视频"

不适用：
- 实时监控、告警推送（本 skill 是离线批处理）
- 其他动物 / 其他分析目标

## 核心原则

1. **token 由两个正交维度决定**：送多少帧 × 每帧多大。预筛砍段数（最大杠杆）、
   降采样砍每帧 token（6×）、分段采样救黑猫漏检、dHash 去重省帧数——四者咬合。
   单靠去重解决不了连续录像的量级问题。详见 `references/workflow.md`。
2. **绝不重复识别**。`scan` 只返回未处理文件；`ingest` 处理完即标记；预筛的
   `silent` 段也标记。这是定时启用的前提，不能破坏。
3. **预筛不破坏数据**。无运动段静默跳过、不写 jsonl（`absent` 帧本就不参与事件），
   但必须标记 `silent` 避免下次重列。
4. **跨平台**。路径走 `pathlib`，不硬编码挂载点。支持 macOS / Linux / WSL / Windows。
5. **失败可重入**。单个视频任何一步失败，不要标记为已处理，下次 `scan` 会重试。
6. **识别精度优先**。宁可保守（过渡帧算 `idle`），也不要把噪声混进事件——
   聚合阶段有 30 秒间隔容忍，会补回短中断。

## 配置

首次运行自动生成 `~/.config/cat-video-analyzer/config.toml`（Windows 为
`%APPDATA%\cat-video-analyzer\config.toml`）。需填写 `nas.litter_box`、
`nas.feeder` 两个视频目录。关键调优项：

- `processing.frame_interval_seconds.litter_box` / `.feeder`：采样间隔按场景分段
  （猫砂盆 6s 救黑猫快速进出、喂食机 12s）；也支持单一整数写法（向后兼容）
- `processing.frame_max_side`：代表帧长边上限，降采样省 token（默认 768）
- `processing.min_frames.litter_box` / `.feeder`：事件最短帧数按场景分段
- `processing.motion_threshold`：预筛运动检测阈值（默认 2.0，按 silent 占比调）
- `processing.dedup_enabled` / `dedup_hamming_threshold`：段内去重

详见 `references/config.md`。

## 参考文档

均位于 `${CLAUDE_PLUGIN_ROOT}/skills/cat-video-analyzer/references/` 下：

| 文档 | 何时读 |
|------|--------|
| `recognition-protocol.md` | **第 4 步识别前必读** |
| `workflow.md` | 调试某个环节、改流程时 |
| `aggregation-rules.md` | 理解事件怎么合并、调 `merge_gap` |
| `config.md` | 配置参数调优 |
| `report-format.md` | 改报告格式时 |

## 依赖

- Python ≥ 3.10（命令示例用 `python3`；Windows 上 `python` 亦可）
- `ffmpeg`（系统级，PATH 中可用；脚本会自动探测常见安装位置，含 Windows）
- `Pillow`（`pip install pillow`；连续录像场景下为**必需**——预筛依赖它砍无运动段，
  未装时 `prefilter` 直接报错；去重也依赖它，未装时降级为不去重）
- agent 自身的多模态读图能力（无需任何模型 API key）

所有入口均为 Python，**Windows / Linux / macOS 原生可用，无需 bash**。
