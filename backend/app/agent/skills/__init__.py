"""旧 `app.agent.skills` 入口兼容层。

真实 Skill 实现已迁移到 `app.skills`。这里保留到 C4 迁移完成前，用于兼容
旧动态 import 与 monkeypatch target，并确保旧路径解析到同一模块对象。
"""

from __future__ import annotations

import importlib
import importlib.abc
import importlib.machinery
import importlib.util
import sys
from types import ModuleType

_OLD_PREFIX = __name__
_NEW_PREFIX = "app.skills"


class _SkillAliasLoader(importlib.abc.Loader):
    def __init__(self, fullname: str, target_name: str) -> None:
        self.fullname = fullname
        self.target_name = target_name

    def create_module(self, spec: importlib.machinery.ModuleSpec) -> ModuleType:
        module = importlib.import_module(self.target_name)
        sys.modules[self.fullname] = module
        return module

    def exec_module(self, module: ModuleType) -> None:
        return None


class _SkillAliasFinder(importlib.abc.MetaPathFinder):
    def find_spec(
        self,
        fullname: str,
        path: object | None,
        target: ModuleType | None = None,
    ) -> importlib.machinery.ModuleSpec | None:
        if not fullname.startswith(f"{_OLD_PREFIX}."):
            return None

        target_name = f"{_NEW_PREFIX}{fullname[len(_OLD_PREFIX):]}"
        target_spec = importlib.util.find_spec(target_name)
        if target_spec is None:
            return None

        spec = importlib.machinery.ModuleSpec(
            fullname,
            _SkillAliasLoader(fullname, target_name),
            is_package=target_spec.submodule_search_locations is not None,
        )
        spec.origin = target_spec.origin
        spec.submodule_search_locations = target_spec.submodule_search_locations
        return spec


def _install_alias_finder() -> None:
    for finder in sys.meta_path:
        if isinstance(finder, _SkillAliasFinder):
            return
    sys.meta_path.insert(0, _SkillAliasFinder())


_install_alias_finder()
_target = importlib.import_module(_NEW_PREFIX)
sys.modules[_OLD_PREFIX] = _target
