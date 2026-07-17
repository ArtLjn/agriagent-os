"""DataFlywheel repair/review 子包真实入口测试。"""

from __future__ import annotations

import importlib

import pytest

pytestmark = pytest.mark.no_db

_ROOT_PREFIX = "app.platforms.data_flywheel"


@pytest.mark.parametrize(
    ("module_suffix", "target_suffix"),
    [
        ("review_issue_chain.helpers", "review_issue_chain.helpers"),
        ("review_issue_chain.case", "review_issue_chain.case"),
        ("review_issue_chain.repair", "review_issue_chain.repair"),
        ("review_issue_chain.service", "review_issue_chain.service"),
        ("repair_pack.chain", "repair_pack.chain"),
        ("repair_pack.readme", "repair_pack.readme"),
        ("repair_pack.service", "repair_pack.service"),
    ],
)
def test_repair_review_subpackage_modules_import_from_real_path(
    module_suffix: str, target_suffix: str
) -> None:
    module = importlib.import_module(f"{_ROOT_PREFIX}.{module_suffix}")

    assert module.__name__ == f"{_ROOT_PREFIX}.{target_suffix}"


def test_repair_pack_chain_real_patch_target_affects_subpackage_call(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    target_chain = importlib.import_module(f"{_ROOT_PREFIX}.repair_pack.chain")

    def fake_readme(manifest: dict[str, object]) -> str:
        return f"patched:{manifest['pack_id']}"

    monkeypatch.setattr(target_chain, "build_repair_pack_readme", fake_readme)

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
        pack_id="pack-real-patch",
        export_path="repair-packs/pack-real-patch",
    )

    assert payload["readme"] == "patched:pack-real-patch"


def test_review_issue_chain_case_real_patch_target_affects_repair_call(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    target_case = importlib.import_module(f"{_ROOT_PREFIX}.review_issue_chain.case")
    target_repair_pack = importlib.import_module(f"{_ROOT_PREFIX}.repair_pack.chain")

    def fake_case_json(*, chain_id: str, detail: dict[str, object]) -> dict[str, str]:
        return {"case_id": f"patched-{chain_id}"}

    monkeypatch.setattr(target_case, "build_chain_case_json", fake_case_json)

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
