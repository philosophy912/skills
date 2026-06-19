#!/usr/bin/env python3
"""cat-video-analyzer 命令入口（跨平台）。

定位本脚本所在 skill 目录并加入 sys.path，使 `from scripts.run import main`
可用，随后转发命令行参数。这样 agent 在任意工作目录、任意 OS（Windows /
Linux / macOS）上都可用：

    python3 catva.py <子命令> [...]

调用，无需关心 PYTHONPATH 或工作目录。

由 SKILL.md 通过 ${CLAUDE_PLUGIN_ROOT}/skills/cat-video-analyzer/scripts/catva.py 调用。
"""
import sys
from pathlib import Path

# scripts/ 的父目录 = skill 根目录（含 scripts/ 包）
_SKILL_DIR = Path(__file__).resolve().parent.parent
if str(_SKILL_DIR) not in sys.path:
    sys.path.insert(0, str(_SKILL_DIR))

from scripts.run import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
