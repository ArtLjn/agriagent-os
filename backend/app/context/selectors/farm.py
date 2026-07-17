"""旧农场 selector 模块兼容入口。"""

import importlib
import sys

_target = importlib.import_module("app.context.selectors.core")
sys.modules[__name__] = _target
