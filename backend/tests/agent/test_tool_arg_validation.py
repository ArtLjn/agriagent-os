from types import SimpleNamespace
from unittest.mock import MagicMock

from langchain_core.messages import ToolMessage

from app.agent.runtime.tool_arg_validation import validate_before_pending
from app.agent.runtime.tool_metadata import _PermissionDecision
from app.agent.runtime.tool_pending import (
    _pending_action_message,
    _pending_action_precheck,
)


def test_validate_before_pending_reports_missing_required_field(monkeypatch):
    monkeypatch.setattr(
        "app.agent.runtime.tool_arg_validation.load_skill_candidates",
        lambda _farm_id: SimpleNamespace(values={"category": ["化肥", "种子"]}),
    )

    result = validate_before_pending(
        "manage_cost",
        {
            "operation": "create_record",
            "amount": 5000,
            "record_type": "cost",
        },
        farm_id=1,
    )

    assert result.valid is False
    assert result.missing_fields == ["category"]
    assert (
        result.message == "create_record 缺少必填字段：category，请补充后我再为你确认。"
    )
    assert result.to_trace_payload()["message"] == result.message


def test_validate_before_pending_infers_canonical_write_operation(monkeypatch):
    monkeypatch.setattr(
        "app.agent.runtime.tool_arg_validation.load_skill_candidates",
        lambda _farm_id: SimpleNamespace(values={"category": ["化肥", "种子"]}),
    )

    result = validate_before_pending(
        "manage_cost",
        {
            "amount": 5000,
            "record_type": "cost",
        },
        farm_id=1,
    )

    assert result.valid is False
    assert result.params["operation"] == "create_record"
    assert result.missing_fields == ["category"]


def test_validate_before_pending_repairs_invalid_other_category_to_broad_candidate(
    monkeypatch,
):
    monkeypatch.setattr(
        "app.agent.runtime.tool_arg_validation.load_skill_candidates",
        lambda _farm_id: SimpleNamespace(values={"category": ["农资", "化肥"]}),
    )

    result = validate_before_pending(
        "manage_cost",
        {
            "operation": "create_record",
            "amount": 5000,
            "category": "其他",
            "record_type": "cost",
            "note": "大棚膜采购",
        },
        farm_id=1,
    )

    assert result.valid is True
    assert result.params["category"] == "农资"
    assert result.params["_category_repair_strategy"] == "dynamic_consolidation"


def test_pending_action_precheck_blocks_missing_category_before_confirmation(
    monkeypatch,
):
    monkeypatch.setattr(
        "app.agent.runtime.tool_arg_validation.load_skill_candidates",
        lambda _farm_id: SimpleNamespace(values={"category": ["化肥", "种子"]}),
    )
    ambiguous_check = MagicMock(return_value=None)
    build_confirmation = MagicMock(return_value=({"unused": True}, "不应生成确认"))
    monkeypatch.setattr(
        "app.agent.runtime.tool_pending._ambiguous_pending_message",
        ambiguous_check,
    )
    monkeypatch.setattr(
        "app.agent.runtime.tool_pending._build_pending_confirmation",
        build_confirmation,
    )
    collector = MagicMock()

    message, confirmation_context, confirm_text = _pending_action_precheck(
        state={"session_id": "session-1"},
        name="manage_cost",
        execution_args={
            "operation": "create_record",
            "amount": 5000,
            "record_type": "cost",
        },
        original_input="刚才买了点大棚膜5000元",
        farm_id=1,
        tool_call_id="call-1",
        permission_decision=_PermissionDecision(
            permission_level="write_confirm",
            requires_confirmation=True,
            capability="manage_cost",
            operation="create_record",
            operation_risk="write_confirm",
        ),
        collector=collector,
    )

    assert isinstance(message, ToolMessage)
    assert message.tool_call_id == "call-1"
    assert "create_record 缺少必填字段：category" in message.content
    assert "请补充" in message.content
    assert confirmation_context is None
    assert confirm_text is None
    ambiguous_check.assert_called_once()
    build_confirmation.assert_not_called()
    collector.record.assert_called_once()
    record_kwargs = collector.record.call_args.kwargs
    assert record_kwargs["node_type"] == "skill_call"
    assert record_kwargs["node_name"] == "manage_cost"
    assert record_kwargs["input_data"]["amount"] == 5000
    output_data = record_kwargs["output_data"]
    assert output_data["status"] == "contract_blocked"
    assert output_data["contract_validation"]["missing_fields"] == ["category"]
    assert output_data["permission_level"] == "write_confirm"
    assert output_data["resolved_capability"] == "manage_cost"
    assert output_data["resolved_operation"] == "create_record"


def test_pending_action_message_does_not_store_when_contract_blocked(monkeypatch):
    monkeypatch.setattr(
        "app.agent.runtime.tool_arg_validation.load_skill_candidates",
        lambda _farm_id: SimpleNamespace(values={"category": ["化肥", "种子"]}),
    )
    store_pending_action = MagicMock()
    monkeypatch.setattr(
        "app.agent.runtime.tool_pending._store_pending_action_message",
        store_pending_action,
    )

    message = _pending_action_message(
        state={"session_id": "session-1"},
        name="manage_cost",
        args={
            "operation": "create_record",
            "amount": 5000,
            "record_type": "cost",
        },
        farm_id=1,
        original_input="刚才买了点大棚膜5000元",
        tool_call_id="call-1",
        permission_decision=_PermissionDecision(
            permission_level="write_confirm",
            requires_confirmation=True,
        ),
        collector=MagicMock(),
        logger=MagicMock(),
    )

    assert isinstance(message, ToolMessage)
    assert "缺少必填字段：category" in message.content
    store_pending_action.assert_not_called()
