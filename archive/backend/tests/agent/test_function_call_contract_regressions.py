from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from skillify.models.schemas import ResultStatus, SkillResult

from app.agent.executor.pending_actions import (
    _confirm_pending_plan,
    handle_pending_action,
)
from app.agent.reflector import ReflectionDecision
from app.agent.runtime.tool_pending import _pending_plan_tool_message
from app.infra.pending_actions import (
    PENDING_MARKER,
    PendingPlan,
    PendingPlanStep,
    _pending,
    _pending_plans,
    get_pending,
    store_pending,
)


@pytest.fixture(autouse=True)
def clean_pending_action():
    _clear_test_pending()
    yield
    _clear_test_pending()


def _clear_test_pending() -> None:
    for session_id in (
        "contract-confirm",
        "contract-repair",
        "contract-plan-create",
        "contract-plan-failure",
        "contract-plan-tool-call-args",
    ):
        _pending.pop((1, session_id), None)
        _pending_plans.pop((1, session_id), None)


class _PassReflection:
    decision = ReflectionDecision.PASS
    reason = ""

    def to_trace_payload(self) -> dict:
        return {}


@pytest.mark.asyncio
async def test_confirm_pending_missing_category_does_not_execute_raw_skill(monkeypatch):
    store_pending(
        1,
        "manage_cost",
        {"operation": "create_record", "amount": 5000, "record_type": "cost"},
        original_input="买了大棚膜5000元",
        session_id="contract-confirm",
    )
    monkeypatch.setattr(
        "app.agent.runtime.tool_arg_validation.load_skill_candidates",
        lambda _farm_id: type(
            "CandidateSet",
            (),
            {"values": {"category": ["化肥", "种子", "农药", "人工", "其他"]}},
        )(),
    )
    monkeypatch.setattr(
        "app.agent.executor.pending_actions.get_pending_plan",
        lambda *_args, **_kwargs: None,
    )

    with patch(
        "app.agent.executor.pending_actions._execute_write_skill",
        new_callable=AsyncMock,
    ) as mock_execute:
        decision = await handle_pending_action(
            farm_id=1,
            message="确认",
            session_id="contract-confirm",
        )

    assert decision.handled is True
    assert decision.status == "modified"
    assert "category" in decision.reply
    assert get_pending(1, session_id="contract-confirm") is not None
    mock_execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_confirm_pending_failure_stores_repaired_pending(monkeypatch):
    store_pending(
        1,
        "manage_cost",
        {"operation": "create_record", "amount": 5000, "record_type": "cost"},
        original_input="买了大棚膜5000元",
        session_id="contract-repair",
    )
    monkeypatch.setattr(
        "app.agent.executor.pending_actions.validate_pending_tool_args",
        lambda **kwargs: type(
            "Validation",
            (),
            {
                "valid": True,
                "params": dict(kwargs["params"]),
                "trace_payload": lambda self: {},
            },
        )(),
    )
    monkeypatch.setattr(
        "app.agent.executor.pending_actions._get_metadata_cache_groups",
        lambda *_args, **_kwargs: [],
    )
    monkeypatch.setattr(
        "app.agent.executor.pending_actions._clear_cache_groups",
        lambda *_args, **_kwargs: [],
    )
    monkeypatch.setattr(
        "app.agent.executor.pending_actions.get_pending_plan",
        lambda *_args, **_kwargs: None,
    )
    collector = MagicMock()

    with (
        patch(
            "app.agent.executor.pending_actions._execute_write_skill",
            new_callable=AsyncMock,
        ) as mock_execute,
        patch(
            "app.agent.executor.pending_actions.ReflectorService",
        ) as reflector_cls,
        patch(
            "app.agent.executor.pending_actions.get_collector",
            return_value=collector,
        ),
    ):
        mock_execute.return_value = type(
            "SkillResult",
            (),
            {"status": "failed", "reply": "记账失败：分类不能为空。"},
        )()
        reflector_cls.return_value.check_write_plan.return_value = type(
            "Reflection",
            (),
            {"decision": ReflectionDecision.PASS},
        )()

        decision = await handle_pending_action(
            farm_id=1,
            message="确认",
            session_id="contract-repair",
        )

    pending = get_pending(1, session_id="contract-repair")
    assert decision.status == "modified"
    assert "记账失败：分类不能为空。" in decision.reply
    assert pending is not None
    assert pending.params["category"] == "其他"
    assert pending.repair_attempts == 1


def test_pending_plan_creation_blocks_missing_category(monkeypatch):
    monkeypatch.setattr(
        "app.agent.runtime.tool_arg_validation.load_skill_candidates",
        lambda _farm_id: SimpleNamespace(
            values={"category": ["化肥", "种子", "农药", "人工", "销售", "其他"]}
        ),
    )
    collector = MagicMock()
    monkeypatch.setattr(
        "app.agent.runtime.tool_pending.get_collector",
        lambda: collector,
    )
    state = {
        "session_id": "contract-plan-create",
        "plan_draft": {
            "route_type": "write_pending_plan",
            "validation": {"status": "valid"},
            "steps": [
                {
                    "step_id": "step-1",
                    "skill_name": "manage_cost",
                    "params": {
                        "operation": "create_record",
                        "amount": 5000,
                        "record_type": "cost",
                    },
                    "depends_on": [],
                }
            ],
        },
    }

    messages = _pending_plan_tool_message(
        state=state,
        farm_id=1,
        original_input="买了大棚膜5000元",
        tool_calls=[{"id": "tc1", "name": "manage_cost"}],
    )

    assert messages is not None
    assert "待确认计划参数不完整" in messages[0].content
    assert "category" in messages[0].content
    assert (1, "contract-plan-create") not in _pending_plans
    output_data = collector.record.call_args.kwargs["output_data"]
    assert output_data["status"] == "contract_blocked"
    assert output_data["blocked_steps"][0]["contract_validation"]["missing_fields"] == [
        "category"
    ]


def test_pending_plan_creation_infers_operation_before_contract_validation(monkeypatch):
    monkeypatch.setattr(
        "app.agent.runtime.tool_arg_validation.load_skill_candidates",
        lambda _farm_id: SimpleNamespace(values={"category": ["化肥", "种子"]}),
    )
    state = {
        "session_id": "contract-plan-create",
        "plan_draft": {
            "route_type": "write_pending_plan",
            "validation": {"status": "valid"},
            "steps": [
                {
                    "step_id": "step-1",
                    "skill_name": "manage_cost",
                    "params": {"amount": 5000, "record_type": "cost"},
                    "depends_on": [],
                }
            ],
        },
    }

    messages = _pending_plan_tool_message(
        state=state,
        farm_id=1,
        original_input="买了大棚膜5000元",
        tool_calls=[{"id": "tc1", "name": "manage_cost"}],
    )

    assert messages is not None
    assert "category" in messages[0].content
    assert (1, "contract-plan-create") not in _pending_plans


def test_pending_plan_merges_tool_call_args_before_contract_validation(monkeypatch):
    monkeypatch.setattr(
        "app.agent.runtime.tool_arg_validation.load_skill_candidates",
        lambda _farm_id: SimpleNamespace(values={}),
    )
    monkeypatch.setattr(
        "app.agent.runtime.tool_pending.ReflectorService",
        lambda: SimpleNamespace(check_pending_plan=lambda **_kwargs: _PassReflection()),
    )
    monkeypatch.setattr(
        "app.infra.pending_actions.pending_plan_service.create_pending_plan",
        lambda *_args, **_kwargs: SimpleNamespace(plan_id="plan-tool-call-args"),
    )
    state = {
        "session_id": "contract-plan-tool-call-args",
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
                },
                {
                    "step_id": "create_worker",
                    "skill_name": "manage_workers",
                    "params": {
                        "action": "create",
                        "default_pay_type": "daily",
                        "default_unit_price": "100",
                    },
                    "depends_on": [],
                },
            ],
        },
    }

    messages = _pending_plan_tool_message(
        state=state,
        farm_id=1,
        original_input="我招了一些工人，主自豪，李是四 工资 100一天擅长压瓜",
        tool_calls=[
            {
                "id": "tc1",
                "name": "manage_workers",
                "args": {
                    "action": "create",
                    "default_pay_type": "daily",
                    "default_unit_price": "100",
                    "name": "主自豪",
                },
            },
            {
                "id": "tc2",
                "name": "manage_workers",
                "args": {
                    "action": "create",
                    "default_pay_type": "daily",
                    "default_unit_price": "100",
                    "name": "李是四",
                },
            },
        ],
    )

    assert messages is not None
    assert messages[0].content.startswith(PENDING_MARKER)
    assert "缺少必填字段：name" not in messages[0].content
    plan = _pending_plans[(1, "contract-plan-tool-call-args")]
    assert [step.params["name"] for step in plan.steps] == ["主自豪", "李是四"]


@pytest.mark.asyncio
async def test_pending_plan_failed_skill_result_does_not_confirm(monkeypatch):
    step = PendingPlanStep(
        step_id="step-1",
        step_index=0,
        tool_name="manage_cost",
        params={
            "operation": "create_record",
            "amount": 5000,
            "record_type": "cost",
        },
        depends_on=[],
    )
    plan = PendingPlan(
        plan_id="plan-contract-failure",
        farm_id=1,
        session_id="contract-plan-failure",
        status="pending",
        current_step_index=0,
        raw_user_input="买了化肥5000元",
        router_decision={},
        steps=[step],
        created_at=0,
    )
    monkeypatch.setattr(
        "app.agent.executor.pending_actions.validate_pending_tool_args",
        lambda **kwargs: SimpleNamespace(
            valid=True,
            params=dict(kwargs["params"]),
            trace_payload=lambda: {},
        ),
    )
    monkeypatch.setattr(
        "app.agent.executor.tool_failure_reflection.load_skill_candidates",
        lambda _farm_id: SimpleNamespace(values={"category": ["化肥", "其他"]}),
    )
    monkeypatch.setattr(
        "app.agent.executor.pending_actions._execute_write_skill",
        AsyncMock(
            return_value=SkillResult(
                status=ResultStatus.FAILED,
                reply="记账失败：分类不能为空。",
            )
        ),
    )
    mark_failed = MagicMock()
    monkeypatch.setattr(
        "app.agent.executor.pending_actions._mark_pending_plan_step_failed",
        mark_failed,
    )
    monkeypatch.setattr(
        "app.agent.executor.pending_actions._clear_runtime_pending_plan_cache",
        MagicMock(),
    )
    monkeypatch.setattr(
        "app.agent.executor.pending_actions.ReflectorService",
        lambda: SimpleNamespace(check_pending_plan=lambda **_kwargs: _PassReflection()),
    )

    decision = await _confirm_pending_plan(
        farm_id=1,
        plan=plan,
        session_id="contract-plan-failure",
    )

    assert decision.handled is True
    assert decision.status == "modified"
    assert "执行计划第 1 步失败" in decision.reply
    assert "请重新确认" in decision.reply
    repaired = get_pending(1, session_id="contract-plan-failure")
    assert repaired is not None
    assert repaired.params["category"] == "化肥"
    mark_failed.assert_called_once_with(
        "plan-contract-failure",
        0,
        "记账失败：分类不能为空。",
    )
