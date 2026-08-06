"""Pending plan Saga 补偿与补偿契约校验。"""

import logging
import re
import time
from collections.abc import Awaitable
from dataclasses import dataclass
from typing import Any, Protocol

from app.agent.executor.models import PendingActionDecision
from app.agent.executor.pending_aliases import pending_alias_metadata
from app.agent.pending_plan_service import (
    mark_plan_partial_completed,
    mark_step_compensated,
)
from app.infra.pending_actions import PendingPlan, PendingPlanStep
from app.infra.trace_collector import get_collector
from app.observability import increment_counter
from app.shared.database import SessionLocal
from app.shared.logging import log_event
from app.skills.registry import load_skill_registry

logger = logging.getLogger(__name__)


class ExecuteWriteSkill(Protocol):
    """Pending plan 执行器提供的写 skill 调用入口。"""

    def __call__(
        self,
        *,
        farm_id: int,
        skill_name: str,
        params: dict,
        farm_uid: str | None = None,
    ) -> Awaitable[object]: ...


@dataclass(frozen=True)
class ExecutedPlanStep:
    """已成功执行、可能需要补偿的 pending plan step。"""

    step: PendingPlanStep
    params: dict
    result: object


@dataclass(frozen=True)
class SagaCompensationResult:
    """Saga 补偿结果。"""

    attempted: bool
    completed: bool
    steps: list[dict]
    error_message: str | None = None


def pending_plan_compensation_block(plan: PendingPlan) -> PendingActionDecision | None:
    """未声明补偿的 write step 不允许作为多步 plan 非末位。"""
    if len(plan.steps) <= 1:
        return None
    for step in sorted(plan.steps, key=lambda item: item.step_index)[:-1]:
        compensate_skill = resolve_compensate_skill(step.tool_name, step.params)
        if compensate_skill:
            continue
        return PendingActionDecision.failed(
            f"执行计划已拒绝：第 {step.step_index + 1} 步 skill "
            f"{step.tool_name} 不支持补偿，只能作为最后一步。"
        )
    return None


async def compensate_executed_plan_steps(
    *,
    farm_id: int,
    plan: PendingPlan,
    executed_steps: list[ExecutedPlanStep],
    farm_uid: str | None,
    session_id: str | None,
    failed_step: PendingPlanStep,
    failure_message: str,
    execute_write_skill: ExecuteWriteSkill,
) -> SagaCompensationResult:
    """按逆序补偿已成功执行的 step。"""
    if not executed_steps:
        return SagaCompensationResult(attempted=False, completed=True, steps=[])

    saga_steps: list[dict] = []
    for executed in reversed(executed_steps):
        result = await _compensate_one_step(
            farm_id=farm_id,
            plan=plan,
            executed=executed,
            farm_uid=farm_uid,
            session_id=session_id,
            failed_step=failed_step,
            failure_message=failure_message,
            saga_steps=saga_steps,
            execute_write_skill=execute_write_skill,
        )
        if result is not None:
            return result

    return SagaCompensationResult(attempted=True, completed=True, steps=saga_steps)


async def _compensate_one_step(
    *,
    farm_id: int,
    plan: PendingPlan,
    executed: ExecutedPlanStep,
    farm_uid: str | None,
    session_id: str | None,
    failed_step: PendingPlanStep,
    failure_message: str,
    saga_steps: list[dict],
    execute_write_skill: ExecuteWriteSkill,
) -> SagaCompensationResult | None:
    step = executed.step
    compensate_skill = resolve_compensate_skill(step.tool_name, executed.params)
    if not compensate_skill:
        error_message = (
            f"第 {step.step_index + 1} 步 skill {step.tool_name} 未声明补偿。"
        )
        return _partial_completed_result(
            plan=plan,
            session_id=session_id,
            failed_step=failed_step,
            compensated_step=step,
            error_message=error_message,
            saga_steps=saga_steps,
        )

    compensate_params = build_compensate_params(
        compensate_skill=compensate_skill,
        original_step=step,
        original_params=executed.params,
        original_result=executed.result,
    )
    if compensate_params is None:
        error_message = (
            f"第 {step.step_index + 1} 步 skill {step.tool_name} 缺少可补偿的结果标识。"
        )
        return _partial_completed_result(
            plan=plan,
            session_id=session_id,
            failed_step=failed_step,
            compensated_step=step,
            error_message=error_message,
            saga_steps=saga_steps,
        )

    started_at = time.perf_counter()
    result = await execute_write_skill(
        farm_id=farm_id,
        skill_name=compensate_skill,
        params=compensate_params,
        farm_uid=farm_uid,
    )
    saga_step = _saga_step_payload(
        step=step,
        compensate_skill=compensate_skill,
        compensate_params=compensate_params,
        result=result,
        started_at=started_at,
    )
    saga_steps.append(saga_step)
    _record_saga_trace(
        plan=plan,
        session_id=session_id,
        failed_step=failed_step,
        saga_steps=saga_steps,
        saga_step=saga_step,
    )
    if _skill_result_failed_or_needs_clarify(result):
        increment_counter("pending_plan_saga_compensate_total", {"result": "failed"})
        return _partial_completed_result(
            plan=plan,
            session_id=session_id,
            failed_step=failed_step,
            compensated_step=step,
            error_message=_skill_result_reply(result) or failure_message,
            saga_steps=saga_steps,
        )
    _mark_pending_plan_step_compensated(
        plan.plan_id,
        step.step_index,
        {
            "message": _skill_result_reply(result),
            "compensate_skill": compensate_skill,
            "compensate_params": compensate_params,
        },
    )
    return None


def resolve_compensate_skill(skill_name: str, params: dict) -> str:
    """读取 registry operation 中声明的补偿 skill。"""
    try:
        alias_metadata = pending_alias_metadata(skill_name, params)
        registry = load_skill_registry()
        operation = registry.get_operation(
            alias_metadata["resolved_capability"],
            alias_metadata["resolved_operation"],
        )
    except ValueError as exc:
        logger.warning(
            "读取补偿 Skill metadata 失败 | skill=%s error=%s",
            skill_name,
            exc,
        )
        return ""
    return operation.compensate_skill if operation is not None else ""


def build_compensate_params(
    *,
    compensate_skill: str,
    original_step: PendingPlanStep,
    original_params: dict,
    original_result: object,
) -> dict | None:
    """从原始参数和执行结果构造补偿调用参数。"""
    identifier = _extract_result_identifier(original_result)
    if compensate_skill == "delete_cost_record":
        record_id = identifier or original_params.get("record_id")
        return {"record_id": record_id} if record_id else None
    if compensate_skill == "delete_crop_cycle":
        cycle_id = identifier or original_params.get("cycle_id")
        return {"cycle_id": cycle_id} if cycle_id else None
    if compensate_skill == "manage_work_orders":
        work_order_id = identifier or original_params.get("work_order_id")
        if not work_order_id:
            return None
        return {"operation": "delete_work_order", "work_order_id": work_order_id}
    if compensate_skill == "manage_labor_payment":
        payment_id = identifier or original_params.get("payment_id")
        if not payment_id:
            return None
        return {"operation": "reverse_payment", "payment_id": payment_id}
    if compensate_skill == "manage_crop_templates":
        template_id = identifier or original_params.get("template_id")
        if not template_id:
            return None
        return {
            "operation": "manage_template",
            "action": "delete",
            "template_id": template_id,
        }
    if compensate_skill == "manage_planting_units":
        unit_id = identifier or original_params.get("unit_id")
        if not unit_id:
            return None
        return {
            "operation": "manage_units",
            "action": "delete",
            "unit_id": unit_id,
        }
    if compensate_skill == "manage_workers":
        return _worker_compensate_params(identifier, original_params)
    if compensate_skill == "create_cost_record":
        return {
            "record_type": original_params.get("record_type", "income"),
            "category": "还款回滚",
            "amount": original_params.get("amount"),
            "note": f"pending plan 补偿：{original_step.step_id}",
        }
    return None


def pending_plan_failure_decision(
    *,
    step: PendingPlanStep,
    result_reply: str,
    compensation: SagaCompensationResult,
) -> PendingActionDecision:
    """合并 step 失败与 Saga 结果。"""
    if compensation.attempted and not compensation.completed:
        return PendingActionDecision.failed(
            f"执行计划第 {step.step_index + 1} 步失败：{result_reply}\n"
            f"{partial_completed_reply()}"
        )
    if compensation.attempted:
        return PendingActionDecision.failed(
            f"执行计划第 {step.step_index + 1} 步失败：{result_reply}\n"
            "已自动撤销前序步骤。"
        )
    return PendingActionDecision.failed(
        f"执行计划第 {step.step_index + 1} 步失败：{result_reply}"
    )


def merge_pending_plan_failure_decision(
    *,
    decision: PendingActionDecision,
    compensation: SagaCompensationResult,
) -> PendingActionDecision:
    """在已有失败决策上追加 Saga 结果。"""
    if compensation.attempted and not compensation.completed:
        return PendingActionDecision.failed(
            f"{decision.reply}\n{partial_completed_reply()}",
            metadata=decision.metadata,
        )
    if compensation.attempted and decision.status == "failed":
        return PendingActionDecision.failed(
            f"{decision.reply}\n已自动撤销前序步骤。",
            metadata=decision.metadata,
        )
    return decision


def partial_completed_reply() -> str:
    return "操作失败,已自动撤销部分步骤,请联系客服清理"


def _worker_compensate_params(identifier: Any, original_params: dict) -> dict | None:
    worker_id = identifier or original_params.get("worker_id")
    if worker_id:
        return {"action": "deactivate", "worker_id": worker_id}
    worker_name = original_params.get("name") or original_params.get("worker_name")
    if worker_name:
        return {"action": "deactivate", "name": worker_name}
    return None


def _extract_result_identifier(result: object) -> Any:
    for path in (
        "id",
        "data.id",
        "record_id",
        "data.record_id",
        "cycle_id",
        "data.cycle_id",
        "work_order_id",
        "data.work_order_id",
        "payment_id",
        "data.payment_id",
        "worker_id",
        "data.worker_id",
        "template_id",
        "data.template_id",
        "unit_id",
        "data.unit_id",
    ):
        value = _try_read_result_path(result, path)
        if value not in (None, ""):
            return value

    match = re.search(r"#(\d+)", _skill_result_reply(result))
    return int(match.group(1)) if match else None


def _try_read_result_path(result: object, path: str) -> Any:
    segments = [segment for segment in str(path or "").split(".") if segment]
    current = result
    for segment in segments:
        current = _read_result_segment(current, segment)
        if current is None:
            return None
    return current


def _read_result_segment(current: object, segment: str) -> Any:
    if isinstance(current, dict):
        return current.get(segment)
    if isinstance(current, list) and segment.isdigit():
        index = int(segment)
        return current[index] if 0 <= index < len(current) else None
    if hasattr(current, segment):
        return getattr(current, segment)

    data = getattr(current, "data", None)
    if isinstance(data, dict):
        return data.get(segment)
    return None


def _saga_step_payload(
    *,
    step: PendingPlanStep,
    compensate_skill: str,
    compensate_params: dict,
    result: object,
    started_at: float,
) -> dict:
    return {
        "step_id": step.step_id,
        "step_index": step.step_index,
        "skill_name": step.tool_name,
        "compensate_skill": compensate_skill,
        "compensate_params": compensate_params,
        "status": _skill_result_status(result),
        "reply": _skill_result_reply(result),
        "duration_ms": int((time.perf_counter() - started_at) * 1000),
    }


def _partial_completed_result(
    *,
    plan: PendingPlan,
    session_id: str | None,
    failed_step: PendingPlanStep,
    compensated_step: PendingPlanStep,
    error_message: str,
    saga_steps: list[dict],
) -> SagaCompensationResult:
    _mark_plan_partial_completed_in_db(plan.plan_id, error_message, saga_steps)
    _log_compensation_failure(
        plan=plan,
        session_id=session_id,
        failed_step=failed_step,
        compensated_step=compensated_step,
        error_message=error_message,
        saga_steps=saga_steps,
    )
    return SagaCompensationResult(
        attempted=True,
        completed=False,
        steps=saga_steps,
        error_message=error_message,
    )


def _record_saga_trace(
    *,
    plan: PendingPlan,
    session_id: str | None,
    failed_step: PendingPlanStep,
    saga_steps: list[dict],
    saga_step: dict,
) -> None:
    get_collector().record(
        node_type="skill_call",
        node_name=saga_step["compensate_skill"],
        input_data=saga_step["compensate_params"],
        output_data={
            "status": saga_step["status"],
            "phase": "pending_plan_saga_compensate",
            "plan_id": plan.plan_id,
            "plan_version": plan.version,
            "session_id": session_id,
            "failed_step_id": failed_step.step_id,
            "failed_step_index": failed_step.step_index,
            "saga_compensate_steps": saga_steps,
        },
        duration_ms=saga_step["duration_ms"],
    )


def _log_compensation_failure(
    *,
    plan: PendingPlan,
    session_id: str | None,
    failed_step: PendingPlanStep,
    compensated_step: PendingPlanStep,
    error_message: str,
    saga_steps: list[dict],
) -> None:
    log_event(
        logger,
        logging.WARNING,
        "pending_plan.saga_compensate_failed",
        code="PENDING_PLAN_PARTIAL_COMPLETED",
        session_id=session_id,
        step_id=compensated_step.step_id,
        status="partial_completed",
        data={
            "plan_id": plan.plan_id,
            "plan_version": plan.version,
            "failed_step_id": failed_step.step_id,
            "failed_step_index": failed_step.step_index,
            "compensated_step_id": compensated_step.step_id,
            "compensated_step_index": compensated_step.step_index,
            "error_message": error_message,
            "saga_compensate_steps": saga_steps,
        },
    )


def _mark_pending_plan_step_compensated(
    plan_id: str,
    step_index: int,
    result: dict,
) -> None:
    db = SessionLocal()
    try:
        mark_step_compensated(
            db,
            plan_id=plan_id,
            step_index=step_index,
            result=result,
        )
    finally:
        db.close()


def _mark_plan_partial_completed_in_db(
    plan_id: str,
    error_message: str,
    saga_steps: list[dict],
) -> None:
    db = SessionLocal()
    try:
        mark_plan_partial_completed(
            db,
            plan_id=plan_id,
            error_message=error_message,
            saga_steps=saga_steps,
        )
    finally:
        db.close()


def _skill_result_reply(result: object) -> str:
    return str(getattr(result, "reply", result) or "")


def _skill_result_status(result: object) -> str:
    if isinstance(result, str):
        return "success" if result else "failed"
    status = getattr(result, "status", None)
    value = getattr(status, "value", status)
    text = str(value or "").lower()
    if "." in text:
        text = text.rsplit(".", maxsplit=1)[-1]
    return text


def _skill_result_failed_or_needs_clarify(result: object) -> bool:
    return _skill_result_status(result) in {"failed", "need_clarify"}
