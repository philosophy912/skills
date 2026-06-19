#!/usr/bin/env python3
"""setup_config.py — 引导式生成 ~/.wikipedia_restapi.json（跨平台 Python 版）。

用法：python3 setup_config.py
"""
import json
from pathlib import Path

CONFIG = Path.home() / ".wikipedia_restapi.json"

DEFAULT_PROXY = "http://127.0.0.1:16780"
DEFAULT_LANG = "en"


def main() -> int:
    print("==============================================")
    print("  Wikipedia REST API — 配置文件设置")
    print("==============================================")
    print()

    existing: dict = {}
    if CONFIG.exists():
        try:
            existing = json.loads(CONFIG.read_text(encoding="utf-8"))
        except Exception:
            existing = {}

    # ── 1) 代理地址 ──
    old_proxy = existing.get("proxy", "")
    print("[1/2] HTTP 代理地址（用于访问 Wikipedia，留空用默认值）")
    if old_proxy:
        print(f"  当前值: {old_proxy}")
    proxy = input(f"  proxy [{DEFAULT_PROXY}]: ").strip() or DEFAULT_PROXY

    # ── 2) 语言 ──
    old_lang = existing.get("lang", "")
    print()
    print("[2/2] 默认 Wikipedia 语言（en=英文 / zh=中文 / ja=日文 / fr=法文 / de=德文 ...）")
    if old_lang:
        print(f"  当前值: {old_lang}")
    lang = input(f"  lang [{DEFAULT_LANG}]: ").strip() or DEFAULT_LANG

    cfg = {"proxy": proxy, "lang": lang}
    CONFIG.write_text(
        json.dumps(cfg, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )

    print()
    print("==============================================")
    print(f"  配置已写入 {CONFIG}")
    print(json.dumps(cfg, indent=2, ensure_ascii=False))
    print("==============================================")
    print()
    print("现在你可以直接运行：")
    print('  python3 wikipedia_api.py wmf-restbase GET page-summary "Berlin"')
    print()
    print("如需临时覆盖：")
    print("  WIKI_PROXY=http://other:8080 WIKI_LANG=zh python3 wikipedia_api.py ...")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
