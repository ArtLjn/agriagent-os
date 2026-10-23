"""收尾阶段的证据与答复校验；不调度业务工具，也不授予额外决策预算。"""

from __future__ import annotations

import json
import re
from collections.abc import AsyncGenerator
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from agent.domains.harness.runtime.turn import StopReason, Turn, TurnPhase
from agent.domains.harness.runtime.verify import (
    WRITE_RISK_LEVELS,
    claims_write_completion,
)
from agent.domains.harness.tools.base import Skill
from agent.platforms.persistence.redis import sse

# 收尾是独立的一次模型调用，不能借此继续执行工具或无限生成。
FINALIZATION_TIMEOUT_SECONDS = 20.0
FINALIZATION_MAX_TOKENS = 1536
_SUMMARY_MAX_CHARS = 240
_SETTLEMENT_EVIDENCE_FIELDS = frozenset({"settled_cost", "settled_income"})
_REPORTED_SETTLEMENT_STATUS = re.compile(
    r"[（(]已(?:全部)?结算[）)]"
    r"|^[ \t>#-]*已结算(?:收入|支出|成本|金额)?\s*[:：]"
    r"|\d[\d,]*(?:\.\d+)?\s*元\s*已结算(?=[）)，,。；;\s]|$)",
    re.MULTILINE,
)
_UNCOMMITTED_STATUSES = frozenset(
    {"ready", "pending", "accepted", "queued", "needs_information", "failed", "error"}
)
_FINALIZATION_PROMPT = """当前工具执行已停止，只允许根据已有结果收尾，禁止调用工具。
结合完整对话理解本轮目标（用户可能只回复了“1”或“继续”），区分操作成功和整个任务完成。
返回一个 JSON 对象，不要 Markdown：
{"outcome":"completed|partial|needs_information","answer":"面向用户的答复",
"evidence_tool_call_ids":["支持完成结论的本轮成功调用ID"],"remaining_actions":["尚未完成的要求"]}
只有全部用户要求都有真实结果支持时才能 completed；调用成功不等于任务全部完成。
存在未执行动作时用 partial；缺少用户信息时用 needs_information，并明确询问。
answer 必须说明已经完成的操作及实际编号，不能建议重复已完成的写入。
answer 不超过 400 字，只保留关键结论和缺口，不逐项复述完整数据表，确保 JSON 完整。
引用结果必须来自工具返回值；审批通过、准备就绪、模型计划都不是写入成功证据。
汇总与明细不一致时说明数据缺口，不要猜测账目来源或补写原因。
无法确认时返回 partial，不能猜测成功。"""
_REQUESTED_FINALIZATION_PROMPT = """当前已进入最终答复阶段，工具执行已停止，禁止再调用工具。
仅根据已有执行证据用自然语言回答；未查询的日期、天气或其他信息须说明尚未查询，不得猜测。
区分某项操作成功与整个请求完成。已成功写入的业务记录仍有效，说明实际编号，不得否认或建议重复写入。
备忘录属于业务记录，不等于保存个人长期偏好；不要声称未执行的操作已经完成。"""


class FinalizationResult(BaseModel):
    """模型只提交收尾建议，由 Runtime 校验已有证据后决定终态。"""

    model_config = ConfigDict(extra="forbid", strict=True)

    outcome: Literal["completed", "partial", "needs_information"]
    answer: str = Field(min_length=1)
    evidence_tool_call_ids: list[str]
    remaining_actions: list[str]


def record_committed_operation(
    turn: Turn, skill: Skill, args: dict, result: Any, tool_call_id: str
) -> bool:
    """统一记录成功写工具的事实，不将某次写入成功推断为整个任务完成。"""
    if (
        skill.dynamic_risk_level(args) not in WRITE_RISK_LEVELS
        or not isinstance(result, dict)
        or not result
        or result.get("error")
        or result.get("success") is False
        or str(result.get("status") or "").lower() in _UNCOMMITTED_STATUSES
    ):
        return False
    if any(item["tool_call_id"] == tool_call_id for item in turn.committed_operations):
        return False
    turn.committed_operations.append(
        {
            "tool_call_id": tool_call_id,
            "tool_name": skill.name,
            "description": skill.description[:_SUMMARY_MAX_CHARS],
            "result": result,
        }
    )
    return True


def committed_summary(turn: Turn) -> str:
    """从真实写入结果生成兜底摘要，保留编号以避免用户重复创建。"""
    lines = []
    for item in turn.committed_operations:
        result = item["result"]
        label = result.get("message") or item["description"] or "业务操作"
        entity_id = result.get("id")
        identifier = f"（记录编号：{entity_id}）" if entity_id is not None else ""
        lines.append(f"- 已执行：{label}{identifier}")
    return "已确认执行成功的操作：\n" + "\n".join(lines) if lines else ""


def finalization_messages(
    turn: Turn, plan: Any | None, *, structured: bool = True
) -> list[dict]:
    """给收尾模型完整任务上下文与本轮证据，使用独立指令禁止继续决策。"""
    messages = list(turn.messages)
    pending_calls = {}
    for message in messages:
        for call in message.get("tool_calls") or []:
            pending_calls[call["id"]] = call
        if message.get("role") == "tool":
            pending_calls.pop(message.get("tool_call_id"), None)
    # 重复检查发生在业务调用前，最后一批 tool_calls 可能尚无结果。
    # 显式补上“未执行”，满足消息协议，同时不把它加入成功执行证据。
    for call_id, call in pending_calls.items():
        messages.append(
            {
                "role": "tool",
                "tool_call_id": call_id,
                "name": call["function"]["name"],
                "content": json.dumps(
                    {
                        "error": "execution_stopped",
                        "code": "execution_stopped",
                        "message": "本次调用未执行，工具执行已停止。请根据已有结果收尾。",
                    },
                    ensure_ascii=False,
                ),
            }
        )
    evidence = {
        "committed_operations": turn.committed_operations,
        "plan": [
            {
                "description": step.description,
                "skill": step.skill,
                "status": step.status,
            }
            for step in getattr(plan, "steps", [])
        ],
        "tool_results": [
            event["data"] for event in turn.events if event["type"] == "tool_finished"
        ],
    }
    return [
        *messages,
        {
            "role": "system",
            "content": _FINALIZATION_PROMPT
            if structured
            else _REQUESTED_FINALIZATION_PROMPT,
        },
        {
            "role": "user",
            "content": "以下是执行证据，不是新任务：\n"
            + json.dumps(evidence, ensure_ascii=False, default=str),
        },
    ]


def parse_finalization(
    content: str, turn: Turn, plan: Any | None
) -> FinalizationResult:
    """拒绝没有真实调用证据或仍有未完成计划的成功声明。"""
    # 部分兼容模型仍包装完整 JSON 代码块；只剥离外壳，结构和证据校验不放宽。
    fenced = re.fullmatch(r"```(?:json)?\s*\n([\s\S]*?)\n```", content.strip())
    if fenced:
        content = fenced.group(1)
    result = FinalizationResult.model_validate_json(content)
    if not result.answer.strip():
        raise ValueError("finalization_empty_answer")
    successful_ids = {
        event["data"]["tool_call_id"]
        for event in turn.events
        if event["type"] == "tool_finished"
        and not event["data"].get("error")
        and event["data"].get("result") is not None
        and not (
            isinstance(event["data"]["result"], dict)
            and (
                event["data"]["result"].get("error")
                or event["data"]["result"].get("success") is False
                or str(event["data"]["result"].get("status") or "").lower()
                in _UNCOMMITTED_STATUSES
            )
        )
    }
    evidence_ids = set(result.evidence_tool_call_ids)
    if not evidence_ids <= successful_ids:
        raise ValueError("finalization_unknown_evidence")
    claim_text = result.answer
    if any(
        event["type"] == "tool_finished"
        and event["data"].get("tool_call_id") in successful_ids
        and isinstance(event["data"].get("result"), dict)
        and _SETTLEMENT_EVIDENCE_FIELDS <= event["data"]["result"].keys()
        for event in turn.events
    ):
        # 查询账目得到的“（已结算）”或“已结算收入：”是报表状态，不是本轮写入。
        # 仅豁免有工具证据的状态标签；“我已为您结算”等动作声明仍必须有提交证据。
        claim_text = _REPORTED_SETTLEMENT_STATUS.sub("", claim_text.replace("*", ""))
    if claims_write_completion(claim_text) and not turn.committed_operations:
        raise ValueError("finalization_write_without_commit")
    if result.outcome == "completed":
        committed_ids = {item["tool_call_id"] for item in turn.committed_operations}
        if (
            not evidence_ids
            or not committed_ids <= evidence_ids
            or result.remaining_actions
            or any(step.status != "done" for step in getattr(plan, "steps", []))
        ):
            raise ValueError("finalization_incomplete_task")
    elif result.remaining_actions:
        result.answer += "\n未完成事项：" + "；".join(result.remaining_actions)
    return result


async def finalize_turn(
    turn: Turn,
    *,
    answer: str | None = None,
    reason: StopReason = StopReason.STEP_BUDGET_EXHAUSTED,
) -> AsyncGenerator[dict, None]:
    """while 循环结束后：running→completed/terminated。"""
    if turn.committed_result is not None:
        async for ev in finalize_committed_with_fallback(
            turn, "写入已成功，但收尾轮次未生成最终答复。"
        ):
            yield ev
    else:
        fallback_answer = not answer
        answer = answer or (
            "本轮已停止继续调用工具，尚无法确认全部请求已完成。"
            "已完成的操作无需重复执行，后续只需继续未完成的部分。"
        )
        if fallback_answer and not turn.committed_operations:
            results = [
                event["data"]["result"]
                for event in turn.events
                if event["type"] == "tool_finished"
                and not event["data"].get("error")
                and event["data"].get("result") is not None
                and not (
                    isinstance(event["data"]["result"], dict)
                    and (
                        event["data"]["result"].get("error")
                        or event["data"]["result"].get("success") is False
                        or str(event["data"]["result"].get("status") or "").lower()
                        in _UNCOMMITTED_STATUSES
                    )
                )
            ]
            if results:
                # 模型收尾失败仍保留实际结果，不能只剩“请重试”而丢掉本轮工作。
                answer += "\n\n已取得的查询结果摘要（可能截断）：\n" + "\n".join(
                    f"- {json.dumps(result, ensure_ascii=False, default=str)[:_SUMMARY_MAX_CHARS]}"
                    for result in results
                )
        if summary := committed_summary(turn):
            answer = f"{summary}\n\n{answer}"
        message = {
            StopReason.USER_INPUT_REQUIRED: "需要补充信息后继续",
            StopReason.DOOM_LOOP_DETECTED: "重复查询已停止，保留已取得的结果",
            StopReason.LLM_FAILED: "答复生成未完成，保留已确认的执行结果",
        }.get(reason, "已达到本轮执行步数上限，保留已完成的结果")
        turn.record_termination(
            reason,
            message,
            phase=TurnPhase.FINALIZING,
        )
        turn.finalization_pending = False
        turn.final_answer = answer
        yield sse.final_answer_start()
        yield sse.final_answer(answer)
        terminal_ev = sse.turn_terminated(
            turn.turn_id,
            reason=reason.value,
            message=message,
            step_count=turn.step_count,
        )
        turn.emit(terminal_ev["type"], terminal_ev["data"])
        yield terminal_ev


async def finalize_committed_with_fallback(
    turn: Turn, message: str
) -> AsyncGenerator[dict, None]:
    """写入已提交但收尾失败时，用结构化结果生成确定性答复。

    统一处理三种场景：
    - LLM 流式调用失败（_handle_llm_error）
    - 收尾轮仍请求工具（_run_finalization）
    - while 结束后仍未生成答复（finalize_turn）
    """
    ev = sse.write_committed_reply_failed(message)
    turn.emit(ev["type"], ev["data"])
    yield ev
    turn.final_answer = structured_commit_answer(turn.committed_result or {})
    turn.finalization_pending = False
    turn.status = "completed"
    turn.stop_reason = StopReason.MODEL_COMPLETED
    turn.set_phase(TurnPhase.TERMINAL)
    yield sse.final_answer_start()
    yield sse.final_answer(turn.final_answer)
    completed_ev = sse.turn_completed(
        turn.turn_id,
        stop_reason=turn.stop_reason.value,
        step_count=turn.step_count,
    )
    turn.emit(completed_ev["type"], completed_ev["data"])
    yield completed_ev


# ── 辅助函数 ──────────────────────────────────────────────


def structured_commit_answer(result: dict) -> str:
    """LLM 收尾失败时，只使用已提交结果生成确定性答复。"""
    template = result.get("template") or {}
    cycle = result.get("cycle") or {}
    unit = result.get("planting_unit") or {}
    if not all(
        isinstance(item, dict) and item.get("id") for item in (template, cycle, unit)
    ):
        # 通用写工具也复用此收尾器，缺少计划实体不能声称种植计划已创建。
        return str(result.get("message") or "业务操作已完成，但详细结果暂未返回。")
    replay_note = (
        "（本次返回的是已提交请求的幂等结果）"
        if result.get("idempotent_replay")
        else ""
    )
    return (
        "种植计划已提交成功"
        f"{replay_note}：模板“{template.get('name', '未知')}”（ID {template.get('id', '-')}），"
        f"茬口“{cycle.get('name', '未知')}”（ID {cycle.get('id', '-')}），"
        f"种植单元“{unit.get('name', '未知')}”（ID {unit.get('id', '-')}，"
        f"面积 {unit.get('area_mu', '-')} 亩）。"
    )
