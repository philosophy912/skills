# 工作流详解

本文是对 `SKILL.md` 工作流的展开。调试某个环节或修改流程时读这里。

## 端到端流程（agent 驱动）

流程不是"一键脚本"——中间的识别步骤必须由 agent 介入。脚本和 agent 各司其职：

```
 agent                               scripts
   │                                   │
   ├─ run scan --date D ─────────────► │ 扫描 + 增量去重
   │ ◄────── todo 清单 (JSON) ─────── │
   │                                   │
   │  对 todo 里每个 video:            │
   │   ├─ run extract --video V ─────► │ ffmpeg 抽帧
   │   │ ◄── 帧路径 + 时间戳 ───────── │
   │   │                                │
   │   ├─ 读图 + 识别（agent 自身）     │  ← 不调脚本，不调 API
   │   │   （按 recognition-protocol）  │
   │   │                                │
   │   └─ run ingest --results ... ──► │ 校验 + 写 jsonl + 标记已处理
   │     ◄── 确认 ──────────────────── │
   │                                   │
   └─ run report --date D ───────────► │ 全局聚合 + 生成 Markdown
     ◄── 报告路径 ──────────────────── │
```

## 各步骤细节

### scan（`run scan`）
- 递归扫描 `nas.litter_box` / `nas.feeder`。
- 从**文件名**解析时间戳（支持 `20260611_143000`、`2026-06-11_14-30-00` 等），
  失败回退 mtime；按 `--date` 过滤。
- 读 `state.json` 去重：只返回指纹 `(mtime, size)` 不匹配的文件。
- `--force` 忽略去重，全量重列。

### extract（`run extract`）
- 调 ffmpeg 的 `fps=1/interval` 滤镜均匀抽帧（默认 12s/帧）。
- 每帧的 `frame_ts` = 视频起始时间（文件名/mtime）+ 帧偏移，由脚本算好，
  agent 不用自己算。

### 识别（agent，不涉及脚本）
- agent 用自己的读图能力打开 `frame_path`。
- 按 `references/recognition-protocol.md` 判断猫身份 + 行为。
- 产出 `FrameResult` JSON。

### ingest（`run ingest`）
- 校验每条结果的字段（`schema.validate_frame_result`）。
- 应用**路径级硬约束**：猫砂盆目录的 `eating` → `idle`，喂食机的 `toileting` → `idle`。
- 追加到 `raw/日期.jsonl`。
- `mark_processed`：只有这一步成功，文件才被标记为已处理。

### report（`run report`）
- 读 `raw/日期.jsonl` 里**当天全部帧**（跨视频文件）。
- 全局聚合（见 `aggregation-rules.md`）。
- 生成 `reports_dir/日期.md`。

## 持久化数据布局

```
~/.config/cat-video-analyzer/          (Windows: %APPDATA%\cat-video-analyzer\)
├── config.toml                        用户配置
├── state.json                         已处理文件指纹（增量去重核心）
├── state.json.lock                    文件锁哨兵
└── raw/
    └── 2026-06-11.jsonl               当天所有帧的识别结果（每行一帧 JSON）
```

- `state.json` 只存指纹 → 体积小，加载快。
- `raw/*.jsonl` 存逐帧结果 → 按日分割，可独立重聚合。
- 两者配合：`scan` 跳过已识别文件，`report` 从 jsonl 重聚合。

## 增量去重原理

为什么用 `(mtime, size)` 而非内容哈希：NAS 上视频多，算 SHA 太慢；
对"同名文件被覆盖"这种场景，mtime+size 已经足够可靠，而内容哈希只在
"文件原地编辑但大小时间不变"时才有优势——监控视频不会发生。

## 失败与重试

| 失败点 | 行为 |
|--------|------|
| extract 失败 | 不标记已处理；下次 `scan` 会重新列入 todo |
| 识别时某帧判断不了 | agent 可对该帧填 `idle`/`unknown`，或整帧不写入 results |
| ingest 校验失败 | 该条被拒（返回 errors），其余正常写入；视频整体仍标记已处理 |
| 状态文件损坏 | 自动备份 `.corrupt-*.json` 并重建空状态 |
| ffmpeg 缺失 | 报错并提示安装方式 |

## 定时触发

本 skill 的执行者是 agent，所以"定时启用"= 定时触发 agent。常见方式：

- **Claude Code**：用 cron / 任务计划调 `claude -p "用 cat-video-analyzer 分析昨天的猫咪视频"`
- **OpenCode / Codex**：各自的非交互/定时模式
- 触发后 agent 读 `SKILL.md`，自动从 `scan` 走到 `report`

因为 `scan` 自带增量去重，即使 cron 重叠或补跑也不会重复识别。
