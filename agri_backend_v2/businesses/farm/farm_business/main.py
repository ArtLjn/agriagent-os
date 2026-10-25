"""Business MCP Server 启动入口。

推荐从 agri_backend_v2/ 运行：
    uv run --package farm-manager-business python -m farm_business.main

也支持在 farm_business/ 目录直接执行：
    python main.py
"""
from __future__ import annotations

import sys
from pathlib import Path

# 直接执行时把业务项目根和 shared 源码根加入 sys.path；包安装后这两步是幂等的。
_BUSINESS_PROJECT = Path(__file__).resolve().parents[1]
_SHARED_PROJECT = Path(__file__).resolve().parents[3] / "shared"
for _path in (_BUSINESS_PROJECT, _SHARED_PROJECT):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

from farm_business.server import main

if __name__ == "__main__":
    main()
