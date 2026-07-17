"""旧删茬口 operation 模块兼容入口。"""

import importlib
import sys

_target = importlib.import_module("app.skills.manage-crop-cycle.scripts.main")
sys.modules[__name__] = _target
