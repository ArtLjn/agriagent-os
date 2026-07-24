from types import SimpleNamespace

from app.agent.executor.tool_failure_reflection import reflect_tool_failure


def test_reflect_tool_failure_repairs_missing_category_from_dynamic_candidates(
    monkeypatch,
):
    monkeypatch.setattr(
        "app.agent.executor.tool_failure_reflection.load_skill_candidates",
        lambda _farm_id: SimpleNamespace(
            values={"category": ["化肥", "大棚膜", "其他"]}
        ),
    )

    decision = reflect_tool_failure(
        farm_id=1,
        skill_name="manage_cost",
        params={
            "operation": "create_record",
            "amount": 5000,
            "record_type": "cost",
            "note": "买了大棚膜5000元",
        },
        result=SimpleNamespace(status="failed", reply="记账失败：分类不能为空。"),
        repair_attempts=0,
    )

    assert decision.action == "ask_repaired_confirmation"
    assert decision.repaired_params["category"] == "大棚膜"
    assert decision.repair_attempts == 1
    assert "分类不能为空" in decision.reply
    assert "大棚膜" in decision.confirmation_text


def test_reflect_tool_failure_repairs_missing_category_to_other(monkeypatch):
    monkeypatch.setattr(
        "app.agent.executor.tool_failure_reflection.load_skill_candidates",
        lambda _farm_id: SimpleNamespace(values={"category": ["化肥", "种子", "其他"]}),
    )

    decision = reflect_tool_failure(
        farm_id=1,
        skill_name="manage_cost",
        params={
            "operation": "create_record",
            "amount": 5000,
            "record_type": "cost",
            "note": "买了大棚膜5000元",
        },
        result=SimpleNamespace(status="failed", reply="记账失败：分类不能为空。"),
        repair_attempts=0,
    )

    assert decision.action == "ask_repaired_confirmation"
    assert decision.repaired_params["category"] == "其他"
    assert decision.repair_attempts == 1
    assert "分类不能为空" in decision.reply
    assert "其他" in decision.confirmation_text


def test_reflect_tool_failure_stops_after_repair_limit():
    decision = reflect_tool_failure(
        farm_id=1,
        skill_name="manage_cost",
        params={
            "operation": "create_record",
            "amount": 5000,
            "record_type": "cost",
            "note": "买了大棚膜5000元",
        },
        result=SimpleNamespace(status="failed", reply="记账失败：分类不能为空。"),
        repair_attempts=1,
    )

    assert decision.action == "no_repair"
    assert decision.repaired_params is None
