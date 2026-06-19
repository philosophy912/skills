#!/usr/bin/env python3
"""wikipedia_api.py — 维基百科 REST API 统一入口（跨平台 Python 版）。

原 bash 版（wikipedia_api.sh）依赖 awk/grep/tr 等 Unix 工具，无法在原生
Windows 上运行；本版用纯 Python 做 endpoint 解析与 URL 构造，实际 HTTP
请求仍委托 curl（Windows 10 1803+、macOS、Linux 均自带），从而三端通用。

用法：
    python3 wikipedia_api.py <api> <method> <endpoint-name> [path-args...] [-- [curl-args...]]

示例：
    python3 wikipedia_api.py wmf-restbase GET page-summary "Berlin"
    python3 wikipedia_api.py wmf-restbase GET page-html "Tokyo" > tokyo.html
    python3 wikipedia_api.py mw-extra GET search-page \\
        -- --data-urlencode "q=Albert Einstein" --data-urlencode "limit=3" -G
    python3 wikipedia_api.py wmf-restbase-global POST math-check tex \\
        -- -H "Content-Type: application/json" -d '{"q":"E=mc^2"}'

配置文件 ~/.wikipedia_restapi.json（首次运行用默认值）：
    { "proxy": "http://127.0.0.1:16780", "lang": "en" }

环境变量（覆盖配置文件）：
    WIKI_PROXY   — HTTP 代理
    WIKI_LANG    — 默认语言
    WIKI_HOST_*  — 覆盖特定 API 的 base URL
    WIKI_CONFIG  — 配置文件路径
"""
import json
import os
import re
import subprocess
import sys
from pathlib import Path

CONFIG = os.environ.get("WIKI_CONFIG") or str(Path.home() / ".wikipedia_restapi.json")

DEFAULT_PROXY = "http://127.0.0.1:16780"
DEFAULT_LANG = "en"
DEFAULT_UA = "wikipedia-restapi-skill/1.0 (contact: skill-author)"


def load_config():
    cfg: dict = {}
    if Path(CONFIG).exists():
        try:
            with open(CONFIG, encoding="utf-8") as f:
                cfg = json.load(f)
        except Exception:
            pass
    proxy = os.environ.get("WIKI_PROXY") or cfg.get("proxy") or DEFAULT_PROXY
    lang = os.environ.get("WIKI_LANG") or cfg.get("lang") or DEFAULT_LANG
    ua = os.environ.get("WIKI_UA") or DEFAULT_UA
    return proxy, lang, ua


# ------- base URL 映射 -------
# api -> (覆盖用的环境变量名, 默认模板)
BASE_HOSTS = {
    "wmf-restbase": (
        "WIKI_HOST_WMF_RESTBASE",
        "https://{lang}.wikipedia.org/api/rest_v1",
    ),
    "wmf-restbase-global": (
        "WIKI_HOST_WMF_GLOBAL",
        "https://wikimedia.org/api/rest_v1",
    ),
    "mw-extra": (
        "WIKI_HOST_MW_EXTRA",
        "https://{lang}.wikipedia.org/w/rest.php",
    ),
    "growthexperiments.v0": (
        "WIKI_HOST_GROWTH",
        "https://{lang}.wikipedia.org/w/rest.php/growthexperiments/v0",
    ),
    "specs.v0": (
        "WIKI_HOST_SPECS",
        "https://{lang}.wikipedia.org/w/rest.php/specs/v0",
    ),
    "attribution.v0-beta": (
        "WIKI_HOST_ATTRIBUTION",
        "https://{lang}.wikipedia.org/w/rest.php/attribution/v0-beta",
    ),
}


def base_for(api: str, lang: str) -> str:
    env_key, tmpl = BASE_HOSTS[api]
    return os.environ.get(env_key) or tmpl.format(lang=lang)


# ------- endpoint 路径表 -------
# (api, METHOD, name) -> 路径模板（含 {param}）
ENDPOINTS = {
    # ===== wmf-restbase =====
    ("wmf-restbase", "GET", "citation"): "/data/citation/{format}/{query}",
    ("wmf-restbase", "GET", "css-mobile"): "/data/css/mobile/{type}",
    ("wmf-restbase", "GET", "i18n"): "/data/i18n/{type}",
    ("wmf-restbase", "GET", "js-mobile"): "/data/javascript/mobile/{type}",
    ("wmf-restbase", "GET", "lists"): "/data/lists/",
    ("wmf-restbase", "POST", "lists-create"): "/data/lists/",
    ("wmf-restbase", "POST", "lists-batch-create"): "/data/lists/batch",
    ("wmf-restbase", "GET", "lists-changes"): "/data/lists/changes/since/{date}",
    ("wmf-restbase", "GET", "lists-pages"): "/data/lists/pages/{project}/{title}",
    ("wmf-restbase", "POST", "lists-setup"): "/data/lists/setup",
    ("wmf-restbase", "POST", "lists-teardown"): "/data/lists/teardown",
    ("wmf-restbase", "PUT", "list-update"): "/data/lists/{id}",
    ("wmf-restbase", "DELETE", "list-delete"): "/data/lists/{id}",
    ("wmf-restbase", "GET", "list-entries"): "/data/lists/{id}/entries/",
    ("wmf-restbase", "POST", "list-entries-create"): "/data/lists/{id}/entries/",
    ("wmf-restbase", "POST", "list-entries-batch"): "/data/lists/{id}/entries/batch",
    ("wmf-restbase", "DELETE", "list-entry-delete"): "/data/lists/{id}/entries/{entry_id}",
    ("wmf-restbase", "GET", "reco-morelike"): "/data/recommendation/article/creation/morelike/{seed_article}",
    ("wmf-restbase", "GET", "reco-translation"): "/data/recommendation/article/creation/translation/{from_lang}",
    ("wmf-restbase", "GET", "reco-translation-seed"): "/data/recommendation/article/creation/translation/{from_lang}/{seed_article}",
    ("wmf-restbase", "POST", "math-check"): "/media/math/check/{type}",
    ("wmf-restbase", "GET", "math-formula"): "/media/math/formula/{hash}",
    ("wmf-restbase", "GET", "math-render"): "/media/math/render/{format}/{hash}",
    ("wmf-restbase", "GET", "page"): "/page/",
    ("wmf-restbase", "GET", "page-html"): "/page/html/{title}",
    ("wmf-restbase", "GET", "page-html-rev"): "/page/html/{title}/{revision}",
    ("wmf-restbase", "GET", "page-lint"): "/page/lint/{title}",
    ("wmf-restbase", "GET", "page-lint-rev"): "/page/lint/{title}/{revision}",
    ("wmf-restbase", "GET", "page-media-list"): "/page/media-list/{title}",
    ("wmf-restbase", "GET", "page-media-list-rev"): "/page/media-list/{title}/{revision}",
    ("wmf-restbase", "GET", "page-mobile-html-offline"): "/page/mobile-html-offline-resources/{title}",
    ("wmf-restbase", "GET", "page-mobile-html-offline-rev"): "/page/mobile-html-offline-resources/{title}/{revision}",
    ("wmf-restbase", "GET", "page-mobile-html"): "/page/mobile-html/{title}",
    ("wmf-restbase", "GET", "page-mobile-html-rev"): "/page/mobile-html/{title}/{revision}",
    ("wmf-restbase", "GET", "page-summary"): "/page/summary/{title}",
    ("wmf-restbase", "GET", "page-talk"): "/page/talk/{title}",
    ("wmf-restbase", "GET", "page-talk-rev"): "/page/talk/{title}/{revision}",
    ("wmf-restbase", "GET", "page-title"): "/page/title/{title}",
    ("wmf-restbase", "GET", "page-title-rev"): "/page/title/{title}/{revision}",
    ("wmf-restbase", "POST", "transform-html-wikitext"): "/transform/html/to/wikitext",
    ("wmf-restbase", "POST", "transform-html-wikitext-title"): "/transform/html/to/wikitext/{title}",
    ("wmf-restbase", "POST", "transform-html-wikitext-title-rev"): "/transform/html/to/wikitext/{title}/{revision}",
    ("wmf-restbase", "POST", "transform-wikitext-html"): "/transform/wikitext/to/html",
    ("wmf-restbase", "POST", "transform-wikitext-html-title"): "/transform/wikitext/to/html/{title}",
    ("wmf-restbase", "POST", "transform-wikitext-html-title-rev"): "/transform/wikitext/to/html/{title}/{revision}",
    ("wmf-restbase", "POST", "transform-wikitext-lint"): "/transform/wikitext/to/lint",
    ("wmf-restbase", "POST", "transform-wikitext-lint-title"): "/transform/wikitext/to/lint/{title}",
    ("wmf-restbase", "POST", "transform-wikitext-lint-title-rev"): "/transform/wikitext/to/lint/{title}/{revision}",
    ("wmf-restbase", "POST", "transform-wikitext-mobile-html"): "/transform/wikitext/to/mobile-html/{title}",

    # ===== mw-extra =====
    ("mw-extra", "DELETE", "campaign-event-contrib-delete"): "/campaignevents/v0/event_contributions/{id}",
    ("mw-extra", "POST", "campaign-event-register"): "/campaignevents/v0/event_registration",
    ("mw-extra", "GET", "campaign-event-register-get"): "/campaignevents/v0/event_registration/{id}",
    ("mw-extra", "DELETE", "campaign-event-register-delete"): "/campaignevents/v0/event_registration/{id}",
    ("mw-extra", "PUT", "campaign-event-register-update"): "/campaignevents/v0/event_registration/{id}",
    ("mw-extra", "PUT", "campaign-event-register-edits"): "/campaignevents/v0/event_registration/{id}/edits/{wiki}/{revid}",
    ("mw-extra", "POST", "campaign-event-register-email"): "/campaignevents/v0/event_registration/{id}/email",
    ("mw-extra", "GET", "campaign-event-organizers"): "/campaignevents/v0/event_registration/{id}/organizers",
    ("mw-extra", "PUT", "campaign-event-organizers-update"): "/campaignevents/v0/event_registration/{id}/organizers",
    ("mw-extra", "GET", "campaign-event-participants"): "/campaignevents/v0/event_registration/{id}/participants",
    ("mw-extra", "DELETE", "campaign-event-participants-delete"): "/campaignevents/v0/event_registration/{id}/participants",
    ("mw-extra", "PUT", "campaign-event-participant-self"): "/campaignevents/v0/event_registration/{id}/participants/self",
    ("mw-extra", "DELETE", "campaign-event-participant-self-delete"): "/campaignevents/v0/event_registration/{id}/participants/self",
    ("mw-extra", "GET", "campaign-event-participant-self-get"): "/campaignevents/v0/event_registration/{id}/participants/self",
    ("mw-extra", "GET", "campaign-formatted-time"): "/campaignevents/v0/formatted_time/{languageCode}/{start}/{end}",
    ("mw-extra", "GET", "campaign-organizer-events"): "/campaignevents/v0/organizer/{userid}/event_registrations",
    ("mw-extra", "GET", "campaign-participant-edit-events"): "/campaignevents/v0/participant/self/events_for_edit",
    ("mw-extra", "GET", "campaign-participant-events"): "/campaignevents/v0/participant/{userid}/event_registrations",
    ("mw-extra", "GET", "campaign-participant-questions"): "/campaignevents/v0/participant_questions",
    ("mw-extra", "POST", "checkuser-batch-tempaccount"): "/checkuser/v0/batch-temporaryaccount",
    ("mw-extra", "POST", "checkuser-connected-tempaccounts"): "/checkuser/v0/connectedtemporaryaccounts/{name}",
    ("mw-extra", "POST", "checkuser-suggested-update"): "/checkuser/v0/suggestedinvestigations/case/{caseId}/update",
    ("mw-extra", "POST", "checkuser-tempaccount-ip"): "/checkuser/v0/temporaryaccount/ip/{ip}",
    ("mw-extra", "POST", "checkuser-tempaccount-name"): "/checkuser/v0/temporaryaccount/{name}",
    ("mw-extra", "POST", "checkuser-useragent-clienthints"): "/checkuser/v0/useragent-clienthints/{type}/{id}",
    ("mw-extra", "POST", "checkuser-userinfo"): "/checkuser/v0/userinfo",
    ("mw-extra", "GET", "checkuser-userinfo-blocked"): "/checkuser/v0/userinfo/blocked/{name}",
    ("mw-extra", "POST", "confirmedit-hcaptcha-blocktoken"): "/confirmedit/v0/hcaptcha/blocktoken",
    ("mw-extra", "POST", "eventbus-internal-job"): "/eventbus/v0/internal/job/execute",
    ("mw-extra", "GET", "flaggedrevs-diffheader"): "/flaggedrevs/internal/diffheader/{oldId}/{newId}",
    ("mw-extra", "POST", "flaggedrevs-review"): "/flaggedrevs/internal/review/{target}",
    ("mw-extra", "POST", "ipinfo-archived-revision"): "/ipinfo/v0/archivedrevision/{id}",
    ("mw-extra", "POST", "ipinfo-log"): "/ipinfo/v0/log/{id}",
    ("mw-extra", "POST", "ipinfo-norevision"): "/ipinfo/v0/norevision/{username}",
    ("mw-extra", "POST", "ipinfo-revision"): "/ipinfo/v0/revision/{id}",
    ("mw-extra", "GET", "math-popup"): "/math/v0/popup/html/{qid}",
    ("mw-extra", "POST", "oauth2-access-token"): "/oauth2/access_token",
    ("mw-extra", "GET", "oauth2-authorize"): "/oauth2/authorize",
    ("mw-extra", "POST", "oauth2-client-create"): "/oauth2/client",
    ("mw-extra", "GET", "oauth2-client-list"): "/oauth2/client",
    ("mw-extra", "POST", "oauth2-client-reset-secret"): "/oauth2/client/{client_key}/reset_secret",
    ("mw-extra", "GET", "oauth2-resource"): "/oauth2/resource/{type}",
    ("mw-extra", "POST", "reportincident-report"): "/reportincident/v0/report",
    ("mw-extra", "POST", "securepoll-translation"): "/securepoll/set_translation/{entityid}/{language}",
    ("mw-extra", "GET", "file"): "/v1/file/{title}",
    ("mw-extra", "GET", "file-thumbnails"): "/v1/file/{title}/thumbnails",
    ("mw-extra", "POST", "page-create"): "/v1/page",
    ("mw-extra", "GET", "page-source"): "/v1/page/{title}",
    ("mw-extra", "PUT", "page-update"): "/v1/page/{title}",
    ("mw-extra", "GET", "page-bare"): "/v1/page/{title}/bare",
    ("mw-extra", "GET", "page-history"): "/v1/page/{title}/history",
    ("mw-extra", "GET", "page-history-counts"): "/v1/page/{title}/history/counts/{type}",
    ("mw-extra", "GET", "page-html-mw"): "/v1/page/{title}/html",
    ("mw-extra", "GET", "page-languages"): "/v1/page/{title}/links/language",
    ("mw-extra", "GET", "page-media"): "/v1/page/{title}/links/media",
    ("mw-extra", "GET", "page-lint-mw"): "/v1/page/{title}/lint",
    ("mw-extra", "GET", "page-with-html"): "/v1/page/{title}/with_html",
    ("mw-extra", "GET", "revision-compare"): "/v1/revision/{from}/compare/{to}",
    ("mw-extra", "GET", "revision-source"): "/v1/revision/{id}",
    ("mw-extra", "GET", "revision-bare"): "/v1/revision/{id}/bare",
    ("mw-extra", "GET", "revision-html"): "/v1/revision/{id}/html",
    ("mw-extra", "GET", "revision-lint"): "/v1/revision/{id}/lint",
    ("mw-extra", "GET", "revision-with-html"): "/v1/revision/{id}/with_html",
    ("mw-extra", "GET", "opensearch"): "/v1/search",
    ("mw-extra", "GET", "search-page"): "/v1/search/page",
    ("mw-extra", "GET", "search-title"): "/v1/search/title",
    ("mw-extra", "POST", "transform-html-wikitext-mw"): "/v1/transform/html/to/wikitext",
    ("mw-extra", "POST", "transform-html-wikitext-mw-title"): "/v1/transform/html/to/wikitext/{title}",
    ("mw-extra", "POST", "transform-html-wikitext-mw-title-rev"): "/v1/transform/html/to/wikitext/{title}/{revision}",
    ("mw-extra", "POST", "transform-wikitext-html-mw"): "/v1/transform/wikitext/to/html",
    ("mw-extra", "POST", "transform-wikitext-html-mw-title"): "/v1/transform/wikitext/to/html/{title}",
    ("mw-extra", "POST", "transform-wikitext-html-mw-title-rev"): "/v1/transform/wikitext/to/html/{title}/{revision}",
    ("mw-extra", "POST", "transform-wikitext-lint-mw"): "/v1/transform/wikitext/to/lint",
    ("mw-extra", "POST", "transform-wikitext-lint-mw-title"): "/v1/transform/wikitext/to/lint/{title}",
    ("mw-extra", "POST", "transform-wikitext-lint-mw-title-rev"): "/v1/transform/wikitext/to/lint/{title}/{revision}",
    ("mw-extra", "PUT", "campaign-grant-id-update"): "/wikimediacampaignevents/v0/event_registration/{id}/grant_id",
    ("mw-extra", "DELETE", "campaign-grant-id-delete"): "/wikimediacampaignevents/v0/event_registration/{id}/grant_id",
    ("mw-extra", "GET", "campaign-grant-id-get"): "/wikimediacampaignevents/v0/event_registration/{id}/grant_id",

    # ===== growthexperiments.v0 =====
    ("growthexperiments.v0", "GET", "mentees"): "/mentees",
    ("growthexperiments.v0", "GET", "mentees-prefixsearch"): "/mentees/prefixsearch/{prefix}",
    ("growthexperiments.v0", "POST", "newcomertask-complete"): "/newcomertask/complete",
    ("growthexperiments.v0", "GET", "quickstarttips"): "/quickstarttips/{skin}/{editor}/{tasktypeid}/{uselang}",
    ("growthexperiments.v0", "PUT", "addimage-feedback"): "/suggestions/addimage/feedback/{title}",
    ("growthexperiments.v0", "GET", "link-suggestions"): "/suggestions/addlink/{title}",
    ("growthexperiments.v0", "GET", "suggestions-info"): "/suggestions/info",
    ("growthexperiments.v0", "GET", "user-impact"): "/user-impact/{user}",
    ("growthexperiments.v0", "POST", "user-impact-update"): "/user-impact/{user}",
    ("growthexperiments.v0", "POST", "welcome-survey-skip"): "/welcomesurvey/skip",

    # ===== specs.v0 =====
    ("specs.v0", "GET", "discovery"): "/discovery",
    ("specs.v0", "GET", "module"): "/module/{module}",
    ("specs.v0", "GET", "module-version"): "/module/{module}/{version}",

    # ===== wmf-restbase-global (Math API) =====
    ("wmf-restbase-global", "POST", "math-check"): "/media/math/check/{type}",
    ("wmf-restbase-global", "GET", "math-formula"): "/media/math/formula/{hash}",
    ("wmf-restbase-global", "GET", "math-render"): "/media/math/render/{format}/{hash}",

    # ===== attribution.v0-beta =====
    ("attribution.v0-beta", "GET", "page-signals"): "/pages/{title}/signals",
    ("attribution.v0-beta", "GET", "site-signals"): "/site/signals",
}


def substitute(template: str, args: list) -> str:
    """逐个把 args 填入模板里第一个未替换的 {param}。"""
    out = template
    for a in args:
        # 用函数形式返回固定值，避免 re 对 replacement 里的 \ / \1 等做特殊解析
        out = re.sub(r"\{[^}]+\}", lambda m, repl=a: repl, out, count=1)
    return out


USAGE = """用法：wikipedia_api.py <api> <method> <endpoint-name> [path-args...] [-- [curl-extra-args...]]

<api> 可选：
  wmf-restbase            Wikimedia REST API
  wmf-restbase-global     Math API（wikimedia.org）
  mw-extra                MediaWiki REST API（routes not in modules）
  growthexperiments.v0    Growth experiments API
  specs.v0                Specs API
  attribution.v0-beta     Attribution API (Beta)

<method>：GET / POST / PUT / DELETE / PATCH

<endpoint-name>：见 SKILL.md 端点表；可用 --list 查看

-- 后可追加任意 curl 参数，例如 -H "..." -d '{...}'

配置文件 ~/.wikipedia_restapi.json：
  { "proxy": "http://127.0.0.1:16780", "lang": "en" }
  首次运行自动使用默认值。环境变量 WIKI_PROXY / WIKI_LANG 可覆盖。
"""


def list_apis() -> None:
    print("可用 API：wmf-restbase | wmf-restbase-global | mw-extra | "
          "growthexperiments.v0 | specs.v0 | attribution.v0-beta")
    print("完整端点表见 SKILL.md / references/endpoints.md")


def main(argv: list) -> int:
    if not argv or argv[0] in ("-h", "--help"):
        print(USAGE)
        return 0 if argv else 1
    if argv[0] == "--list":
        list_apis()
        return 0

    # "--" 之前是位置参数，之后原样转发给 curl
    if "--" in argv:
        idx = argv.index("--")
        pos = argv[:idx]
        curl_extra = argv[idx + 1:]
    else:
        pos = argv
        curl_extra = []

    if len(pos) < 3:
        print("Error: 需要 <api> <method> <endpoint-name>", file=sys.stderr)
        return 1

    api = pos[0]
    method = pos[1].upper()
    name = pos[2]
    path_args = pos[3:]

    if api not in BASE_HOSTS:
        print(f"Unknown API: {api}", file=sys.stderr)
        return 2

    key = (api, method, name)
    if key not in ENDPOINTS:
        print(f"Unknown endpoint: {api} {method} {name}", file=sys.stderr)
        return 3

    template = ENDPOINTS[key]
    needed = len(re.findall(r"\{[^}]+\}", template))
    if len(path_args) != needed:
        print(f"Error: {api} {method} {name} 需要 {needed} 个 path 参数，"
              f"提供了 {len(path_args)}", file=sys.stderr)
        print(f"  Template: {template}", file=sys.stderr)
        return 4

    proxy, lang, ua = load_config()
    base = base_for(api, lang)
    path = substitute(template, path_args)
    url = base + path

    # 实际请求委托 curl（保留 -H / -d / --data-urlencode / -G 等语义）
    cmd = [
        "curl", "-sS", "--max-time", "60",
        "-x", proxy,
        "-H", f"User-Agent: {ua}",
        "-H", f"Api-User-Agent: {ua}",
        "-X", method,
        "-w", "\n[HTTP %{http_code}  size=%{size_download}B  time=%{time_total}s]\n",
        *curl_extra,
        url,
    ]
    return subprocess.call(cmd)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
