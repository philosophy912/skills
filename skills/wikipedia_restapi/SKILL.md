---
name: wikipedia_restapi
description: 通过 Wikipedia / Wikimedia REST API 查询条目、搜索、算公式、读页面 HTML、读数学公式。覆盖 Special:RestSandbox 中 6 个 API 集合（145 个 endpoint），统一通过 `scripts/wikipedia_api.py` 调用（Python 跨平台版，实际请求委托 curl），代理和语言通过 `~/.wikipedia_restapi.json` 配置文件管理（首次运行 `setup_config.py` 引导式生成）。当用户要查维基百科、搜条目、读页面摘要 / HTML、读 / 检查 LaTeX 公式、查 OpenSearch 描述、查站点 / 条目 attribution 信息时使用此 skill。
---

# wikipedia_restapi

通过 Wikimedia 官方 REST API 访问维基百科内容。所有调用统一走 `scripts/wikipedia_api.py`（纯 Python 做 endpoint 解析与 URL 构造，实际请求委托 curl）。

## 调用约定

本 skill 随 `philosophy` 插件分发。`${CLAUDE_PLUGIN_ROOT}` 会被 Claude Code
自动替换为插件安装目录的绝对路径，主入口脚本完整路径为：

```
${CLAUDE_PLUGIN_ROOT}/skills/wikipedia_restapi/scripts/wikipedia_api.py
```

> 下文为简洁起见，用 **`WIKI`** 代表
> `python3 "${CLAUDE_PLUGIN_ROOT}/skills/wikipedia_restapi/scripts/wikipedia_api.py"`。
> 参考文档位于 `${CLAUDE_PLUGIN_ROOT}/skills/wikipedia_restapi/references/`。
>
> 命令示例统一用 `python3`（Windows / Linux / macOS 通用）。Windows 上若
> `python3` 命令不存在（python.org 安装默认只提供 `python`），改用 `python` 即可。

## 这个 skill 能做什么

| 能力 | 说明 |
|------|------|
| 📄 **查条目摘要** | 获取页面标题、首段、封面图、wikibase ID 等结构化元数据 |
| 🌐 **拉完整 HTML** | 桌面版 / 移动版完整 HTML，可离线保存 |
| 📝 **查修订历史 & 元数据** | 某页面的全部修订记录、时间戳、编辑者、delta |
| 🔍 **搜索条目 & 标题补全** | 全文搜索（关键词 + 摘要）+ 标题自动补全 |
| 🧮 **查 / 检查数学公式** | LaTeX 公式合法性检查 + 渲染 SVG/PNG |
| 🖼️ **查页面媒体列表** | 列出页面中引用的所有图片 / 文件 |
| 🔧 **查 Lint 错误** | 获取 wikitext 的 Linter 错误 |
| 💬 **查讨论页** | 获取结构化的 Talk 页面内容 |
| ↔️ **Wikitext ↔ HTML 互转** | 向服务器提交 wikitext/HTML 做双向转换 |
| 📎 **查词条 / 站点归属** | 获取 Attribution 信号、品牌 logo、引用链接 |
| 🔌 **OpenSearch 描述** | 获取 OpenSearch XML，供搜索引擎集成 |
| 🌱 **Growth 实验 API** | 新手任务建议、链接建议、用户影响力数据 |

**支持多语言**：通过配置文件切换 Wikipedia 语言（en / zh / ja / fr / de … 300+）。

## 配置（引导式）

首次使用请运行引导脚本：

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/skills/wikipedia_restapi/scripts/setup_config.py"
```

它会交互式询问两项配置并写入 `~/.wikipedia_restapi.json`：

```json
{
  "proxy": "http://127.0.0.1:16780",
  "lang": "en"
}
```

| 字段 | 含义 | 默认值 |
|------|------|--------|
| `proxy` | HTTP 代理地址 | `http://127.0.0.1:16780` |
| `lang` | 默认 Wikipedia 语言 | `en` |

环境变量 `WIKI_PROXY` / `WIKI_LANG` 可临时覆盖（优先级高于配置文件）。不想写文件时，环境变量足够。

## 调用格式

```
WIKI <api> <method> <endpoint-name> [path-args...] [-- [curl-args...]]
```

- `<api>` 取 6 个之一（见下表）
- `<method>` 大写：`GET / POST / PUT / DELETE / PATCH`
- `<endpoint-name>` 短名（见 `references/endpoints.md` 或 `wikipedia_api.py` 内 `ENDPOINTS` 表）
- `path-args...` 按 endpoint 模板里的 `{param}` 顺序传入
- `--` 之后所有参数原样转发给 curl（`-d` `-H` `--data-urlencode -G` 等都可）

## 6 个 API 集合

| API key | 名称 | Language-aware | 端点数 |
|---------|------|:---:|-------|
| `wmf-restbase` | Wikimedia REST API（页面、阅读列表、推荐、Transform） | ✅ | 49 |
| `wmf-restbase-global` | Math API（wikimedia.org，跨语种） | ❌ | 3 |
| `mw-extra` | MediaWiki REST API（OAuth、CheckUser、CampaignEvents、Page v1、Search） | ✅ | 78 |
| `growthexperiments.v0` | Growth experiments API（新手任务、User impact、Suggestions） | ✅ | 10 |
| `specs.v0` | Specs API（自描述 / Discovery） | ✅ | 3 |
| `attribution.v0-beta` | Attribution API（页面与站点归属） | ✅ | 2 |

合计 **145 个 endpoint**。完整方法 / 路径 / 摘要表见 `references/endpoints.md`。

## 高频用法示例

```bash
# 1) 查 Berlin 摘要
WIKI wmf-restbase GET page-summary "Berlin"

# 2) 拉 Tokyo 页面 HTML
WIKI wmf-restbase GET page-html "Tokyo" > tokyo.html

# 3) 查 Albert Einstein 修订元数据
WIKI wmf-restbase GET page-title "Albert_Einstein"

# 4) 用中文 Wikipedia 查 北京
WIKI_LANG=zh WIKI wmf-restbase GET page-summary "北京"

# 5) 搜索条目（空格用 --data-urlencode）
WIKI mw-extra GET search-page \
  -- --data-urlencode "q=Albert Einstein" --data-urlencode "limit=3" -G

# 6) 检查 LaTeX 公式 E=mc² 是否合法
WIKI wmf-restbase-global POST math-check tex \
  -- -H "Content-Type: application/json" -d '{"q":"E=mc^2"}'

# 7) 列出所有可用的 REST 模块
WIKI specs.v0 GET discovery | python3 -m json.tool

# 8) 查站点 attribution 信号
WIKI attribution.v0-beta GET site-signals

# 9) 查 Berlin 页面的 attribution
WIKI attribution.v0-beta GET page-signals "Berlin"

# 10) 拉 OpenSearch 描述 XML
WIKI mw-extra GET opensearch
```

## URL 编码 & 引号

- **path 参数里的空格**必须编码（`%20` 或 `_`），否则 curl 会拒绝。Wikipedia 允许用 `_` 代替空格（`Albert_Einstein`）。
- **query 参数里的空格**用 `--data-urlencode "key=value" -G` 编码。
- **JSON body** 用 `-H "Content-Type: application/json" -d '{...}'`。
- POST 请求中的 `--` 分隔很重要：让脚本知道 path args 在哪结束、curl 参数从哪开始。

## HTTP 状态码约定

脚本会输出一行 `[HTTP <code>  size=<bytes>B  time=<sec>s]` 收尾。
- `200` 成功
- `301/302` 重定向（curl 默认跟随）
- `400` 参数错误（看返回 JSON 的 `errorKey`）
- `401/403` 需要登录（OAuth / Cookies / Session），本 skill 不处理鉴权
- `404` 条目不存在或 hash 错误
- `429` 限流（Wikipedia 限制 200 req/s，加 `sleep` 或换 UA）

## 鉴权相关端点

以下 endpoint 需要认证，**本 skill 仅做无认证 GET / POST 演示**，实际写操作请走标准 OAuth 2 流程：

- `mw-extra /oauth2/*`（access_token、client、resource、authorize）
- `mw-extra /v1/page`（POST 创建）、`/v1/page/{title}`（PUT 更新）— 需要 `MediaWiki-API-Token` CSRF
- `mw-extra /checkuser/*`、`/campaignevents/*` — 需要相应用户权限
- `wmf-restbase /data/lists/*`（Reading lists）— 需要登录 Cookie
- `growthexperiments.v0 /mentees`、`/newcomertask/*`、`/user-impact/*` — 需要登录

## 资源

- `scripts/wikipedia_api.py` — 主入口脚本（145 个 endpoint，Python 跨平台版，实际请求委托 curl）
- `scripts/setup_config.py` — 引导式配置生成器（一次运行，写入 `~/.wikipedia_restapi.json`）
- `references/endpoints.md` — 完整 endpoint 表（方法 / 路径 / 摘要）

## 注意事项

- 本地代理（`~/.wikipedia_restapi.json` 中 proxy 指向的服务）必须已启动，否则所有请求会失败。
- User-Agent **必须**设置（Wikipedia 公共 API 强制要求），脚本默认带 `wikipedia-restapi-skill/1.0`。
- 严格遵守 200 req/s 限流；本 skill 默认每次调用即一次请求，无循环刷。
- 输出默认走 stdout，二进制（SVG / PNG）请重定向到文件。
- 所有入口均为 Python，**Windows / Linux / macOS 原生可用，无需 bash**（curl 三端自带）。

## 更新 API 列表

如果 Wikipedia 后续新增/弃用 endpoint：

1. 重新抓 spec：访问 `https://<lang>.wikipedia.org/wiki/Special:RestSandbox` 取新 `specUrl`。
2. 更新 `scripts/wikipedia_api.py` 中 `ENDPOINTS` 字典。
3. 重新生成 `references/endpoints.md`（用类似 `python3 -c "import json; ..."` 的脚本遍历 spec `paths`）。
