"""兼容入口：流式聊天类型已迁移到 app.application.chat.stream_types。"""

from __future__ import annotations

import sys

from app.application.chat import stream_types as _target

sys.modules[__name__] = _target
