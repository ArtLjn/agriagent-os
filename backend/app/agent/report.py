"""兼容入口：报告 Agent 已迁移到 app.agent.application.report。"""

from __future__ import annotations

import sys

from app.agent.application import report as _target

sys.modules[__name__] = _target
