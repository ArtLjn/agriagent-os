"""Business MCP Server 启动入口。

从 agri_backend_v2/ 目录运行：
    uv run --package farm-manager-business python -m farm_business.main
"""
from __future__ import annotations

from farm_business.server import main

if __name__ == "__main__":
    main()
