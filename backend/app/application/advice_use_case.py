"""兼容入口：建议 use case 已迁移到 app.application.advice.use_case。"""

from __future__ import annotations

import sys

from app.application.advice import use_case as _target

sys.modules[__name__] = _target
