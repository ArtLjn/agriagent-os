"""测试评测用例加载。"""

from pathlib import Path

from app.evaluation.cases.loader import builtin_skill_regression_cases, load_replay_cases, load_simulation_cases


def test_load_simulation_cases_reuses_existing_json() -> None:
    cases = load_simulation_cases(Path("data/simulation_cases"), category="basic")

    assert cases
    first_case = cases[0]
    assert first_case.user_input
    assert first_case.metadata["source"] == "simulation"
    assert first_case.reply_assertions
    assert any(write.table for write in first_case.expected_writes)


def test_load_replay_case_supports_pending_confirmation_and_db_diff(tmp_path) -> None:
    path = tmp_path / "cases.json"
    path.write_text(
        """
[
  {
    "case_id": "case-1",
    "user_input": "把玉米茬口改成9月1开始",
    "expected_skills": [{"name": "update_crop_cycle", "arguments": {"start_date": "2026-09-01"}}],
    "expected_parameters": {"start_date": "2026-09-01"},
    "expected_pending_action": {"skill_name": "update_crop_cycle", "params": {"start_date": "2026-09-01"}},
    "confirmation_flow": [{"user_input": "确认", "expected_status": "confirmed"}],
    "expected_database_diff": [{"table": "crop_cycles", "operation": "update", "after": {"start_date": "2026-09-01"}}]
  }
]
""",
        encoding="utf-8",
    )

    case = load_replay_cases(path)[0]

    assert case.expected_skills[0].name == "update_crop_cycle"
    assert case.expected_parameters["start_date"] == "2026-09-01"
    assert case.expected_pending_action.skill_name == "update_crop_cycle"
    assert case.confirmation_flow[0].expected_status == "confirmed"
    assert case.expected_database_diff[0].table == "crop_cycles"


def test_builtin_skill_regression_cases_cover_required_domains() -> None:
    cases = builtin_skill_regression_cases()
    case_ids = {case.case_id for case in cases}

    assert {
        "crop-cycle-update-start-date",
        "work-order-create",
        "work-order-correction",
        "unpaid-labor-query",
        "labor-settlement",
        "cost-record-correction",
        "weather-query",
    }.issubset(case_ids)
    assert any(case.expected_pending_action for case in cases)
    assert any(case.expected_database_diff for case in cases)
