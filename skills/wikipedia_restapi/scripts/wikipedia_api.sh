#!/usr/bin/env bash
# wikipedia_api.sh — 维基百科 REST API 统一入口
#
# 用法：
#   wikipedia_api.sh <api> <method> <endpoint-name> [path-args...] [-- query/header params]
#
# 示例：
#   wikipedia_api.sh wmf-restbase GET page-summary "Berlin"
#   wikipedia_api.sh wmf-restbase GET page-html "Tokyo"
#   wikipedia_api.sh mw-extra GET search-page -- q=Albert+Einstein limit=3
#   wikipedia_api.sh wmf-restbase-global POST math-check tex -- '{"q":"E=mc^2"}'
#
# 配置文件 ~/.wikipedia_restapi.json（首次运行自动生成）：
#   { "proxy": "http://127.0.0.1:16780", "lang": "en" }
#
# 环境变量（覆盖配置文件）：
#   WIKI_PROXY  — HTTP 代理
#   WIKI_LANG   — 默认语言
#   WIKI_HOST_* — 覆盖特定 API 的 base URL

set -o pipefail

CONFIG="${WIKI_CONFIG:-$HOME/.wikipedia_restapi.json}"

load_config() {
  if [[ -f "$CONFIG" ]]; then
    # 用 python3 解析 JSON 输出 key=value 供 source
    local parsed
    parsed=$(python3 -c "
import json,sys
try:
  with open(r'$CONFIG') as f:
    cfg = json.load(f)
  print('WIKI_PROXY=' + cfg.get('proxy',''))
  print('WIKI_LANG=' + cfg.get('lang','en'))
except: pass
" 2>/dev/null) || true
    eval "$parsed"
  fi
  # 环境变量优先于配置文件
  WIKI_PROXY="${WIKI_PROXY:-http://127.0.0.1:16780}"
  WIKI_LANG="${WIKI_LANG:-en}"
  WIKI_UA="${WIKI_UA:-wikipedia-restapi-skill/1.0 (contact: skill-author)}"
}

load_config

# ------- base URL 映射 -------
base_for() {
  case "$1" in
    wmf-restbase)           echo "${WIKI_HOST_WMF_RESTBASE:-https://${WIKI_LANG}.wikipedia.org/api/rest_v1}";;
    wmf-restbase-global)    echo "${WIKI_HOST_WMF_GLOBAL:-https://wikimedia.org/api/rest_v1}";;
    mw-extra)               echo "${WIKI_HOST_MW_EXTRA:-https://${WIKI_LANG}.wikipedia.org/w/rest.php}";;
    growthexperiments.v0)   echo "${WIKI_HOST_GROWTH:-https://${WIKI_LANG}.wikipedia.org/w/rest.php/growthexperiments/v0}";;
    specs.v0)               echo "${WIKI_HOST_SPECS:-https://${WIKI_LANG}.wikipedia.org/w/rest.php/specs/v0}";;
    attribution.v0-beta)    echo "${WIKI_HOST_ATTRIBUTION:-https://${WIKI_LANG}.wikipedia.org/w/rest.php/attribution/v0-beta}";;
    *) echo "Unknown API: $1" >&2; return 1;;
  esac
}

# ------- endpoint 路径表 -------
# 名称 -> 路径模板（含 {param}）
endpoint_path() {
  case "$1:$2:$3" in
    # ===== wmf-restbase =====
    wmf-restbase:GET:citation) echo "/data/citation/{format}/{query}";;
    wmf-restbase:GET:css-mobile) echo "/data/css/mobile/{type}";;
    wmf-restbase:GET:i18n) echo "/data/i18n/{type}";;
    wmf-restbase:GET:js-mobile) echo "/data/javascript/mobile/{type}";;
    wmf-restbase:GET:lists) echo "/data/lists/";;
    wmf-restbase:POST:lists-create) echo "/data/lists/";;
    wmf-restbase:POST:lists-batch-create) echo "/data/lists/batch";;
    wmf-restbase:GET:lists-changes) echo "/data/lists/changes/since/{date}";;
    wmf-restbase:GET:lists-pages) echo "/data/lists/pages/{project}/{title}";;
    wmf-restbase:POST:lists-setup) echo "/data/lists/setup";;
    wmf-restbase:POST:lists-teardown) echo "/data/lists/teardown";;
    wmf-restbase:PUT:list-update) echo "/data/lists/{id}";;
    wmf-restbase:DELETE:list-delete) echo "/data/lists/{id}";;
    wmf-restbase:GET:list-entries) echo "/data/lists/{id}/entries/";;
    wmf-restbase:POST:list-entries-create) echo "/data/lists/{id}/entries/";;
    wmf-restbase:POST:list-entries-batch) echo "/data/lists/{id}/entries/batch";;
    wmf-restbase:DELETE:list-entry-delete) echo "/data/lists/{id}/entries/{entry_id}";;
    wmf-restbase:GET:reco-morelike) echo "/data/recommendation/article/creation/morelike/{seed_article}";;
    wmf-restbase:GET:reco-translation) echo "/data/recommendation/article/creation/translation/{from_lang}";;
    wmf-restbase:GET:reco-translation-seed) echo "/data/recommendation/article/creation/translation/{from_lang}/{seed_article}";;
    wmf-restbase:POST:math-check) echo "/media/math/check/{type}";;
    wmf-restbase:GET:math-formula) echo "/media/math/formula/{hash}";;
    wmf-restbase:GET:math-render) echo "/media/math/render/{format}/{hash}";;
    wmf-restbase:GET:page) echo "/page/";;
    wmf-restbase:GET:page-html) echo "/page/html/{title}";;
    wmf-restbase:GET:page-html-rev) echo "/page/html/{title}/{revision}";;
    wmf-restbase:GET:page-lint) echo "/page/lint/{title}";;
    wmf-restbase:GET:page-lint-rev) echo "/page/lint/{title}/{revision}";;
    wmf-restbase:GET:page-media-list) echo "/page/media-list/{title}";;
    wmf-restbase:GET:page-media-list-rev) echo "/page/media-list/{title}/{revision}";;
    wmf-restbase:GET:page-mobile-html-offline) echo "/page/mobile-html-offline-resources/{title}";;
    wmf-restbase:GET:page-mobile-html-offline-rev) echo "/page/mobile-html-offline-resources/{title}/{revision}";;
    wmf-restbase:GET:page-mobile-html) echo "/page/mobile-html/{title}";;
    wmf-restbase:GET:page-mobile-html-rev) echo "/page/mobile-html/{title}/{revision}";;
    wmf-restbase:GET:page-summary) echo "/page/summary/{title}";;
    wmf-restbase:GET:page-talk) echo "/page/talk/{title}";;
    wmf-restbase:GET:page-talk-rev) echo "/page/talk/{title}/{revision}";;
    wmf-restbase:GET:page-title) echo "/page/title/{title}";;
    wmf-restbase:GET:page-title-rev) echo "/page/title/{title}/{revision}";;
    wmf-restbase:POST:transform-html-wikitext) echo "/transform/html/to/wikitext";;
    wmf-restbase:POST:transform-html-wikitext-title) echo "/transform/html/to/wikitext/{title}";;
    wmf-restbase:POST:transform-html-wikitext-title-rev) echo "/transform/html/to/wikitext/{title}/{revision}";;
    wmf-restbase:POST:transform-wikitext-html) echo "/transform/wikitext/to/html";;
    wmf-restbase:POST:transform-wikitext-html-title) echo "/transform/wikitext/to/html/{title}";;
    wmf-restbase:POST:transform-wikitext-html-title-rev) echo "/transform/wikitext/to/html/{title}/{revision}";;
    wmf-restbase:POST:transform-wikitext-lint) echo "/transform/wikitext/to/lint";;
    wmf-restbase:POST:transform-wikitext-lint-title) echo "/transform/wikitext/to/lint/{title}";;
    wmf-restbase:POST:transform-wikitext-lint-title-rev) echo "/transform/wikitext/to/lint/{title}/{revision}";;
    wmf-restbase:POST:transform-wikitext-mobile-html) echo "/transform/wikitext/to/mobile-html/{title}";;

    # ===== mw-extra =====
    mw-extra:DELETE:campaign-event-contrib-delete) echo "/campaignevents/v0/event_contributions/{id}";;
    mw-extra:POST:campaign-event-register) echo "/campaignevents/v0/event_registration";;
    mw-extra:GET:campaign-event-register-get) echo "/campaignevents/v0/event_registration/{id}";;
    mw-extra:DELETE:campaign-event-register-delete) echo "/campaignevents/v0/event_registration/{id}";;
    mw-extra:PUT:campaign-event-register-update) echo "/campaignevents/v0/event_registration/{id}";;
    mw-extra:PUT:campaign-event-register-edits) echo "/campaignevents/v0/event_registration/{id}/edits/{wiki}/{revid}";;
    mw-extra:POST:campaign-event-register-email) echo "/campaignevents/v0/event_registration/{id}/email";;
    mw-extra:GET:campaign-event-organizers) echo "/campaignevents/v0/event_registration/{id}/organizers";;
    mw-extra:PUT:campaign-event-organizers-update) echo "/campaignevents/v0/event_registration/{id}/organizers";;
    mw-extra:GET:campaign-event-participants) echo "/campaignevents/v0/event_registration/{id}/participants";;
    mw-extra:DELETE:campaign-event-participants-delete) echo "/campaignevents/v0/event_registration/{id}/participants";;
    mw-extra:PUT:campaign-event-participant-self) echo "/campaignevents/v0/event_registration/{id}/participants/self";;
    mw-extra:DELETE:campaign-event-participant-self-delete) echo "/campaignevents/v0/event_registration/{id}/participants/self";;
    mw-extra:GET:campaign-event-participant-self-get) echo "/campaignevents/v0/event_registration/{id}/participants/self";;
    mw-extra:GET:campaign-formatted-time) echo "/campaignevents/v0/formatted_time/{languageCode}/{start}/{end}";;
    mw-extra:GET:campaign-organizer-events) echo "/campaignevents/v0/organizer/{userid}/event_registrations";;
    mw-extra:GET:campaign-participant-edit-events) echo "/campaignevents/v0/participant/self/events_for_edit";;
    mw-extra:GET:campaign-participant-events) echo "/campaignevents/v0/participant/{userid}/event_registrations";;
    mw-extra:GET:campaign-participant-questions) echo "/campaignevents/v0/participant_questions";;
    mw-extra:POST:checkuser-batch-tempaccount) echo "/checkuser/v0/batch-temporaryaccount";;
    mw-extra:POST:checkuser-connected-tempaccounts) echo "/checkuser/v0/connectedtemporaryaccounts/{name}";;
    mw-extra:POST:checkuser-suggested-update) echo "/checkuser/v0/suggestedinvestigations/case/{caseId}/update";;
    mw-extra:POST:checkuser-tempaccount-ip) echo "/checkuser/v0/temporaryaccount/ip/{ip}";;
    mw-extra:POST:checkuser-tempaccount-name) echo "/checkuser/v0/temporaryaccount/{name}";;
    mw-extra:POST:checkuser-useragent-clienthints) echo "/checkuser/v0/useragent-clienthints/{type}/{id}";;
    mw-extra:POST:checkuser-userinfo) echo "/checkuser/v0/userinfo";;
    mw-extra:GET:checkuser-userinfo-blocked) echo "/checkuser/v0/userinfo/blocked/{name}";;
    mw-extra:POST:confirmedit-hcaptcha-blocktoken) echo "/confirmedit/v0/hcaptcha/blocktoken";;
    mw-extra:POST:eventbus-internal-job) echo "/eventbus/v0/internal/job/execute";;
    mw-extra:GET:flaggedrevs-diffheader) echo "/flaggedrevs/internal/diffheader/{oldId}/{newId}";;
    mw-extra:POST:flaggedrevs-review) echo "/flaggedrevs/internal/review/{target}";;
    mw-extra:POST:ipinfo-archived-revision) echo "/ipinfo/v0/archivedrevision/{id}";;
    mw-extra:POST:ipinfo-log) echo "/ipinfo/v0/log/{id}";;
    mw-extra:POST:ipinfo-norevision) echo "/ipinfo/v0/norevision/{username}";;
    mw-extra:POST:ipinfo-revision) echo "/ipinfo/v0/revision/{id}";;
    mw-extra:GET:math-popup) echo "/math/v0/popup/html/{qid}";;
    mw-extra:POST:oauth2-access-token) echo "/oauth2/access_token";;
    mw-extra:GET:oauth2-authorize) echo "/oauth2/authorize";;
    mw-extra:POST:oauth2-client-create) echo "/oauth2/client";;
    mw-extra:GET:oauth2-client-list) echo "/oauth2/client";;
    mw-extra:POST:oauth2-client-reset-secret) echo "/oauth2/client/{client_key}/reset_secret";;
    mw-extra:GET:oauth2-resource) echo "/oauth2/resource/{type}";;
    mw-extra:POST:reportincident-report) echo "/reportincident/v0/report";;
    mw-extra:POST:securepoll-translation) echo "/securepoll/set_translation/{entityid}/{language}";;
    mw-extra:GET:file) echo "/v1/file/{title}";;
    mw-extra:GET:file-thumbnails) echo "/v1/file/{title}/thumbnails";;
    mw-extra:POST:page-create) echo "/v1/page";;
    mw-extra:GET:page-source) echo "/v1/page/{title}";;
    mw-extra:PUT:page-update) echo "/v1/page/{title}";;
    mw-extra:GET:page-bare) echo "/v1/page/{title}/bare";;
    mw-extra:GET:page-history) echo "/v1/page/{title}/history";;
    mw-extra:GET:page-history-counts) echo "/v1/page/{title}/history/counts/{type}";;
    mw-extra:GET:page-html-mw) echo "/v1/page/{title}/html";;
    mw-extra:GET:page-languages) echo "/v1/page/{title}/links/language";;
    mw-extra:GET:page-media) echo "/v1/page/{title}/links/media";;
    mw-extra:GET:page-lint-mw) echo "/v1/page/{title}/lint";;
    mw-extra:GET:page-with-html) echo "/v1/page/{title}/with_html";;
    mw-extra:GET:revision-compare) echo "/v1/revision/{from}/compare/{to}";;
    mw-extra:GET:revision-source) echo "/v1/revision/{id}";;
    mw-extra:GET:revision-bare) echo "/v1/revision/{id}/bare";;
    mw-extra:GET:revision-html) echo "/v1/revision/{id}/html";;
    mw-extra:GET:revision-lint) echo "/v1/revision/{id}/lint";;
    mw-extra:GET:revision-with-html) echo "/v1/revision/{id}/with_html";;
    mw-extra:GET:opensearch) echo "/v1/search";;
    mw-extra:GET:search-page) echo "/v1/search/page";;
    mw-extra:GET:search-title) echo "/v1/search/title";;
    mw-extra:POST:transform-html-wikitext-mw) echo "/v1/transform/html/to/wikitext";;
    mw-extra:POST:transform-html-wikitext-mw-title) echo "/v1/transform/html/to/wikitext/{title}";;
    mw-extra:POST:transform-html-wikitext-mw-title-rev) echo "/v1/transform/html/to/wikitext/{title}/{revision}";;
    mw-extra:POST:transform-wikitext-html-mw) echo "/v1/transform/wikitext/to/html";;
    mw-extra:POST:transform-wikitext-html-mw-title) echo "/v1/transform/wikitext/to/html/{title}";;
    mw-extra:POST:transform-wikitext-html-mw-title-rev) echo "/v1/transform/wikitext/to/html/{title}/{revision}";;
    mw-extra:POST:transform-wikitext-lint-mw) echo "/v1/transform/wikitext/to/lint";;
    mw-extra:POST:transform-wikitext-lint-mw-title) echo "/v1/transform/wikitext/to/lint/{title}";;
    mw-extra:POST:transform-wikitext-lint-mw-title-rev) echo "/v1/transform/wikitext/to/lint/{title}/{revision}";;
    mw-extra:PUT:campaign-grant-id-update) echo "/wikimediacampaignevents/v0/event_registration/{id}/grant_id";;
    mw-extra:DELETE:campaign-grant-id-delete) echo "/wikimediacampaignevents/v0/event_registration/{id}/grant_id";;
    mw-extra:GET:campaign-grant-id-get) echo "/wikimediacampaignevents/v0/event_registration/{id}/grant_id";;

    # ===== growthexperiments.v0 =====
    growthexperiments.v0:GET:mentees) echo "/mentees";;
    growthexperiments.v0:GET:mentees-prefixsearch) echo "/mentees/prefixsearch/{prefix}";;
    growthexperiments.v0:POST:newcomertask-complete) echo "/newcomertask/complete";;
    growthexperiments.v0:GET:quickstarttips) echo "/quickstarttips/{skin}/{editor}/{tasktypeid}/{uselang}";;
    growthexperiments.v0:PUT:addimage-feedback) echo "/suggestions/addimage/feedback/{title}";;
    growthexperiments.v0:GET:link-suggestions) echo "/suggestions/addlink/{title}";;
    growthexperiments.v0:GET:suggestions-info) echo "/suggestions/info";;
    growthexperiments.v0:GET:user-impact) echo "/user-impact/{user}";;
    growthexperiments.v0:POST:user-impact-update) echo "/user-impact/{user}";;
    growthexperiments.v0:POST:welcome-survey-skip) echo "/welcomesurvey/skip";;

    # ===== specs.v0 =====
    specs.v0:GET:discovery) echo "/discovery";;
    specs.v0:GET:module) echo "/module/{module}";;
    specs.v0:GET:module-version) echo "/module/{module}/{version}";;

    # ===== wmf-restbase-global (Math API) =====
    wmf-restbase-global:POST:math-check) echo "/media/math/check/{type}";;
    wmf-restbase-global:GET:math-formula) echo "/media/math/formula/{hash}";;
    wmf-restbase-global:GET:math-render) echo "/media/math/render/{format}/{hash}";;

    # ===== attribution.v0-beta =====
    attribution.v0-beta:GET:page-signals) echo "/pages/{title}/signals";;
    attribution.v0-beta:GET:site-signals) echo "/site/signals";;

    *) echo "Unknown endpoint: $1 $2 $3" >&2; return 1;;
  esac
}

# ------- URL 模板替换 -------
# 用法：substitute "/foo/{x}/{y}" "v1" "v2"  ->  /foo/v1/v2
# 一次替换第一个未替换的 {param}，避免对含花括号的值做正则匹配
substitute() {
  local tmpl="$1"; shift
  local out="$tmpl"
  for arg in "$@"; do
    out=$(printf '%s' "$out" | awk -v repl="$arg" '{
      while (match($0, /\{[^}]+\}/)) {
        $0 = substr($0, 1, RSTART-1) repl substr($0, RSTART+RLENGTH)
        break
      }
      print
    }')
  done
  echo "$out"
}

# ------- 主流程 -------
usage() {
  cat <<'EOF'
用法：wikipedia_api.sh <api> <method> <endpoint-name> [path-args...] [-- [curl-extra-args...]]

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
EOF
}

list_apis() {
  echo "可用 API：wmf-restbase | wmf-restbase-global | mw-extra | growthexperiments.v0 | specs.v0 | attribution.v0-beta"
  echo "完整端点表见 SKILL.md / references/endpoints.md"
}

if [[ $# -lt 1 ]]; then usage; exit 1; fi
case "$1" in
  -h|--help) usage; exit 0;;
  --list) list_apis; exit 0;;
esac

API="$1"; shift
METHOD="$1"; shift
NAME="$1"; shift

BASE=$(base_for "$API") || exit 2
TEMPLATE=$(endpoint_path "$API" "$METHOD" "$NAME") || exit 3

# 收集 path 参数（"--" 之前的所有非选项参数）
PATH_ARGS=()
while [[ $# -gt 0 && "$1" != "--" ]]; do
  PATH_ARGS+=("$1"); shift
done
[[ $# -gt 0 && "$1" == "--" ]] && shift

# 校验 path 参数数量
NEEDED=$(echo "$TEMPLATE" | grep -oE '\{[^}]+\}' | wc -l | tr -d ' ')
GIVEN=${#PATH_ARGS[@]}
if [[ "$GIVEN" -ne "$NEEDED" ]]; then
  echo "Error: $API $METHOD $NAME 需要 $NEEDED 个 path 参数，提供了 $GIVEN" >&2
  echo "  Template: $TEMPLATE" >&2
  exit 4
fi

PATH_BUILT=$(substitute "$TEMPLATE" "${PATH_ARGS[@]}")
URL="${BASE}${PATH_BUILT}"

# 用 curl 执行（不用 exec，便于显示错误码）
curl -sS --max-time 60 \
  -x "$WIKI_PROXY" \
  -H "User-Agent: $WIKI_UA" \
  -H "Api-User-Agent: $WIKI_UA" \
  -X "$METHOD" \
  -w "\n[HTTP %{http_code}  size=%{size_download}B  time=%{time_total}s]\n" \
  "$@" \
  "$URL"
