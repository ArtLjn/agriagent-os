"""兼容入口：报告 Agent 已迁移到 app.application.report。"""

from __future__ import annotations

import sys

from app.application import report as _target

sys.modules[__name__] = _target
