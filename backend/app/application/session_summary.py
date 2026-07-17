"""兼容入口：会话摘要已迁移到 app.application.session.summary。"""

from __future__ import annotations

import sys

from app.application.session import summary as _target

sys.modules[__name__] = _target
