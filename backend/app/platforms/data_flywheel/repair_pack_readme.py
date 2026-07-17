"""旧 root import 兼容入口，真实实现已归位到子包。"""

from __future__ import annotations

import importlib
import sys

_target = importlib.import_module("app.platforms.data_flywheel.repair_pack.readme")
sys.modules[__name__] = _target
