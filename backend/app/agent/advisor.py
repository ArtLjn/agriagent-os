"""兼容入口：建议 Agent 已迁移到 app.application.advisor。"""

from __future__ import annotations

import sys

from app.application import advisor as _target

sys.modules[__name__] = _target
