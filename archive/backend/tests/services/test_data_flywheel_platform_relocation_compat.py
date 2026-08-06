"""DataFlywheel 平台真实入口测试。"""

from __future__ import annotations

import importlib

import pytest

pytestmark = pytest.mark.no_db

_PLATFORM_PREFIX = "app.platforms.data_flywheel"
_SHARED_PREFIX = "app.platforms.shared"

_PLATFORM_MODULES = [
    "service",
    "router",
    "annotations_router",
    "repair_packs_router",
    "review_issue_chains_router",
    "document_repositories",
    "repair_pack_repository",
    "review_issue_chain_repository",
    "issue_repository",
    "session_sync_service",
    "session_review_service",
    "repair_pack.chain",
    "repair_pack.readme",
    "repair_pack.service",
    "review_issue_chain.case",
    "review_issue_chain.helpers",
    "review_issue_chain.repair",
    "review_issue_chain.service",
]

_SHARED_MODULES = ["judge_service", "repository_selector"]


def test_data_flywheel_package_imports_from_platform_path() -> None:
    platform = importlib.import_module(_PLATFORM_PREFIX)

    assert platform.__name__ == _PLATFORM_PREFIX


@pytest.mark.parametrize("module_suffix", _PLATFORM_MODULES)
def test_data_flywheel_modules_import_from_real_path(
    module_suffix: str,
) -> None:
    platform = importlib.import_module(f"{_PLATFORM_PREFIX}.{module_suffix}")

    assert platform.__name__ == f"{_PLATFORM_PREFIX}.{module_suffix}"


@pytest.mark.parametrize("module_suffix", _SHARED_MODULES)
def test_shared_platform_modules_use_real_path(module_suffix: str) -> None:
    shared = importlib.import_module(f"{_SHARED_PREFIX}.{module_suffix}")

    assert shared.__name__ == f"{_SHARED_PREFIX}.{module_suffix}"
