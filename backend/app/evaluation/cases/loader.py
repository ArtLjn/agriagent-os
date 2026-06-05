"""评测用例加载器。"""

import json
from pathlib import Path
from typing import Any

from app.evaluation.cases.schemas import (
    AgentReplayCase,
    ContextExpectation,
    ExpectedSkillCall,
    ConfirmationFlowStep,
    ExpectedDatabaseDiff,
    ExpectedPendingAction,
    ExpectedWriteOperation,
    ReplyAssertion,
)
from app.simulation.test_runner import CASES_DIR


def load_simulation_cases(
    cases_dir: Path = CASES_DIR,
    category: str | None = None,
) -> list[AgentReplayCase]:
    """复用现有 simulation JSON 用例并转换为 AgentReplayCase。"""
    cases: list[AgentReplayCase] = []
    if not cases_dir.exists():
        return cases

    for path in sorted(cases_dir.glob("*.json")):
        with path.open("r", encoding="utf-8") as file:
            raw_cases = json.load(file)
        if not isinstance(raw_cases, list):
            continue
        for raw in raw_cases:
            replay_case = _simulation_to_replay_case(raw, source_file=path.name)
            if category is None or replay_case.category == category:
                cases.append(replay_case)
    return cases


def load_replay_cases(path: Path) -> list[AgentReplayCase]:
    """加载原生 Agent 回放用例 JSON。"""
    with path.open("r", encoding="utf-8") as file:
        raw_cases = json.load(file)
    if not isinstance(raw_cases, list):
        raise ValueError("replay cases must be a JSON array")
    return [_raw_to_replay_case(raw) for raw in raw_cases]


def builtin_skill_regression_cases() -> list[AgentReplayCase]:
    """返回 Skill 能力增强的内置回归用例集合。"""
    raw_cases = [
        {
            "case_id": "crop-cycle-update-start-date",
            "description": "修改玉米茬口9月1开始",
            "user_input": "把玉米茬口改成9月1开始",
            "category": "crop_cycle",
            "expected_skills": [
                {
                    "name": "update_crop_cycle",
                    "arguments": {"crop_name": "玉米", "start_date": "2026-09-01"},
                }
            ],
            "expected_pending_action": {
                "skill_name": "update_crop_cycle",
                "params": {"start_date": "2026-09-01"},
            },
            "confirmation_flow": [
                {"user_input": "确认", "expected_status": "confirmed"}
            ],
            "expected_database_diff": [
                {
                    "table": "crop_cycles",
                    "operation": "update",
                    "match_fields": {"name": "玉米"},
                    "after": {"start_date": "2026-09-01"},
                }
            ],
            "context": {"expected_block_types": ["cycle"]},
            "metadata": {
                "business_domain": "planting",
                "permission_level": "write_confirm",
                "confirmation_path": "confirm",
                "context_dependencies": ["crop_cycle"],
            },
        },
        {
            "case_id": "work-order-create",
            "description": "创建作业单",
            "user_input": "今天给1号棚打药，张三做工，工钱200",
            "category": "work_order",
            "expected_skills": [
                {
                    "name": "create_operation_work_order",
                    "arguments": {"operation_type": "打药", "worker_names": ["张三"]},
                }
            ],
            "expected_pending_action": {
                "skill_name": "create_operation_work_order",
                "params": {"operation_type": "打药"},
            },
            "confirmation_flow": [
                {"user_input": "确认", "expected_status": "confirmed"}
            ],
            "expected_database_diff": [
                {
                    "table": "operation_work_orders",
                    "operation": "insert",
                    "match_fields": {"operation_type": "打药"},
                }
            ],
            "metadata": {
                "business_domain": "planting",
                "permission_level": "write_confirm",
                "confirmation_path": "confirm",
                "context_dependencies": ["planting_units", "workers"],
            },
        },
        {
            "case_id": "work-order-correction",
            "description": "纠正作业单金额",
            "user_input": "刚才那个打药工钱不对，是300",
            "category": "work_order",
            "expected_skills": [
                {
                    "name": "create_operation_work_order",
                    "arguments": {"payable_amount": 300},
                }
            ],
            "confirmation_flow": [
                {"user_input": "不对，是300", "expected_status": "corrected"}
            ],
            "metadata": {
                "business_domain": "planting",
                "permission_level": "write_confirm",
                "confirmation_path": "correction",
                "context_dependencies": ["operation_work_orders", "workers"],
            },
        },
        {
            "case_id": "unpaid-labor-query",
            "description": "查询未结人工",
            "user_input": "还有哪些人工没结清？",
            "category": "labor",
            "expected_skills": [{"name": "get_labor_payables"}],
            "metadata": {
                "business_domain": "labor",
                "permission_level": "read",
                "confirmation_path": "none",
                "context_dependencies": ["workers", "unpaid_labor"],
            },
        },
        {
            "case_id": "labor-settlement",
            "description": "结算人工",
            "user_input": "给张三结清人工300元",
            "category": "labor",
            "expected_skills": [
                {"name": "settle_labor_payment", "arguments": {"worker": "张三"}}
            ],
            "expected_pending_action": {
                "skill_name": "settle_labor_payment",
                "params": {"worker": "张三", "amount": 300},
            },
            "confirmation_flow": [
                {"user_input": "确认", "expected_status": "confirmed"}
            ],
            "expected_database_diff": [
                {
                    "table": "labor_entries",
                    "operation": "update",
                    "after": {"settlement_status": "paid"},
                }
            ],
            "metadata": {
                "business_domain": "labor",
                "permission_level": "write_confirm",
                "confirmation_path": "confirm",
                "context_dependencies": ["workers", "unpaid_labor", "ledger"],
            },
        },
        {
            "case_id": "cost-record-correction",
            "description": "纠正成本记录",
            "user_input": "刚才肥料账记错了，金额改成120",
            "category": "cost",
            "expected_skills": [
                {"name": "update_cost_record", "arguments": {"amount": 120}}
            ],
            "confirmation_flow": [
                {"user_input": "不对，是120", "expected_status": "corrected"}
            ],
            "metadata": {
                "business_domain": "finance",
                "permission_level": "write_confirm",
                "confirmation_path": "correction",
                "context_dependencies": ["ledger", "cost_categories"],
            },
        },
        {
            "case_id": "weather-query",
            "description": "天气查询",
            "user_input": "明天适合打药吗？",
            "category": "weather",
            "expected_skills": [{"name": "get_weather_forecast"}],
            "metadata": {
                "business_domain": "weather",
                "permission_level": "external_network",
                "confirmation_path": "none",
                "context_dependencies": ["weather"],
            },
        },
    ]
    return [_raw_to_replay_case(raw) for raw in raw_cases]


def _simulation_to_replay_case(
    raw: dict[str, Any], source_file: str
) -> AgentReplayCase:
    expected_writes = [
        ExpectedWriteOperation(
            table=table,
            operation="insert" if spec.get("added", 0) else "unknown",
            expected_count=spec.get("added", 0),
            match_fields=spec.get("match_fields", {}),
        )
        for table, spec in raw.get("expected_db_changes", {}).items()
    ]
    return AgentReplayCase(
        case_id=raw["case_id"],
        description=raw["description"],
        user_input=raw["user_input"],
        expected_skills=[],
        expected_writes=expected_writes,
        reply_assertions=[
            ReplyAssertion(contains=keyword)
            for keyword in raw.get("expected_response_matches", [])
        ],
        context=ContextExpectation(
            farm_context=raw.get("precondition", {}),
            required_facts=[],
        ),
        category=raw.get("category", "basic"),
        metadata={"source": "simulation", "source_file": source_file},
    )


def _raw_to_replay_case(raw: dict[str, Any]) -> AgentReplayCase:
    return AgentReplayCase(
        case_id=raw["case_id"],
        description=raw.get("description", ""),
        user_input=raw["user_input"],
        user_context=raw.get("user_context", {}),
        context=_raw_context(raw.get("context", {})),
        expected_skills=[
            ExpectedSkillCall(
                name=item["name"],
                arguments=item.get("arguments", {}),
                required=item.get("required", True),
            )
            for item in raw.get("expected_skills", [])
        ],
        expected_parameters=raw.get("expected_parameters", {}),
        expected_pending_action=_raw_pending_action(
            raw.get("expected_pending_action")
        ),
        confirmation_flow=[
            ConfirmationFlowStep(
                user_input=item["user_input"],
                expected_status=item["expected_status"],
                expected_pending_action=_raw_pending_action(
                    item.get("expected_pending_action")
                ),
            )
            for item in raw.get("confirmation_flow", [])
        ],
        expected_database_diff=[
            ExpectedDatabaseDiff(
                table=item["table"],
                operation=item.get("operation", "unknown"),
                match_fields=item.get("match_fields", {}),
                before=item.get("before", {}),
                after=item.get("after", {}),
            )
            for item in raw.get("expected_database_diff", [])
        ],
        expected_writes=[
            ExpectedWriteOperation(
                table=item["table"],
                operation=item.get("operation", "unknown"),
                expected_count=item.get("expected_count", 1),
                match_fields=item.get("match_fields", {}),
                requires_confirmation=item.get("requires_confirmation", False),
            )
            for item in raw.get("expected_writes", [])
        ],
        reply_assertions=[
            ReplyAssertion(
                contains=item.get("contains"),
                not_contains=item.get("not_contains"),
                min_length=item.get("min_length", 0),
            )
            for item in raw.get("reply_assertions", [])
        ],
        category=raw.get("category", "basic"),
        metadata=raw.get("metadata", {}),
    )


def _raw_pending_action(raw: dict[str, Any] | None) -> ExpectedPendingAction | None:
    if not raw:
        return None
    return ExpectedPendingAction(
        skill_name=raw["skill_name"],
        params=raw.get("params", {}),
        status=raw.get("status", "created"),
        confirmation_required=raw.get("confirmation_required", True),
    )


def _raw_context(raw: dict[str, Any]) -> ContextExpectation:
    return ContextExpectation(
        user_context=raw.get("user_context", {}),
        farm_context=raw.get("farm_context", {}),
        required_facts=raw.get("required_facts", []),
        expected_block_types=raw.get("expected_block_types", []),
    )
