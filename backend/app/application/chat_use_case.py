"""兼容入口：聊天 use case 已迁移到 app.application.chat.use_case。"""

from __future__ import annotations

import sys

from app.application.chat import use_case as _target

sys.modules[__name__] = _target
