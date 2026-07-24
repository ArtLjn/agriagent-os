"""工具执行结构化日志测试。"""

import logging
from unittest.mock import MagicMock

from langchain_core.messages import ToolMessage

from app.agent.runtime.tool_executor import _validation_error_message
from app.agent.runtime.tool_metadata import _PermissionDecision
from app.agent.runtime.tool_pending import _pending_plan_tool_message


class _InvalidArgsSchema:
    @classmethod
    def model_validate(cls, _args):
        raise ValueError("第一行\n第二行")


def test_tool_args_validation_error_logs_stable_event_fields(caplog):
    """工具参数错误日志应有稳定事件字段，并压平成单行。"""
    tool = MagicMock()
    tool.args_schema = _InvalidArgsSchema
    collector = MagicMock()

    with caplog.at_level(logging.WARNING, logger="app.agent.runtime.tool_executor"):
        message = _validation_error_message(
            tool=tool,
            name="manage_workers",
            args={"action": "create"},
            tool_call_id="tc-1",
            permission_decision=_PermissionDecision(
                permission_level="write_confirm",
                requires_confirmation=True,
                capability="manage_workers",
                operation="manage_worker",
                operation_risk="write_confirm",
            ),
            collector=collector,
        )

    assert isinstance(message, ToolMessage)
    log_message = caplog.records[0].getMessage()
    assert "event=tool_args_validation_error" in log_message
    assert "code=tool_args_validation_error" in log_message
    assert "step_id=tool-call-tc-1" in log_message
    assert "status=failed" in log_message
    assert "tool=manage_workers" in log_message
    assert "error=第一行 第二行" in log_message


def test_pending_plan_contract_block_logs_root_cause_fields(monkeypatch, caplog):
    """pending plan 参数阻塞应输出可 grep 的根因字段。"""
    monkeypatch.setattr(
        "app.agent.runtime.tool_arg_validation.load_skill_candidates",
        lambda _farm_id: type("CandidateSet", (), {"values": {}})(),
    )
    monkeypatch.setattr(
        "app.agent.runtime.tool_pending.get_collector",
        lambda: MagicMock(),
    )
    state = {
        "session_id": "session-1",
        "plan_draft": {
            "route_type": "write_pending_plan",
            "validation": {"status": "valid"},
            "steps": [
                {
                    "step_id": "create_worker",
                    "skill_name": "manage_workers",
                    "params": {
                        "action": "create",
                        "default_pay_type": "daily",
                        "default_unit_price": "100",
                    },
                    "depends_on": [],
                }
            ],
        },
    }

    with caplog.at_level(logging.WARNING, logger="app.agent.runtime.tool_pending"):
        messages = _pending_plan_tool_message(
            state=state,
            farm_id=1,
            original_input="我招了张三，工资100一天",
            tool_calls=[
                {
                    "id": "tc-1",
                    "name": "manage_workers",
                    "args": {"action": "create"},
                }
            ],
        )

    assert messages is not None
    log_message = caplog.records[0].getMessage()
    assert "event=pending_plan_contract_blocked" in log_message
    assert "code=pending_plan_contract_blocked" in log_message
    assert "step_id=pending-plan-contract-create_worker" in log_message
    assert "status=blocked" in log_message
    assert "tool=manage_workers" in log_message
    assert "missing_fields=name" in log_message
