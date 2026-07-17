"""兼容入口：流式聊天 use case 已迁移到 app.application.chat.stream_chat。"""

from __future__ import annotations

import sys

from app.application.chat import stream_chat as _target

sys.modules[__name__] = _target
