"""兼容入口：流式持久化逻辑已迁移到 app.application.chat.stream_persistence。"""

from __future__ import annotations

import sys

from app.application.chat import stream_persistence as _target

sys.modules[__name__] = _target
