#!/usr/bin/env bash
# setup_config.sh — 引导式生成 ~/.wikipedia_restapi.json 配置文件
# 用法：bash setup_config.sh

set -e

CONFIG="$HOME/.wikipedia_restapi.json"

echo "=============================================="
echo "  Wikipedia REST API — 配置文件设置"
echo "=============================================="
echo ""

# ── 1) 代理地址 ──
echo "[1/2] HTTP 代理地址（用于访问 Wikipedia，留空用默认值）"
if [[ -f "$CONFIG" ]]; then
  old_proxy=$(python3 -c "import json; print(json.load(open(r'$CONFIG')).get('proxy',''))" 2>/dev/null || echo "")
  [[ -n "$old_proxy" ]] && echo "  当前值: $old_proxy"
fi
printf "  proxy [http://127.0.0.1:16780]: "
read -r proxy
proxy="${proxy:-http://127.0.0.1:16780}"

# ── 2) 语言 ──
echo ""
echo "[2/2] 默认 Wikipedia 语言（en=英文 / zh=中文 / ja=日文 / fr=法文 / de=德文 ...）"
if [[ -f "$CONFIG" ]]; then
  old_lang=$(python3 -c "import json; print(json.load(open(r'$CONFIG')).get('lang',''))" 2>/dev/null || echo "")
  [[ -n "$old_lang" ]] && echo "  当前值: $old_lang"
fi
printf "  lang [en]: "
read -r lang
lang="${lang:-en}"

# ── 写入 ──
python3 -c "
import json
cfg = {'proxy': r'${proxy}', 'lang': r'${lang}'}
with open(r'${CONFIG}', 'w') as f:
    json.dump(cfg, f, indent=2)
    f.write('\n')
" 2>/dev/null || {
  # 回退：手动 echo
  cat > "$CONFIG" <<CFGEOF
{
  "proxy": "${proxy}",
  "lang": "${lang}"
}
CFGEOF
}

echo ""
echo "=============================================="
echo "  配置已写入 $CONFIG"
cat "$CONFIG"
echo "=============================================="
echo ""
echo "现在你可以直接运行："
echo '  scripts/wikipedia_api.sh wmf-restbase GET page-summary "Berlin"'
echo ""
echo "如需临时覆盖："
echo "  WIKI_PROXY=http://other:8080 WIKI_LANG=zh scripts/wikipedia_api.sh ..."
