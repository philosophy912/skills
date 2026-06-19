# philosophy

一个 [Claude Code](https://code.claude.com) 插件，打包了两个个人 skill。

| Skill | 作用 |
|-------|------|
| **cat-video-analyzer** | 离线批处理小米摄像头录到 NAS 的猫咪监控视频，识别狸花猫 / 黑猫在猫砂盆与喂食机区域的行为（吃饭、上厕所），按日输出 Markdown 报告 |
| **wikipedia_restapi** | 通过 Wikimedia 官方 REST API 访问维基百科：条目摘要、全文搜索、页面 HTML、修订历史、数学公式检查、媒体列表等（覆盖 145 个 endpoint） |

## 安装

本仓库本身就是一个 Claude Code 插件市场（marketplace），可以直接安装，无需手动克隆或软链。

### 方式一：从 marketplace 安装（推荐）

在 Claude Code 交互式会话中：

```
/plugin marketplace add philosophy912/skills
/plugin install philosophy@philosophy-skills
```

或用 CLI：

```bash
claude plugin marketplace add philosophy912/skills
claude plugin install philosophy@philosophy-skills
```

安装后插件默认启用，两个 skill 自动可用。

之后发布新版本，更新方式：

```
/plugin marketplace update philosophy-skills
/plugin update philosophy
```

### 方式二：本地开发（skills-directory 插件）

适合在本仓库上直接迭代——把仓库软链到 skills 目录，以 `philosophy@skills-dir` 就地加载，改动 `SKILL.md` 即时生效，无需 install：

```bash
ln -s "$(pwd)" ~/.claude/skills/philosophy
```

## 依赖

- **Python ≥ 3.10**（两个 skill 均需）
- **ffmpeg**：仅 cat-video-analyzer 抽帧需要，须在 `PATH` 中（脚本会自动探测常见安装位置）
- **curl**：wikipedia_restapi 需要，几乎所有系统自带
- 两个 skill 均通过 Claude 自身的多模态能力 / 网络访问工作，**无需额外 API key**

## 目录结构

```
philosophy/
├── .claude-plugin/
│   ├── plugin.json          # 插件 manifest
│   └── marketplace.json     # 自托管市场（本仓库既是插件也是市场）
└── skills/
    ├── cat-video-analyzer/
    │   ├── SKILL.md
    │   ├── references/
    │   ├── scripts/         # run.py + catva 包装器 + 各子模块
    │   └── evals/
    └── wikipedia_restapi/
        ├── SKILL.md
        ├── references/
        └── scripts/         # wikipedia_api.sh + setup_config.sh
```

## 各 skill 配置

- **cat-video-analyzer**：首次运行自动生成 `~/.config/cat-video-analyzer/config.toml`
  （Windows 为 `%APPDATA%\cat-video-analyzer\config.toml`），需填入 NAS 上猫砂盆与
  喂食机两个视频目录。报告默认输出到 `~/Documents/cat-reports/`。
- **wikipedia_restapi**：运行 `setup_config.sh` 生成 `~/.wikipedia_restapi.json`，
  配置 HTTP 代理和默认语言（en / zh / ja …）。也可用环境变量 `WIKI_PROXY` /
  `WIKI_LANG` 临时覆盖。

## 许可证

MIT，详见 [LICENSE](LICENSE)。
