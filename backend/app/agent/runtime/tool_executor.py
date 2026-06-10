"""Agent Runtime 工具执行。"""

import asyncio
import logging
import re
import time as _time
from dataclasses import dataclass

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from app.agent.router import SkillRouter
from app.agent.skills import get_langchain_tools
from app.agent.skills.metadata import SkillPermissionLevel
from app.agent.state import AgentState
from app.core.database import SessionLocal
from app.infra.pending_actions import (
    PENDING_MARKER,
    PendingPlanStep,
    build_confirm_message,
    build_confirmation_context,
    build_plan_confirm_message,
    is_write_skill,
    store_pending,
    store_pending_plan,
)
from app.infra.trace_collector import get_collector
from app.models.cycle import CropCycle
from app.models.planting import Worker

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class _PermissionDecision:
    permission_level: str
    requires_confirmation: bool = False
    reject_message: str | None = None
    disabled: bool = False
    disabled_reason: str | None = None

    @property
    def is_disabled(self) -> bool:
        return self.disabled


_KNOWN_PERMISSION_LEVELS = {level.value for level in SkillPermissionLevel}
_DEBT_DIRECTION_HINT_RE = re.compile(
    r"(?:买|采购|购|花|支出|卖|销售|收入|赚|向|跟|找|在|给|我欠|欠我|未付|未收|先欠着)"
)
_AMBIGUOUS_DEBT_RE = re.compile(
    r"^(?P<name>[\u4e00-\u9fffA-Za-z0-9·]{1,20})(?:赊账|赊了|赊|欠账|欠款|欠)\s*\d*"
)


def _permission_decision(
    tool, skill_name: str, state: AgentState
) -> _PermissionDecision:
    """根据 metadata 权限等级做执行决策，未知权限按 fail closed 处理。"""
    metadata = getattr(tool, "skill_metadata", None)
    if metadata is not None:
        permission_level = getattr(metadata, "permission_level", None)
        permission_value = getattr(permission_level, "value", permission_level)
        enabled = getattr(metadata, "enabled", None)
        disabled_reason = getattr(metadata, "disabled_reason", None)
        if enabled is False:
            if permission_value in _KNOWN_PERMISSION_LEVELS:
                permission_level_value = permission_value
            elif is_write_skill(skill_name):
                permission_level_value = SkillPermissionLevel.WRITE_CONFIRM.value
            elif isinstance(permission_value, str):
                permission_level_value = permission_value
            else:
                permission_level_value = SkillPermissionLevel.READ.value
            return _PermissionDecision(
                permission_level=permission_level_value,
                disabled=True,
                disabled_reason=disabled_reason,
            )
        if permission_value in _KNOWN_PERMISSION_LEVELS:
            if permission_value == SkillPermissionLevel.WRITE_CONFIRM.value:
                return _PermissionDecision(
                    permission_level=permission_value,
                    requires_confirmation=True,
                )
            if permission_value == SkillPermissionLevel.ADMIN.value:
                if state.get("user_role") == "admin":
                    return _PermissionDecision(permission_level=permission_value)
                return _PermissionDecision(
                    permission_level=permission_value,
                    reject_message="工具调用失败：需要管理员权限。",
                )
            return _PermissionDecision(permission_level=permission_value)

        if isinstance(permission_value, str):
            if is_write_skill(skill_name):
                return _PermissionDecision(
                    permission_level=SkillPermissionLevel.WRITE_CONFIRM.value,
                    requires_confirmation=True,
                )
            return _PermissionDecision(
                permission_level=permission_value,
                reject_message="工具调用失败：未知权限等级。",
            )

    if is_write_skill(skill_name):
        return _PermissionDecision(
            permission_level=SkillPermissionLevel.WRITE_CONFIRM.value,
            requires_confirmation=True,
        )

    return _PermissionDecision(permission_level=SkillPermissionLevel.READ.value)


def _build_pending_confirmation_args(name: str, args: dict, farm_id: int) -> dict:
    """构建确认展示用参数，避免修改实际待执行参数。"""
    context_args = dict(args or {})
    if name == "create_operation_work_order":
        _normalize_operation_work_order_args(context_args)
    if name == "update_crop_cycle":
        _fill_update_crop_cycle_context_args(context_args, farm_id)
    if name == "settle_labor_payment":
        _fill_settle_labor_context_args(context_args, farm_id)
    return context_args


def _build_pending_execution_args(
    name: str,
    args: dict,
    farm_id: int,
    original_input: str,
) -> dict:
    """构建待执行参数，只补齐确定性的目标标识。"""
    execution_args = dict(args or {})
    if name == "create_operation_work_order":
        _normalize_operation_work_order_args(execution_args)
    if name == "manage_workers":
        _fill_manage_workers_target_args(execution_args, farm_id, original_input)
    return execution_args


def _normalize_operation_work_order_args(args: dict) -> None:
    """规范化模型常见作业单参数别名。"""
    _copy_arg_if_missing(args, "operation_date", "work_date")
    _copy_arg_if_missing(args, "unit_names", "planting_unit_name")
    _copy_arg_if_missing(args, "workers", "worker_name")
    _copy_arg_if_missing(args, "pay_type", "payment_method")


def _copy_arg_if_missing(args: dict, target: str, source: str) -> None:
    if args.get(target) in (None, "") and args.get(source) not in (None, ""):
        args[target] = args[source]


def _ambiguous_debt_direction_message(
    name: str,
    args: dict,
) -> str:
    amount = args.get("amount")
    amount_text = f"{amount}元" if amount not in (None, "") else "这笔钱"
    return (
        f"这笔赊账还没有执行。请先确认谁欠谁："
        f"是你欠{name}{amount_text}，还是{name}欠你{amount_text}？"
    )


def _needs_debt_direction_clarification(
    name: str,
    args: dict,
    original_input: str,
) -> str | None:
    if name != "create_cost_record":
        return None
    if args.get("record_subtype") != "赊账":
        return None
    text = original_input.strip()
    if not text or _DEBT_DIRECTION_HINT_RE.search(text):
        return None
    counterparty = str(args.get("counterparty") or "").strip()
    match = _AMBIGUOUS_DEBT_RE.search(text)
    if match:
        return counterparty or match.group("name")
    return None


def _fill_update_crop_cycle_context_args(args: dict, farm_id: int) -> None:
    """为 update_crop_cycle 补齐确认展示所需的当前茬口信息。"""
    needs_lookup = any(
        args.get(key) in (None, "")
        for key in ("old_start_date", "cycle_name", "cycle_id")
    )
    if not needs_lookup:
        return

    db = SessionLocal()
    try:
        cycle = _resolve_pending_crop_cycle(db, args=args, farm_id=farm_id)
        if cycle is None:
            return
        args["cycle_id"] = cycle.id
        args["cycle_name"] = cycle.name
        args["old_start_date"] = _date_to_iso(getattr(cycle, "start_date", None))
    except Exception as exc:
        logger.warning(
            "构建 update_crop_cycle pending context 失败 | farm_id=%s | error=%s",
            farm_id,
            exc,
        )
    finally:
        db.close()


def _resolve_pending_crop_cycle(db, *, args: dict, farm_id: int) -> CropCycle | None:
    cycle_id = args.get("cycle_id")
    if cycle_id not in (None, ""):
        return (
            db.query(CropCycle)
            .filter(CropCycle.id == cycle_id, CropCycle.farm_id == farm_id)
            .first()
        )

    crop_name = _clean_text(args.get("crop_name"))
    cycle_name = _clean_text(args.get("cycle_name"))
    if not crop_name and not cycle_name:
        return None

    active_cycles = (
        db.query(CropCycle)
        .filter(CropCycle.farm_id == farm_id, CropCycle.status == "active")
        .all()
    )
    matches = [
        cycle
        for cycle in active_cycles
        if _pending_cycle_matches(
            cycle,
            crop_name=crop_name,
            cycle_name=cycle_name,
        )
    ]
    if len(matches) == 1:
        return matches[0]
    return None


def _pending_cycle_matches(
    cycle: CropCycle,
    *,
    crop_name: str | None,
    cycle_name: str | None,
) -> bool:
    cycle_label = _normalize_text(cycle.name)
    template_label = _normalize_text(getattr(cycle.crop_template, "name", ""))

    if cycle_name:
        query = _normalize_text(cycle_name)
        if query in cycle_label or cycle_label in query:
            return True

    if crop_name:
        query = _normalize_text(crop_name)
        return (
            query in cycle_label
            or query in template_label
            or (template_label and template_label in query)
        )

    return False


def _fill_settle_labor_context_args(args: dict, farm_id: int) -> None:
    """为人工结算确认补齐受影响未付条目预览。"""
    if args.get("affected_entries"):
        return
    db = SessionLocal()
    try:
        from app.services import planting_read_service

        entries = planting_read_service.list_labor_payables(
            db,
            farm_id=farm_id,
            worker_name=_clean_text(args.get("worker") or args.get("worker_name")),
            cycle_id=args.get("cycle_id"),
            work_order_id=args.get("work_order_id"),
        )
        args["affected_entries"] = [
            {
                "entry_id": entry.id,
                "work_order_id": entry.work_order_id,
                "worker_name": entry.worker.name if entry.worker else "",
                "unpaid_amount": _date_to_iso(entry.unpaid_amount),
            }
            for entry in entries[:10]
        ]
    except Exception as exc:
        logger.warning(
            "构建 settle_labor_payment pending context 失败 | farm_id=%s | error=%s",
            farm_id,
            exc,
        )
    finally:
        db.close()


def _fill_manage_workers_target_args(
    args: dict,
    farm_id: int,
    original_input: str,
) -> None:
    """为工人档案写操作补齐真实 worker_id 和完整姓名。"""
    action = _clean_text(args.get("action")) or "create"
    if action == "create":
        return
    db = SessionLocal()
    try:
        worker = _resolve_pending_worker(db, args=args, farm_id=farm_id)
        if worker is None:
            worker = _resolve_pending_worker_from_input(
                db,
                farm_id=farm_id,
                original_input=original_input,
                name=_clean_text(args.get("name")),
            )
        if worker is None:
            return
        args["worker_id"] = worker.id
        args["name"] = worker.name
    except Exception as exc:
        logger.warning(
            "构建 manage_workers pending args 失败 | farm_id=%s | error=%s",
            farm_id,
            exc,
        )
    finally:
        db.close()


def _resolve_pending_worker(db, *, args: dict, farm_id: int) -> Worker | None:
    worker_id = args.get("worker_id")
    if worker_id not in (None, ""):
        return (
            db.query(Worker)
            .filter(Worker.id == worker_id, Worker.farm_id == farm_id)
            .first()
        )

    name = _clean_text(args.get("name"))
    if not name:
        return None
    return (
        db.query(Worker)
        .filter(Worker.farm_id == farm_id, Worker.name == name)
        .order_by(Worker.id)
        .first()
    )


def _resolve_pending_worker_from_input(
    db,
    *,
    farm_id: int,
    original_input: str,
    name: str | None,
) -> Worker | None:
    if not original_input:
        return None
    workers = (
        db.query(Worker)
        .filter(Worker.farm_id == farm_id)
        .order_by(Worker.id)
        .limit(50)
        .all()
    )
    matches = [
        worker for worker in workers if worker.name and worker.name in original_input
    ]
    if not matches and name:
        matches = [
            worker
            for worker in workers
            if worker.name and (name in worker.name or worker.name in name)
        ]
    if len(matches) == 1:
        return matches[0]
    return None


def _date_to_iso(value) -> str | None:
    try:
        if value is None:
            return None
        if hasattr(value, "isoformat"):
            return value.isoformat()
        return str(value)
    except Exception:
        return None


def _clean_text(value) -> str | None:
    if not isinstance(value, str):
        return None
    cleaned = value.strip()
    return cleaned or None


def _normalize_text(value: str) -> str:
    return "".join(str(value).split()).lower()


def _pending_plan_tool_message(
    *,
    state: AgentState,
    farm_id: int,
    original_input: str,
    tool_call_id: str,
) -> ToolMessage | None:
    """如果 router 已生成多步骤写计划，则存储 pending plan 并返回确认消息。"""
    router_decision = state.get("router_decision")
    if router_decision is None:
        return None

    steps = SkillRouter().build_pending_plan_steps(router_decision)
    if len(steps) < 2:
        return None

    pending_steps = [
        PendingPlanStep(
            step_id=str(step["step_id"]),
            step_index=index,
            tool_name=str(step["tool_name"]),
            params=dict(step.get("params") or {}),
            depends_on=list(step.get("depends_on") or []),
        )
        for index, step in enumerate(steps)
    ]
    session_id = state.get("session_id")
    store_pending_plan(
        farm_id=farm_id,
        session_id=session_id,
        raw_user_input=original_input,
        router_decision=router_decision.to_trace_payload(),
        steps=pending_steps,
    )
    confirm_text = build_plan_confirm_message(pending_steps)
    return ToolMessage(
        content=f"{PENDING_MARKER} {confirm_text}",
        tool_call_id=tool_call_id,
    )


async def _parallel_tool_node(state: AgentState) -> dict:
    """并行执行多个 tool_calls 的节点。写操作 Skill 拦截为 pending action。"""
    last = state["messages"][-1]
    if not isinstance(last, AIMessage) or not last.tool_calls:
        return {"messages": []}

    farm_id = state.get("farm_id")
    if not isinstance(farm_id, int) or farm_id <= 0:
        return {
            "messages": [
                ToolMessage(
                    content="工具调用失败：缺少可信农场上下文。",
                    tool_call_id=tc["id"],
                )
                for tc in last.tool_calls
            ]
        }
    farm_uid = state.get("farm_uid")
    tool_map = {
        t.name: t for t in get_langchain_tools(farm_id=farm_id, farm_uid=farm_uid)
    }
    collector = get_collector()

    # 获取用户原始输入（最近一条 HumanMessage）
    original_input = ""
    for msg in reversed(state.get("messages", [])):
        if isinstance(msg, HumanMessage):
            original_input = msg.content[:200]
            break

    first_tool_call = last.tool_calls[0]
    plan_message = _pending_plan_tool_message(
        state=state,
        farm_id=farm_id,
        original_input=original_input,
        tool_call_id=first_tool_call["id"],
    )
    if plan_message is not None:
        collector.record(
            node_type="skill_call",
            node_name="pending_plan",
            input_data={"message": original_input},
            output_data={"status": "pending_plan"},
            duration_ms=0,
        )
        return {"messages": [plan_message]}

    async def _call_one(tc: dict) -> ToolMessage:
        name = tc["name"]
        args = tc["args"]
        tool_call_id = tc["id"]
        logger.info("Skill 调用 %s(%s)", name, args)
        start = _time.perf_counter()

        tool = tool_map.get(name)
        permission_decision = _permission_decision(tool, name, state)

        if permission_decision.is_disabled:
            output_data = {
                "status": "disabled",
                "permission_level": permission_decision.permission_level,
            }
            content = "工具调用失败：工具已禁用。"
            if permission_decision.disabled_reason:
                output_data["disabled_reason"] = permission_decision.disabled_reason
                content = f"{content} 原因：{permission_decision.disabled_reason}"
            logger.warning(
                "Skill 已禁用 | name=%s | permission_level=%s",
                name,
                permission_decision.permission_level,
            )
            collector.record(
                node_type="skill_call",
                node_name=name,
                input_data=args,
                output_data=output_data,
                duration_ms=0,
            )
            return ToolMessage(
                content=content,
                tool_call_id=tool_call_id,
            )

        # Pydantic 参数校验：在写操作拦截前校验，校验失败反馈 LLM 自纠错
        if tool and hasattr(tool, "args_schema") and tool.args_schema:
            try:
                tool.args_schema.model_validate(args)
            except Exception as e:
                error_msg = f"参数校验失败: {e}"
                logger.warning("Tool 参数校验失败 | name=%s | error=%s", name, e)
                collector.record(
                    node_type="skill_call",
                    node_name=name,
                    input_data=args,
                    output_data={
                        "status": "validation_error",
                        "permission_level": permission_decision.permission_level,
                    },
                    duration_ms=0,
                    error_message=str(e),
                )
                return ToolMessage(
                    content=error_msg,
                    tool_call_id=tool_call_id,
                )

        if permission_decision.reject_message is not None:
            logger.warning(
                "Skill 权限拒绝 | name=%s | permission_level=%s",
                name,
                permission_decision.permission_level,
            )
            collector.record(
                node_type="skill_call",
                node_name=name,
                input_data=args,
                output_data={
                    "status": "rejected",
                    "permission_level": permission_decision.permission_level,
                },
                duration_ms=0,
            )
            return ToolMessage(
                content=permission_decision.reject_message,
                tool_call_id=tool_call_id,
            )

        # 写操作 Skill 拦截：存储 pending action，不直接执行
        if permission_decision.requires_confirmation:
            execution_args = _build_pending_execution_args(
                name, args, farm_id, original_input
            )
            ambiguous_debt_name = _needs_debt_direction_clarification(
                name, execution_args, original_input
            )
            if ambiguous_debt_name:
                content = _ambiguous_debt_direction_message(
                    ambiguous_debt_name,
                    execution_args,
                )
                collector.record(
                    node_type="skill_call",
                    node_name=name,
                    input_data=execution_args,
                    output_data={
                        "status": "need_clarify",
                        "permission_level": permission_decision.permission_level,
                        "reason": "ambiguous_debt_direction",
                    },
                    duration_ms=0,
                )
                return ToolMessage(
                    content=content,
                    tool_call_id=tool_call_id,
                )
            confirmation_args = _build_pending_confirmation_args(
                name, execution_args, farm_id
            )
            confirmation_context = build_confirmation_context(
                name, confirmation_args, original_input=original_input
            )
            session_id = state.get("session_id")
            action_id = store_pending(
                farm_id,
                name,
                execution_args,
                original_input=original_input,
                confirmation_context=confirmation_context,
                session_id=session_id,
            )
            logger.info(
                "写操作 Skill 已拦截 | farm=%s action_id=%s skill=%s",
                farm_id,
                action_id,
                name,
            )
            collector.record(
                node_type="skill_call",
                node_name=name,
                input_data=execution_args,
                output_data={
                    "status": "pending",
                    "permission_level": permission_decision.permission_level,
                    "confirmation_context": confirmation_context,
                },
                duration_ms=0,
            )
            confirm_text = build_confirm_message(
                name, confirmation_args, original_input=original_input
            )
            return ToolMessage(
                content=f"{PENDING_MARKER} {confirm_text}",
                tool_call_id=tool_call_id,
            )

        # 读操作执行
        if not tool:
            return ToolMessage(content=f"未知工具: {name}", tool_call_id=tool_call_id)
        try:
            result = await tool.ainvoke(args)
            duration_ms = int((_time.perf_counter() - start) * 1000)
            summary = str(result)[:120].replace("\n", " ")
            logger.info(
                "Skill 完成 | name=%s | duration_ms=%d | result=%s",
                name,
                duration_ms,
                summary,
            )
            trace_output = getattr(result, "trace_data", None)
            if not trace_output:
                trace_output = {
                    "status": "success",
                    "reply_preview": str(result)[:500],
                }
            else:
                trace_output["reply_preview"] = str(result)[:500]
            trace_output["permission_level"] = permission_decision.permission_level
            collector.record(
                node_type="skill_call",
                node_name=name,
                input_data=args,
                output_data=trace_output,
                duration_ms=duration_ms,
            )
            return ToolMessage(content=str(result), tool_call_id=tool_call_id)
        except Exception as e:
            duration_ms = int((_time.perf_counter() - start) * 1000)
            logger.error(
                "Skill 失败 | name=%s | error=%s",
                name,
                e,
            )
            collector.record(
                node_type="skill_call",
                node_name=name,
                input_data=args,
                duration_ms=duration_ms,
                error_message=str(e),
            )
            return ToolMessage(content=f"工具调用失败: {e}", tool_call_id=tool_call_id)

    if len(last.tool_calls) == 1:
        results = [await _call_one(last.tool_calls[0])]
    else:
        logger.info("并行执行 %d 个 Skill", len(last.tool_calls))
        batch_start = _time.perf_counter()
        results = await asyncio.gather(*[_call_one(tc) for tc in last.tool_calls])
        batch_duration = int((_time.perf_counter() - batch_start) * 1000)
        collector.record(
            node_type="parallel_batch",
            node_name=f"parallel_{len(results)}_skills",
            output_data={
                "parallel_count": len(results),
                "skills": [{"name": tc["name"]} for tc in last.tool_calls],
            },
            duration_ms=batch_duration,
        )

    return {"messages": results}


__all__ = ["_parallel_tool_node"]
