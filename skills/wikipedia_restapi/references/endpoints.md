# Wikipedia REST API 端点表

所有 endpoint 均通过 `scripts/wikipedia_api.sh` 调用。
完整调用格式：`wikipedia_api.sh <api> <method> <endpoint-name> [path-args...] [-- [curl-args...]]`

> path 参数中的空格请用 `%20` 或 `"` `"` 引用后再传入。query 参数里含空格请用 `--data-urlencode ... -G`。

## wmf-restbase — Wikimedia REST API

**Base URL**: `https://en.wikipedia.org/api/rest_v1`  
**版本**: 1.0.0  
**端点数**: 46

| Method | Endpoint | Path Template | Summary |
|--------|----------|---------------|---------|
| GET | /data/citation/{format}/{query} | `/data/citation/{format}/{query}` | Get citation data given an article identifier. |
| GET | /data/css/mobile/{type} | `/data/css/mobile/{type}` | Get CSS for mobile apps. |
| GET | /data/i18n/{type} | `/data/i18n/{type}` | Get internationalization info |
| GET | /data/javascript/mobile/{type} | `/data/javascript/mobile/{type}` | Get JavaScript for mobileapps |
| GET | /data/lists/ | `/data/lists/` | Get all lists of the current user. |
| POST | /data/lists/ | `/data/lists/` | Create a new list for the current user. |
| POST | /data/lists/batch | `/data/lists/batch` | Create multiple new lists for the current user. |
| GET | /data/lists/changes/since/{date} | `/data/lists/changes/since/{date}` | Get recent changes to the lists |
| GET | /data/lists/pages/{project}/{title} | `/data/lists/pages/{project}/{title}` | Get lists of the current user which contain a given page. |
| POST | /data/lists/setup | `/data/lists/setup` | Opt in to use reading lists. |
| POST | /data/lists/teardown | `/data/lists/teardown` | Opt out from using reading lists. |
| PUT | /data/lists/{id} | `/data/lists/{id}` | Update a list. |
| DELETE | /data/lists/{id} | `/data/lists/{id}` | Delete a list. |
| GET | /data/lists/{id}/entries/ | `/data/lists/{id}/entries/` | Get all entries of a given list. |
| POST | /data/lists/{id}/entries/ | `/data/lists/{id}/entries/` | Create a new list entry. |
| POST | /data/lists/{id}/entries/batch | `/data/lists/{id}/entries/batch` | Create multiple new list entries. |
| DELETE | /data/lists/{id}/entries/{entry_id} | `/data/lists/{id}/entries/{entry_id}` | Delete a list entry. |
| GET | /data/recommendation/article/creation/morelike/{seed_article} | `/data/recommendation/article/creation/morelike/{seed_article}` | Recommend missing articles |
| GET | /data/recommendation/article/creation/translation/{from_lang} | `/data/recommendation/article/creation/translation/{from_lang}` | Recommend articles for translation. |
| GET | /data/recommendation/article/creation/translation/{from_lang}/{seed_article} | `/data/recommendation/article/creation/translation/{from_lang}/{seed_article}` | Recommend articles for translation. |
| POST | /media/math/check/{type} | `/media/math/check/{type}` | Check and normalize a TeX formula. |
| GET | /media/math/formula/{hash} | `/media/math/formula/{hash}` | Get a previously-stored formula |
| GET | /media/math/render/{format}/{hash} | `/media/math/render/{format}/{hash}` | Get rendered formula in the given format. |
| GET | /page/ | `/page/` | List page-related API entry points. |
| GET | /page/html/{title} | `/page/html/{title}` | Get latest HTML for a title. |
| GET | /page/html/{title}/{revision} | `/page/html/{title}/{revision}` | Get HTML for a specific title/revision & optionally timeuuid. |
| GET | /page/lint/{title} | `/page/lint/{title}` | Get the linter errors for a specific title/revision. |
| GET | /page/lint/{title}/{revision} | `/page/lint/{title}/{revision}` | Get the linter errors for a specific title/revision. |
| GET | /page/media-list/{title} | `/page/media-list/{title}` | Get list of media files used on a page. |
| GET | /page/media-list/{title}/{revision} | `/page/media-list/{title}/{revision}` | Get list of media files used on a page. |
| GET | /page/mobile-html-offline-resources/{title} | `/page/mobile-html-offline-resources/{title}` | Get styles and scripts for offline consumption of mobile-html-formatted pages |
| GET | /page/mobile-html-offline-resources/{title}/{revision} | `/page/mobile-html-offline-resources/{title}/{revision}` | Get styles and scripts for offline consumption of mobile-html-formatted pages |
| GET | /page/mobile-html/{title} | `/page/mobile-html/{title}` | Get page content HTML optimized for mobile consumption. |
| GET | /page/mobile-html/{title}/{revision} | `/page/mobile-html/{title}/{revision}` | Get page content HTML optimized for mobile consumption. |
| GET | /page/summary/{title} | `/page/summary/{title}` | Get basic metadata and simplified article introduction. |
| GET | /page/talk/{title} | `/page/talk/{title}` | Get structured talk page contents |
| GET | /page/talk/{title}/{revision} | `/page/talk/{title}/{revision}` | Get structured talk page contents |
| GET | /page/title/{title} | `/page/title/{title}` | Get revision metadata for a title. |
| GET | /page/title/{title}/{revision} | `/page/title/{title}/{revision}` | Get revision metadata for a title. |
| POST | /transform/html/to/wikitext | `/transform/html/to/wikitext` | Transform HTML to Wikitext |
| POST | /transform/html/to/wikitext/{title} | `/transform/html/to/wikitext/{title}` | Transform HTML to Wikitext |
| POST | /transform/html/to/wikitext/{title}/{revision} | `/transform/html/to/wikitext/{title}/{revision}` | Transform HTML to Wikitext |
| POST | /transform/wikitext/to/html | `/transform/wikitext/to/html` | Transform Wikitext to HTML |
| POST | /transform/wikitext/to/html/{title} | `/transform/wikitext/to/html/{title}` | Transform Wikitext to HTML |
| POST | /transform/wikitext/to/html/{title}/{revision} | `/transform/wikitext/to/html/{title}/{revision}` | Transform Wikitext to HTML |
| POST | /transform/wikitext/to/lint | `/transform/wikitext/to/lint` | Check Wikitext for lint errors |
| POST | /transform/wikitext/to/lint/{title} | `/transform/wikitext/to/lint/{title}` | Check Wikitext for lint errors |
| POST | /transform/wikitext/to/lint/{title}/{revision} | `/transform/wikitext/to/lint/{title}/{revision}` | Check Wikitext for lint errors |
| POST | /transform/wikitext/to/mobile-html/{title} | `/transform/wikitext/to/mobile-html/{title}` | Transform Wikitext to Mobile HTML |

## mw-extra — MediaWiki REST API (routes not in modules)

**Base URL**: `https://en.wikipedia.org/w/rest.php`  
**版本**: undefined  
**端点数**: 68

| Method | Endpoint | Path Template | Summary |
|--------|----------|---------------|---------|
| DELETE | /campaignevents/v0/event_contributions/{id} | `/campaignevents/v0/event_contributions/{id}` |  |
| POST | /campaignevents/v0/event_registration | `/campaignevents/v0/event_registration` |  |
| GET | /campaignevents/v0/event_registration/{id} | `/campaignevents/v0/event_registration/{id}` |  |
| DELETE | /campaignevents/v0/event_registration/{id} | `/campaignevents/v0/event_registration/{id}` |  |
| PUT | /campaignevents/v0/event_registration/{id} | `/campaignevents/v0/event_registration/{id}` |  |
| PUT | /campaignevents/v0/event_registration/{id}/edits/{wiki}/{revid} | `/campaignevents/v0/event_registration/{id}/edits/{wiki}/{revid}` |  |
| POST | /campaignevents/v0/event_registration/{id}/email | `/campaignevents/v0/event_registration/{id}/email` |  |
| GET | /campaignevents/v0/event_registration/{id}/organizers | `/campaignevents/v0/event_registration/{id}/organizers` |  |
| PUT | /campaignevents/v0/event_registration/{id}/organizers | `/campaignevents/v0/event_registration/{id}/organizers` |  |
| GET | /campaignevents/v0/event_registration/{id}/participants | `/campaignevents/v0/event_registration/{id}/participants` |  |
| DELETE | /campaignevents/v0/event_registration/{id}/participants | `/campaignevents/v0/event_registration/{id}/participants` |  |
| PUT | /campaignevents/v0/event_registration/{id}/participants/self | `/campaignevents/v0/event_registration/{id}/participants/self` |  |
| DELETE | /campaignevents/v0/event_registration/{id}/participants/self | `/campaignevents/v0/event_registration/{id}/participants/self` |  |
| GET | /campaignevents/v0/event_registration/{id}/participants/self | `/campaignevents/v0/event_registration/{id}/participants/self` |  |
| GET | /campaignevents/v0/formatted_time/{languageCode}/{start}/{end} | `/campaignevents/v0/formatted_time/{languageCode}/{start}/{end}` |  |
| GET | /campaignevents/v0/organizer/{userid}/event_registrations | `/campaignevents/v0/organizer/{userid}/event_registrations` |  |
| GET | /campaignevents/v0/participant/self/events_for_edit | `/campaignevents/v0/participant/self/events_for_edit` |  |
| GET | /campaignevents/v0/participant/{userid}/event_registrations | `/campaignevents/v0/participant/{userid}/event_registrations` |  |
| GET | /campaignevents/v0/participant_questions | `/campaignevents/v0/participant_questions` |  |
| POST | /checkuser/v0/batch-temporaryaccount | `/checkuser/v0/batch-temporaryaccount` |  |
| POST | /checkuser/v0/connectedtemporaryaccounts/{name} | `/checkuser/v0/connectedtemporaryaccounts/{name}` |  |
| POST | /checkuser/v0/suggestedinvestigations/case/{caseId}/update | `/checkuser/v0/suggestedinvestigations/case/{caseId}/update` |  |
| POST | /checkuser/v0/temporaryaccount/ip/{ip} | `/checkuser/v0/temporaryaccount/ip/{ip}` |  |
| POST | /checkuser/v0/temporaryaccount/{name} | `/checkuser/v0/temporaryaccount/{name}` |  |
| POST | /checkuser/v0/useragent-clienthints/{type}/{id} | `/checkuser/v0/useragent-clienthints/{type}/{id}` |  |
| POST | /checkuser/v0/userinfo | `/checkuser/v0/userinfo` |  |
| GET | /checkuser/v0/userinfo/blocked/{name} | `/checkuser/v0/userinfo/blocked/{name}` |  |
| POST | /confirmedit/v0/hcaptcha/blocktoken | `/confirmedit/v0/hcaptcha/blocktoken` |  |
| POST | /eventbus/v0/internal/job/execute | `/eventbus/v0/internal/job/execute` |  |
| GET | /flaggedrevs/internal/diffheader/{oldId}/{newId} | `/flaggedrevs/internal/diffheader/{oldId}/{newId}` |  |
| POST | /flaggedrevs/internal/review/{target} | `/flaggedrevs/internal/review/{target}` |  |
| POST | /ipinfo/v0/archivedrevision/{id} | `/ipinfo/v0/archivedrevision/{id}` |  |
| POST | /ipinfo/v0/log/{id} | `/ipinfo/v0/log/{id}` |  |
| POST | /ipinfo/v0/norevision/{username} | `/ipinfo/v0/norevision/{username}` |  |
| POST | /ipinfo/v0/revision/{id} | `/ipinfo/v0/revision/{id}` |  |
| GET | /math/v0/popup/html/{qid} | `/math/v0/popup/html/{qid}` |  |
| POST | /oauth2/access_token | `/oauth2/access_token` |  |
| GET | /oauth2/authorize | `/oauth2/authorize` |  |
| POST | /oauth2/client | `/oauth2/client` |  |
| GET | /oauth2/client | `/oauth2/client` |  |
| POST | /oauth2/client/{client_key}/reset_secret | `/oauth2/client/{client_key}/reset_secret` |  |
| GET | /oauth2/resource/{type} | `/oauth2/resource/{type}` |  |
| POST | /reportincident/v0/report | `/reportincident/v0/report` |  |
| POST | /securepoll/set_translation/{entityid}/{language} | `/securepoll/set_translation/{entityid}/{language}` |  |
| GET | /v1/file/{title} | `/v1/file/{title}` | Get file |
| GET | /v1/file/{title}/thumbnails | `/v1/file/{title}/thumbnails` | Get file thumbnails |
| POST | /v1/page | `/v1/page` | Create page |
| GET | /v1/page/{title} | `/v1/page/{title}` | Get page source |
| PUT | /v1/page/{title} | `/v1/page/{title}` | Update page |
| GET | /v1/page/{title}/bare | `/v1/page/{title}/bare` | Get page |
| GET | /v1/page/{title}/history | `/v1/page/{title}/history` | Get page history |
| GET | /v1/page/{title}/history/counts/{type} | `/v1/page/{title}/history/counts/{type}` | Get page history counts |
| GET | /v1/page/{title}/html | `/v1/page/{title}/html` | Get HTML |
| GET | /v1/page/{title}/links/language | `/v1/page/{title}/links/language` | Get languages |
| GET | /v1/page/{title}/links/media | `/v1/page/{title}/links/media` | Get files on page |
| GET | /v1/page/{title}/lint | `/v1/page/{title}/lint` | Get page lint errors |
| GET | /v1/page/{title}/with_html | `/v1/page/{title}/with_html` | Get page with HTML |
| GET | /v1/revision/{from}/compare/{to} | `/v1/revision/{from}/compare/{to}` | Compare revisions |
| GET | /v1/revision/{id} | `/v1/revision/{id}` | Get revision source |
| GET | /v1/revision/{id}/bare | `/v1/revision/{id}/bare` | Get revision |
| GET | /v1/revision/{id}/html | `/v1/revision/{id}/html` | Get revision HTML |
| GET | /v1/revision/{id}/lint | `/v1/revision/{id}/lint` | Get revision lint errors |
| GET | /v1/revision/{id}/with_html | `/v1/revision/{id}/with_html` | Get revision information with HTML |
| GET | /v1/search | `/v1/search` | Get OpenSearch description document |
| GET | /v1/search/page | `/v1/search/page` | Search pages |
| GET | /v1/search/title | `/v1/search/title` | Autocomplete page title |
| POST | /v1/transform/html/to/wikitext | `/v1/transform/html/to/wikitext` | Convert HTML to Wikitext |
| POST | /v1/transform/html/to/wikitext/{title} | `/v1/transform/html/to/wikitext/{title}` | Convert HTML to Wikitext |
| POST | /v1/transform/html/to/wikitext/{title}/{revision} | `/v1/transform/html/to/wikitext/{title}/{revision}` | Convert HTML to Wikitext |
| POST | /v1/transform/wikitext/to/html | `/v1/transform/wikitext/to/html` | Convert Wikitext to HTML |
| POST | /v1/transform/wikitext/to/html/{title} | `/v1/transform/wikitext/to/html/{title}` | Convert Wikitext to HTML |
| POST | /v1/transform/wikitext/to/html/{title}/{revision} | `/v1/transform/wikitext/to/html/{title}/{revision}` | Convert Wikitext to HTML |
| POST | /v1/transform/wikitext/to/lint | `/v1/transform/wikitext/to/lint` | Return lint errors for wikitext |
| POST | /v1/transform/wikitext/to/lint/{title} | `/v1/transform/wikitext/to/lint/{title}` | Returns lint errors for wikitext |
| POST | /v1/transform/wikitext/to/lint/{title}/{revision} | `/v1/transform/wikitext/to/lint/{title}/{revision}` | Return lint errors for wikitext |
| PUT | /wikimediacampaignevents/v0/event_registration/{id}/grant_id | `/wikimediacampaignevents/v0/event_registration/{id}/grant_id` |  |
| DELETE | /wikimediacampaignevents/v0/event_registration/{id}/grant_id | `/wikimediacampaignevents/v0/event_registration/{id}/grant_id` |  |
| GET | /wikimediacampaignevents/v0/event_registration/{id}/grant_id | `/wikimediacampaignevents/v0/event_registration/{id}/grant_id` |  |

## growthexperiments.v0 — Growth experiments API

**Base URL**: `https://en.wikipedia.org/w/rest.php/growthexperiments/v0`  
**版本**: 0.1.0  
**端点数**: 9

| Method | Endpoint | Path Template | Summary |
|--------|----------|---------------|---------|
| GET | /mentees | `/mentees` |  |
| GET | /mentees/prefixsearch/{prefix} | `/mentees/prefixsearch/{prefix}` |  |
| POST | /newcomertask/complete | `/newcomertask/complete` |  |
| GET | /quickstarttips/{skin}/{editor}/{tasktypeid}/{uselang} | `/quickstarttips/{skin}/{editor}/{tasktypeid}/{uselang}` |  |
| PUT | /suggestions/addimage/feedback/{title} | `/suggestions/addimage/feedback/{title}` |  |
| GET | /suggestions/addlink/{title} | `/suggestions/addlink/{title}` |  |
| GET | /suggestions/info | `/suggestions/info` |  |
| GET | /user-impact/{user} | `/user-impact/{user}` |  |
| POST | /user-impact/{user} | `/user-impact/{user}` |  |
| POST | /welcomesurvey/skip | `/welcomesurvey/skip` |  |

## specs.v0 — Specs API

**Base URL**: `https://en.wikipedia.org/w/rest.php/specs/v0`  
**版本**: 0.1.0  
**端点数**: 3

| Method | Endpoint | Path Template | Summary |
|--------|----------|---------------|---------|
| GET | /discovery | `/discovery` |  |
| GET | /module/{module} | `/module/{module}` |  |
| GET | /module/{module}/{version} | `/module/{module}/{version}` |  |

## wmf-restbase-global — Math API (Wikimedia)

**Base URL**: `https://wikimedia.org/api/rest_v1`  
**版本**: 1.0.0  
**端点数**: 3

| Method | Endpoint | Path Template | Summary |
|--------|----------|---------------|---------|
| POST | /media/math/check/{type} | `/media/math/check/{type}` | Check and normalize a TeX formula. |
| GET | /media/math/formula/{hash} | `/media/math/formula/{hash}` | Get a previously-stored formula |
| GET | /media/math/render/{format}/{hash} | `/media/math/render/{format}/{hash}` | Get rendered formula in the given format. |

## attribution.v0-beta — Attribution API (Beta)

**Base URL**: `https://en.wikipedia.org/w/rest.php/attribution/v0-beta`  
**版本**: 0.1.0-beta  
**端点数**: 2

| Method | Endpoint | Path Template | Summary |
|--------|----------|---------------|---------|
| GET | /pages/{title}/signals | `/pages/{title}/signals` | Get attribution information for a page. |
| GET | /site/signals | `/site/signals` | Get attribution information for a site. |

---
合计：145 个 endpoint
