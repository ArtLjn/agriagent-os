"""DataFlywheel Judge worker 的纯函数辅助。"""

from __future__ import annotations

import json
import asyncio
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.platforms.evaluation.discovery.risk_scorer import apply_risk_score
from app.agent.turn_models import AgentTurn
from app.platforms.data_flywheel.models import AgentDataFlywheelLabel
from app.platforms.shared.judge_service import OpenAIDataFlywheelJudgeClient

JUDGE_MONTHLY_COST_LIMIT_USD = 200.0
DEFAULT_INPUT_COST_PER_MILLION = 0.25
DEFAULT_OUTPUT_COST_PER_MILLION = 1.25
JUDGE_CONCURRENCY_LIMIT = 32


@dataclass(frozen=True)
class JudgeParseResult:
    """Judge JSON 解析结果。"""

    bad_prob: float | None
    issue_type: str | None
    suggested_label: str | None
    evidence: list[str]
    parse_error: str | None = None


@dataclass(frozen=True)
class JudgeCostDecision:
    """Judge 成本降级判断。"""

    degraded: bool
    mode: str
    reason: str | None = None


@dataclass(frozen=True)
class JudgeBatchSummary:
    """Judge 批处理结果摘要。"""

    processed: int
    updated: int
    skipped: int
    failed: int
    estimated_cost_usd: float
    degraded: bool = False
    reason: str | None = None


def build_judge_prompt(turn_context: dict[str, Any]) -> str:
    """构建要求 Judge 输出结构化 JSON 的提示词。"""

    payload = json.dumps(turn_context, ensure_ascii=False, indent=2, sort_keys=True)
    return (
        "你是 DataFlywheel 标注候选发现层的审查助手。请只判断这个 agent turn "
        "是否值得人工标注，不要写入最终真值。\n"
        "请输出严格 JSON 对象，字段必须包含：\n"
        "- bad_prob: 0 到 1 之间的数字，表示该 turn 是坏例或高风险候选的概率\n"
        "- issue_type: 字符串或 null，简短说明问题类型\n"
        '- suggested_label: "good"、"bad"、"needs_review" 或 null\n'
        "- evidence: 字符串数组，列出支持判断的证据\n\n"
        f"待评估 turn:\n{payload}"
    )


def parse_judge_response(content: str) -> JudgeParseResult:
    """解析 Judge 输出，失败时返回安全兜底结果。"""

    try:
        data = json.loads(_strip_json_fence(content))
        if not isinstance(data, dict):
            raise ValueError("Judge response must be a JSON object")

        bad_prob = data.get("bad_prob")
        if not isinstance(bad_prob, int | float):
            raise ValueError("bad_prob must be a number")
        bad_prob = float(bad_prob)
        if bad_prob < 0 or bad_prob > 1:
            raise ValueError("bad_prob must be between 0 and 1")

        issue_type = data.get("issue_type")
        if issue_type is not None and not isinstance(issue_type, str):
            raise ValueError("issue_type must be a string or null")

        suggested_label = data.get("suggested_label")
        if suggested_label is not None and not isinstance(suggested_label, str):
            raise ValueError("suggested_label must be a string or null")

        evidence = data.get("evidence", [])
        if isinstance(evidence, str):
            evidence = [evidence]
        if not isinstance(evidence, list) or not all(
            isinstance(item, str) for item in evidence
        ):
            raise ValueError("evidence must be a string array")

        return JudgeParseResult(
            bad_prob=bad_prob,
            issue_type=issue_type,
            suggested_label=suggested_label,
            evidence=evidence,
        )
    except (json.JSONDecodeError, ValueError, TypeError) as exc:
        return JudgeParseResult(
            bad_prob=None,
            issue_type="parse_error",
            suggested_label=None,
            evidence=[],
            parse_error=str(exc),
        )


def estimate_usage_cost_usd(
    usage: dict[str, Any],
    *,
    input_cost_per_million: float = DEFAULT_INPUT_COST_PER_MILLION,
    output_cost_per_million: float = DEFAULT_OUTPUT_COST_PER_MILLION,
) -> float:
    """根据 token usage 估算美元成本。"""

    input_tokens = _usage_token_count(usage, "input_tokens", "prompt_tokens")
    output_tokens = _usage_token_count(
        usage,
        "output_tokens",
        "completion_tokens",
    )
    input_cost = input_tokens / 1_000_000 * input_cost_per_million
    output_cost = output_tokens / 1_000_000 * output_cost_per_million
    return input_cost + output_cost


def should_degrade_for_cost(
    month_cost_usd: float,
    *,
    limit_usd: float = JUDGE_MONTHLY_COST_LIMIT_USD,
) -> JudgeCostDecision:
    """月成本超过阈值时降级为 rule-only。"""

    if month_cost_usd > limit_usd:
        return JudgeCostDecision(
            degraded=True,
            mode="rule_only",
            reason="judge_monthly_cost_limit_exceeded",
        )
    return JudgeCostDecision(degraded=False, mode="judge")


def run_judge_batch(
    db: Session,
    *,
    judge_client: Any,
    month_cost_usd: float,
    limit: int = 1000,
    now: datetime | None = None,
) -> JudgeBatchSummary:
    """批量评估前 24h 未人工标注且未 judge 的 turn。"""

    cost_decision = should_degrade_for_cost(month_cost_usd)
    if cost_decision.degraded:
        return JudgeBatchSummary(
            processed=0,
            updated=0,
            skipped=0,
            failed=0,
            estimated_cost_usd=0.0,
            degraded=True,
            reason=cost_decision.reason,
        )

    candidates = _judge_candidates(db, now=now or datetime.now(), limit=limit)
    updated = 0
    failed = 0
    estimated_cost = 0.0
    for turn in candidates:
        payload = _turn_payload(turn)
        try:
            raw = judge_client.judge(payload)
            parsed = _parse_judge_raw(raw)
            if parsed.bad_prob is None:
                failed += 1
                continue
            _apply_judge_result(turn, parsed)
            estimated_cost += estimate_usage_cost_usd(raw.get("usage") or {})
            updated += 1
        except Exception:
            failed += 1
    db.commit()
    return JudgeBatchSummary(
        processed=len(candidates),
        updated=updated,
        skipped=0,
        failed=failed,
        estimated_cost_usd=estimated_cost,
    )


async def run_judge_batch_async(
    db: Session,
    *,
    judge_client: Any,
    month_cost_usd: float,
    limit: int = 1000,
    now: datetime | None = None,
    concurrency: int = JUDGE_CONCURRENCY_LIMIT,
) -> JudgeBatchSummary:
    """异步入口，使用 Semaphore(32) 控制批处理并发。"""

    semaphore = asyncio.Semaphore(concurrency)
    async with semaphore:
        return await asyncio.to_thread(
            run_judge_batch,
            db,
            judge_client=judge_client,
            month_cost_usd=month_cost_usd,
            limit=limit,
            now=now,
        )


def build_default_judge_client() -> OpenAIDataFlywheelJudgeClient:
    """通过 LLM manager 构造轻量 Judge client。"""

    from app.shared.llm import get_llm_manager

    manager = get_llm_manager()
    client, info = manager.get_sync_client_with_info(role="lightweight")
    return OpenAIDataFlywheelJudgeClient(client=client, judge_model=str(info["model"]))


def register_daily_judge_job(scheduler: Any, job_func: Any) -> None:
    """注册每天 02:00 的 Judge job，适配 APScheduler 风格对象。"""

    scheduler.add_job(job_func, "cron", hour=2, minute=0, id="dataflywheel_judge")


def _usage_token_count(usage: dict[str, Any], *keys: str) -> int:
    for key in keys:
        value = usage.get(key)
        if value is not None:
            return int(value)
    return 0


def _strip_json_fence(content: str) -> str:
    stripped = content.strip()
    if not stripped.startswith("```"):
        return stripped
    lines = stripped.splitlines()
    if lines and lines[0].startswith("```"):
        lines = lines[1:]
    if lines and lines[-1].startswith("```"):
        lines = lines[:-1]
    return "\n".join(lines).strip()


def _judge_candidates(db: Session, *, now: datetime, limit: int) -> list[AgentTurn]:
    since = now - timedelta(hours=24)
    human_labeled_turn_ids = select(AgentDataFlywheelLabel.turn_id).where(
        AgentDataFlywheelLabel.turn_id.isnot(None),
        AgentDataFlywheelLabel.annotator_id.isnot(None),
    )
    return (
        db.query(AgentTurn)
        .filter(
            AgentTurn.created_at >= since,
            AgentTurn.judge_bad_prob.is_(None),
            ~AgentTurn.id.in_(human_labeled_turn_ids),
        )
        .order_by(AgentTurn.created_at.asc(), AgentTurn.id.asc())
        .limit(max(limit, 0))
        .all()
    )


def _turn_payload(turn: AgentTurn) -> dict[str, Any]:
    return {
        "turn_id": turn.id,
        "session_id": turn.session_id,
        "request_id": turn.request_id,
        "user_message": turn.input_preview,
        "reply_preview": turn.reply_preview,
        "status": turn.status,
        "rule_score": turn.rule_score,
        "rule_hits": turn.rule_hits or [],
    }


def _apply_judge_result(turn: AgentTurn, parsed: JudgeParseResult) -> None:
    if _is_low_risk_chitchat_turn(turn):
        turn.judge_bad_prob = 0.0
        turn.judge_issue_type = "benign_chitchat"
        turn.judge_suggested_label = "not_actionable"
    else:
        turn.judge_bad_prob = parsed.bad_prob
        turn.judge_issue_type = parsed.issue_type
        turn.judge_suggested_label = parsed.suggested_label
    apply_risk_score(
        turn,
        rule_score=turn.rule_score,
        judge_bad_prob=turn.judge_bad_prob,
    )


def _is_low_risk_chitchat_turn(turn: AgentTurn) -> bool:
    if turn.rule_hits or (turn.rule_score or 0.0) > 0:
        return False
    if (turn.selected_tools_count or 0) > 0 or (turn.tool_calls_count or 0) > 0:
        return False
    user_text = str(turn.input_preview or "").strip().lower()
    reply_text = str(turn.reply_preview or "").strip()
    return _is_greeting_text(user_text) and _looks_like_greeting_reply(reply_text)


def _is_greeting_text(text: str) -> bool:
    return text in {"hi", "hello", "hey", "你好", "您好", "嗨", "哈喽"}


def _looks_like_greeting_reply(text: str) -> bool:
    if not text:
        return False
    if any(term in text for term in ("工具", "已", "工资", "成本", "删除", "创建", "结算")):
        return False
    return any(term in text for term in ("你好", "您好", "帮", "看看", "记一笔", "农场"))


def _parse_judge_raw(raw: Any) -> JudgeParseResult:
    if not isinstance(raw, dict):
        return parse_judge_response("")
    return parse_judge_response(json.dumps(raw, ensure_ascii=False))
