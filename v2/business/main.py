"""Business MCP Server 启动入口。

直接运行：
    cd v2/business
    python main.py

或作为模块运行：
    python -m business.server
"""
from __future__ import annotations

import sys
from pathlib import Path

# 允许从 v2/business/ 直接 `python main.py`：把 v2/ 父目录加入 sys.path
_PARENT = str(Path(__file__).resolve().parent.parent)
if _PARENT not in sys.path:
    sys.path.insert(0, _PARENT)

from business.server import main  # noqa: E402


if __name__ == "__main__":
    main()

