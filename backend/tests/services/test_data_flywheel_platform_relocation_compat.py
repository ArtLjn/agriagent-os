"""DataFlywheel 平台迁移兼容入口测试。"""

from __future__ import annotations

import importlib
import os
import subprocess
import sys
import textwrap

import pytest

pytestmark = pytest.mark.no_db

_LEGACY_PREFIX = "app.modules.data_flywheel"
_PLATFORM_PREFIX = "app.platforms.data_flywheel"

_ALIASED_MODULES = [
    "service",
    "router",
    "annotations_router",
    "repair_packs_router",
    "review_issue_chains_router",
    "document_repositories",
    "document_repository_selector",
    "repair_pack_repository",
    "repair_pack_chain",
    "repair_pack_readme",
    "repair_pack_service",
    "review_issue_chain_case",
    "review_issue_chain_helpers",
    "review_issue_chain_repair",
    "review_issue_chain_service",
    "judge_service",
]


def test_legacy_data_flywheel_package_resolves_to_platform_package() -> None:
    legacy = importlib.import_module(_LEGACY_PREFIX)
    platform = importlib.import_module(_PLATFORM_PREFIX)

    assert legacy is platform


@pytest.mark.parametrize("module_suffix", _ALIASED_MODULES)
def test_legacy_data_flywheel_imports_resolve_to_platform_module(
    module_suffix: str,
) -> None:
    legacy = importlib.import_module(f"{_LEGACY_PREFIX}.{module_suffix}")
    platform = importlib.import_module(f"{_PLATFORM_PREFIX}.{module_suffix}")

    assert legacy is platform


def test_legacy_first_import_does_not_duplicate_platform_modules() -> None:
    module_list = ", ".join(repr(module_suffix) for module_suffix in _ALIASED_MODULES)
    code = textwrap.dedent(
        f"""
        import importlib
        import sys

        legacy_package = importlib.import_module("app.modules.data_flywheel")
        platform_package = importlib.import_module("app.platforms.data_flywheel")
        assert legacy_package is platform_package

        for module_suffix in [{module_list}]:
            legacy = importlib.import_module(
                f"app.modules.data_flywheel.{{module_suffix}}"
            )
            platform = importlib.import_module(
                f"app.platforms.data_flywheel.{{module_suffix}}"
            )
            assert legacy is platform, module_suffix
            assert (
                sys.modules[f"app.modules.data_flywheel.{{module_suffix}}"]
                is platform
            ), module_suffix
            assert (
                sys.modules[f"app.platforms.data_flywheel.{{module_suffix}}"]
                is platform
            ), module_suffix
        """
    )
    env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}

    result = subprocess.run(
        [sys.executable, "-c", code],
        check=False,
        cwd=os.getcwd(),
        env=env,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
