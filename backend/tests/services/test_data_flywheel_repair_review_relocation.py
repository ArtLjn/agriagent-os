"""DataFlywheel repair/review 子包归位兼容测试。"""

from __future__ import annotations

import importlib

import pytest

pytestmark = pytest.mark.no_db

_ROOT_PREFIX = "app.platforms.data_flywheel"


@pytest.mark.parametrize(
    ("legacy_suffix", "target_suffix"),
    [
        ("review_issue_chain_helpers", "review_issue_chain.helpers"),
        ("review_issue_chain_case", "review_issue_chain.case"),
        ("review_issue_chain_repair", "review_issue_chain.repair"),
        ("review_issue_chain_service", "review_issue_chain.service"),
        ("repair_pack_chain", "repair_pack.chain"),
        ("repair_pack_readme", "repair_pack.readme"),
        ("repair_pack_service", "repair_pack.service"),
    ],
)
def test_platform_root_repair_review_imports_resolve_to_subpackage_module(
    legacy_suffix: str, target_suffix: str
) -> None:
    legacy = importlib.import_module(f"{_ROOT_PREFIX}.{legacy_suffix}")
    target = importlib.import_module(f"{_ROOT_PREFIX}.{target_suffix}")

    assert legacy is target


def test_legacy_repair_pack_chain_patch_target_affects_subpackage_call(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    legacy_chain = importlib.import_module(f"{_ROOT_PREFIX}.repair_pack_chain")
    target_chain = importlib.import_module(f"{_ROOT_PREFIX}.repair_pack.chain")

    def fake_readme(manifest: dict[str, object]) -> str:
        return f"patched:{manifest['pack_id']}"

    monkeypatch.setattr(legacy_chain, "build_repair_pack_readme", fake_readme)

    payload = target_chain.build_chain_repair_pack_payload(
        {
            "chain": {
                "chain_id": "chain:1:s1:10",
                "session_id": "s1",
                "trigger_turn_id": 10,
                "context_turn_ids": [9],
                "result_turn_ids": [11],
                "status": "accepted",
                "human_review": {"expected_behavior": "必须保持批量对象"},
                "diagnosis": {"candidate_type": "tool_parameter_mismatch"},
            },
            "timeline": [],
            "evidence_checklist": [],
        },
        pack_id="pack-legacy-patch",
        export_path="repair-packs/pack-legacy-patch",
    )

    assert payload["readme"] == "patched:pack-legacy-patch"


def test_legacy_review_issue_chain_case_patch_target_affects_repair_call(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    legacy_case = importlib.import_module(f"{_ROOT_PREFIX}.review_issue_chain_case")
    target_repair_pack = importlib.import_module(f"{_ROOT_PREFIX}.repair_pack.chain")

    def fake_case_json(*, chain_id: str, detail: dict[str, object]) -> dict[str, str]:
        return {"case_id": f"patched-{chain_id}"}

    monkeypatch.setattr(legacy_case, "build_chain_case_json", fake_case_json)

    payload = target_repair_pack.build_chain_repair_pack_payload(
        {
            "chain": {
                "chain_id": "chain:1:s1:10",
                "session_id": "s1",
                "trigger_turn_id": 10,
                "context_turn_ids": [9],
                "result_turn_ids": [11],
                "status": "accepted",
                "human_review": {"expected_behavior": "必须保持批量对象"},
                "diagnosis": {"candidate_type": "tool_parameter_mismatch"},
            },
            "timeline": [],
            "evidence_checklist": [],
        },
        pack_id="pack-case-patch",
        export_path="repair-packs/pack-case-patch",
    )

    assert (
        "regression-drafts/patched-chain_1_s1_10.json" in payload["regression_drafts"]
    )
