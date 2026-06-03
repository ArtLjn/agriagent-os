"""测试评测用例加载。"""

from pathlib import Path

from app.evaluation.cases.loader import load_simulation_cases


def test_load_simulation_cases_reuses_existing_json() -> None:
    cases = load_simulation_cases(Path("data/simulation_cases"), category="basic")

    assert cases
    first_case = cases[0]
    assert first_case.user_input
    assert first_case.metadata["source"] == "simulation"
    assert first_case.reply_assertions
    assert any(write.table for write in first_case.expected_writes)
