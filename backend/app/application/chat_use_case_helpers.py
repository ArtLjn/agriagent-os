"""兼容入口：聊天辅助函数已迁移到 app.application.chat.helpers。"""

from __future__ import annotations

import sys

from app.application.chat import helpers as _target

sys.modules[__name__] = _target
