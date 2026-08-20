"""Skill Loader 聚合配置审计入口和 Runtime 展开入口契约测试。"""

from agent.domains.harness.tools import loader


def test_aggregate_loader_keeps_mixed_skill_for_risk_audit() -> None:
    skills = loader.load_aggregate_skills()
    by_name = {skill.name: skill for skill in skills}

    manage_farm_logs = by_name["manage_farm_logs"]
    assert (
        manage_farm_logs.dynamic_risk_level({"operation": "create"}) == "write_confirm"
    )


def test_runtime_loader_keeps_operation_followups_expanded() -> None:
    skills = loader.load_all()
    names = {skill.name for skill in skills}

    assert "manage_farm_logs" not in names
    assert "query_farm_logs" in names
    assert "commit_planting_plan" in names
