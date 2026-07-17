"""兼容入口：历史记录 use case 已迁移到 app.application.session.history。"""

from __future__ import annotations

import sys

from app.application.session import history as _target

sys.modules[__name__] = _target
