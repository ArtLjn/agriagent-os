"""兼容入口：流式尾部事件已迁移到 app.application.chat.stream_tail。"""

from __future__ import annotations

import sys

from app.application.chat import stream_tail as _target

sys.modules[__name__] = _target
