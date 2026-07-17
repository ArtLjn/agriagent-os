"""兼容入口：流式收尾逻辑已迁移到 app.application.chat.stream_finalization。"""

from __future__ import annotations

import sys

from app.application.chat import stream_finalization as _target

sys.modules[__name__] = _target
