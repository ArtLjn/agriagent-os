"""兼容入口：会话飞轮已迁移到 app.application.session.flywheel。"""

from __future__ import annotations

import sys

from app.application.session import flywheel as _target

sys.modules[__name__] = _target
