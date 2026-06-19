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

本 skill 的**执行者是你**。脚本只做确定性工作（扫描、抽帧、聚合、报告、去重）；
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

## 工作流（分 5 步）

### 第 1 步：扫描当天待处理文件

```bash
CATVA scan --date 2026-06-11
```

输出 JSON：`todo` 是当天、且**尚未处理**的视频清单（已自动去重），每项含
`path` 和 `context`（`litter_box` / `feeder`）。`skipped` 是已处理被跳过的数量。

> 增量去重是自动的：`state.json` 按 `路径+mtime+大小` 记指纹。cron 每次跑只会
> 拿到新增/变化的文件，绝不会重复识别。详见 `references/workflow.md`。

如果 `todo` 为空且 `skipped > 0`，说明当天都处理过了，可直接跳到第 5 步出报告。

### 第 2 步：对每个待处理视频抽帧

```bash
CATVA extract \
  --video /path/to/clip.mp4 \
  --context litter_box \
  --date 2026-06-11
```

输出该视频抽出的帧列表，每帧含 `frame_path`（磁盘路径）、`frame_ts`（绝对时间）、
`context`。默认每 12 秒一帧（1 分钟视频约 5 帧），可在配置里调。

### 第 3 步：你识别每帧图片 ⬅️ 核心步骤

对 `extract` 返回的每一帧，用你的读图能力打开 `frame_path`，按
**`references/recognition-protocol.md`**（完整路径
`${CLAUDE_PLUGIN_ROOT}/skills/cat-video-analyzer/references/recognition-protocol.md`）判断：

- 画面里有哪只猫（狸花 `tabby` / 黑猫 `black` / `unknown`）
- 在做什么（`eating` / `toileting` / `idle` / `absent`）

把每帧产成一个 JSON 对象。**务必先读 `recognition-protocol.md`**——里面有判断
规则、路径级硬约束、输出 schema 和常见陷阱。

### 第 4 步：把识别结果写回

一个视频的所有帧识别完后：

```bash
CATVA ingest \
  --video /path/to/clip.mp4 \
  --date 2026-06-11 \
  --results '[{"frame_ts":"...","context":"litter_box","cats":[{"identity":"black","confidence":0.9}],"activity":{"type":"toileting","evidence":"..."}}, ...]'
```

`--results` 也支持 `@文件路径`（帧多时写到临时文件更稳）。`ingest` 会校验字段、
应用路径级硬约束、追加到 `raw/日期.jsonl`、并把该视频标记为已处理。

对 `todo` 里的每个文件重复第 2–4 步。

### 第 5 步：生成报告

```bash
CATVA report --date 2026-06-11
```

聚合当天全部帧（跨视频文件全局聚合）、生成 `reports_dir/2026-06-11.md`。
报告格式见 `references/report-format.md`。

改了报告格式想重出？直接再跑 `report`，零识别开销。

## 命令速查

下表中 **`CATVA`** = `python3 "${CLAUDE_PLUGIN_ROOT}/skills/cat-video-analyzer/scripts/catva.py"`。

| 命令 | 作用 |
|------|------|
| `CATVA scan --date D [--force]` | 列出日期 D 的待处理视频（已去重） |
| `CATVA extract --video V --context C [--date D]` | 抽帧，输出帧路径+时间戳 |
| `CATVA ingest --video V --date D --results R` | 写入识别结果 + 标记已处理 |
| `CATVA report --date D` | 聚合 + 生成 Markdown 报告 |

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

1. **绝不重复识别**。`scan` 只返回未处理文件；`ingest` 处理完即标记。这是用户
   定时启用的前提，不能破坏。
2. **跨平台**。路径走 `pathlib`，不硬编码挂载点。NAS 根目录、报告目录都从
   配置读。支持 macOS / Linux / WSL / Windows。
3. **失败可重入**。单个视频任何一步失败，不要标记为已处理，下次 `scan` 会重试。
4. **识别精度优先**。宁可在识别阶段保守（过渡帧算 `idle`），也不要把噪声混进
   事件——聚合阶段有 30 秒间隔容忍，会补回短中断。

## 配置

首次运行自动生成 `~/.config/cat-video-analyzer/config.toml`（Windows 为
`%APPDATA%\cat-video-analyzer\config.toml`）。需填写 `nas.litter_box`、
`nas.feeder` 两个视频目录。详见 `references/config.md`。

## 参考文档

均位于 `${CLAUDE_PLUGIN_ROOT}/skills/cat-video-analyzer/references/` 下：

| 文档 | 何时读 |
|------|--------|
| `recognition-protocol.md` | **第 3 步识别前必读** |
| `workflow.md` | 调试某个环节、改流程时 |
| `aggregation-rules.md` | 理解事件怎么合并、调 `merge_gap` |
| `config.md` | 配置参数调优 |
| `report-format.md` | 改报告格式时 |

## 依赖

- Python ≥ 3.10（命令示例用 `python3`；Windows 上 `python` 亦可）
- `ffmpeg`（系统级，PATH 中可用；脚本会自动探测常见安装位置，含 Windows）
- agent 自身的多模态读图能力（无需任何模型 API key）

所有入口均为 Python，**Windows / Linux / macOS 原生可用，无需 bash**。
