"""兼容入口：Skill 覆盖矩阵已迁移到 app.platforms.evaluation.skill_coverage。"""

from __future__ import annotations

import sys

from app.platforms.evaluation import skill_coverage as _target

sys.modules[__name__] = _target
