"""每日建议 v2 生成、重试、fallback 与缓存编排。"""

from __future__ import annotations

import json
import logging
from collections.abc import Awaitable, Callable
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from app.agent.reflector.daily_advice import check_daily_advice_generation
from app.agent.reflector.models import ReflectionDecision, ReflectionResult
from app.agent.runtime.support import QUOTA_REJECT_MESSAGES
from app.core.json_repair import safe_parse_json
from app.infra.repository_runtime import (
    get_agent_record_repository,
    run_maybe_awaitable,
)
from app.models.agent_record import AgentRecord
from app.schemas.agent import DailyAdviceGeneration, DailyAdviceResponse
from app.services.daily_advice_models import (
    DailyAdviceCandidate,
    build_daily_advice_empty_response,
    build_daily_advice_item_skeletons,
    build_daily_advice_overview,
    fingerprint_candidates,
    rank_daily_advice_candidates,
    render_candidate_context,
)
from app.services.daily_advice_signals import collect_daily_advice_candidates

logger = logging.getLogger(__name__)

SCHEMA_VERSION = "daily_advice_v2"
MAX_RETRY_COUNT = 2
_ADVICE_ITEM_MAX = 5
_HOMEPAGE_ADVICE_ITEM_MAX = 3
_NON_ADVICE_MARKERS = (
    "缺少可信用户上下文",
    "配额",
    "quota",
    "error",
    "错误",
    "无法继续处理",
)
_NON_ADVICE_RESPONSES = set(QUOTA_REJECT_MESSAGES.values())

InvokeAdvisor = Callable[..., Awaitable[str]]
GetComposer = Callable[[], Any]


class _DailyAdvicePayloadTruncated(ValueError):
    """LLM 返回的 DailyAdvice JSON 明显被截断。"""

    pass


async def generate_daily_advice(
    db: Session,
    *,
    farm_id: int,
    cycle_id: int | None,
    user_id: str | None,
    invoke_advisor: InvokeAdvisor,
    get_composer: GetComposer,
) -> DailyAdviceResponse:
    """生成每日建议 v2 响应，负责缓存、retry 和 fallback。"""
    today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    selected_candidates = await _collect_selected_candidates(db, farm_id)
    candidate_fingerprint = fingerprint_candidates(selected_candidates)

    cached = _load_matching_cache(
        db,
        farm_id=farm_id,
        today_start=today_start,
        candidate_fingerprint=candidate_fingerprint,
    )
    if cached is not None:
        return cached

    if not selected_candidates:
        response = build_daily_advice_empty_response(cycle_id=cycle_id)
        response.generation.candidate_fingerprint = candidate_fingerprint
        return response

    response, meta = await _run_generation_attempts(
        db,
        farm_id=farm_id,
        cycle_id=cycle_id,
        user_id=user_id,
        selected_candidates=selected_candidates,
        candidate_fingerprint=candidate_fingerprint,
        invoke_advisor=invoke_advisor,
        get_composer=get_composer,
    )
    record = _save_daily_advice_record(
        db,
        farm_id=farm_id,
        cycle_id=cycle_id,
        response=response,
        meta=meta,
    )
    response.created_at = record.created_at
    return response


async def _collect_selected_candidates(
    db: Session,
    farm_id: int,
) -> list[DailyAdviceCandidate]:
    candidates = await collect_daily_advice_candidates(db, farm_id=farm_id)
    return rank_daily_advice_candidates(candidates, limit=_ADVICE_ITEM_MAX)


def _load_matching_cache(
    db: Session,
    *,
    farm_id: int,
    today_start: datetime,
    candidate_fingerprint: str,
) -> DailyAdviceResponse | None:
    cached = run_maybe_awaitable(
        get_agent_record_repository(db).find_daily_cache(
            farm_id=farm_id,
            since=today_start,
        )
    )
    if cached is None:
        return None

    meta = _parse_record_meta(cached.meta)
    if meta.get("schema_version") != SCHEMA_VERSION:
        logger.info("忽略非 v2 今日建议缓存 | record_id=%s", cached.id)
        return None
    if meta.get("candidate_fingerprint") != candidate_fingerprint:
        logger.info("忽略候选指纹不匹配的今日建议缓存 | record_id=%s", cached.id)
        return None

    try:
        payload = safe_parse_json(cached.content)
        response = DailyAdviceResponse.model_validate(payload)
    except (TypeError, ValueError) as exc:
        logger.warning(
            "忽略无法解析的 v2 今日建议缓存 | record_id=%s error=%s", cached.id, exc
        )
        return None

    response.items = _limit_homepage_items(response.items)
    response.created_at = cached.created_at
    response.generation.cache_hit = True
    response.generation.candidate_fingerprint = candidate_fingerprint
    return response


async def _run_generation_attempts(
    db: Session,
    *,
    farm_id: int,
    cycle_id: int | None,
    user_id: str | None,
    selected_candidates: list[DailyAdviceCandidate],
    candidate_fingerprint: str,
    invoke_advisor: InvokeAdvisor,
    get_composer: GetComposer,
) -> tuple[DailyAdviceResponse, dict[str, Any]]:
    validation_errors: list[str] = []
    repair_instruction = ""
    last_reflection: ReflectionResult | None = None
    fallback_retry_count = MAX_RETRY_COUNT

    for attempt_index in range(MAX_RETRY_COUNT + 1):
        fallback_retry_count = attempt_index
        prompt = _compose_prompt(
            get_composer,
            selected_candidates=selected_candidates,
            cycle_id=cycle_id,
            candidate_fingerprint=candidate_fingerprint,
            repair_instruction=repair_instruction,
        )
        raw = await invoke_advisor(
            prompt,
            farm_id=farm_id,
            db=db,
            user_id=user_id,
            call_type="daily_advice",
        )
        try:
            payload, parse_repair_instruction = _parse_llm_payload(raw)
        except _DailyAdvicePayloadTruncated as exc:
            logger.warning(
                "DailyAdvice v2 JSON 明显截断，直接进入 fallback | error=%s", exc
            )
            validation_errors.append("llm_json_truncated")
            break
        if payload is None:
            error_code = (
                "llm_json_parse_failed"
                if parse_repair_instruction
                else "empty_or_non_advice_llm_response"
            )
            validation_errors.append(error_code)
            if parse_repair_instruction:
                repair_instruction = parse_repair_instruction
            continue

        payload = _normalize_generation_payload(
            payload,
            mode="llm" if attempt_index == 0 else "repaired",
            retry_count=attempt_index,
            candidate_fingerprint=candidate_fingerprint,
        )
        reflection = check_daily_advice_generation(
            payload,
            selected_candidates,
            farm_id=farm_id,
            candidate_fingerprint=candidate_fingerprint,
            retry_index=attempt_index,
            generation_mode=payload["generation"]["mode"],
        )
        last_reflection = reflection
        issue_codes = [issue.code for issue in reflection.issues]
        if issue_codes:
            validation_errors.extend(issue_codes)
        if reflection.decision == ReflectionDecision.PASS:
            response = DailyAdviceResponse.model_validate(payload)
            response.items = _limit_homepage_items(response.items)
            response.generation.cache_hit = False
            response.generation.candidate_fingerprint = candidate_fingerprint
            mode = "llm" if attempt_index == 0 else "repaired"
            response.generation.mode = mode
            return response, _build_cache_meta(
                selected_candidates=selected_candidates,
                candidate_fingerprint=candidate_fingerprint,
                generation_mode=mode,
                retry_count=attempt_index,
                reflection_decision=reflection.decision.value,
                validation_errors=validation_errors,
            )
        repair_instruction = str(reflection.metadata.get("repair_instruction") or "")

    return _build_fallback_result(
        cycle_id=cycle_id,
        selected_candidates=selected_candidates,
        candidate_fingerprint=candidate_fingerprint,
        retry_count=fallback_retry_count,
        validation_errors=validation_errors,
        reflection=last_reflection,
    )


def _compose_prompt(
    get_composer: GetComposer,
    *,
    selected_candidates: list[DailyAdviceCandidate],
    cycle_id: int | None,
    candidate_fingerprint: str,
    repair_instruction: str,
) -> str:
    skeletons = [
        item.model_dump(mode="json")
        for item in build_daily_advice_item_skeletons(selected_candidates)
    ]
    skeletons_json = json.dumps(skeletons, ensure_ascii=False, indent=2)
    return get_composer().compose(
        "daily_advice",
        variables={
            "farm_context": render_candidate_context(selected_candidates),
            "cycle_id": cycle_id,
            "candidate_skeletons_json": skeletons_json,
            "candidate_fingerprint": candidate_fingerprint,
            "repair_instruction": repair_instruction,
            "schema_version": SCHEMA_VERSION,
        },
    )


def _parse_llm_payload(raw: str) -> tuple[dict[str, Any] | None, str]:
    text = raw.strip()
    if not text or _is_non_advice_response(text):
        return None, ""
    try:
        parsed = safe_parse_json(text)
    except ValueError as exc:
        if _looks_like_truncated_json(text):
            raise _DailyAdvicePayloadTruncated(str(exc)) from exc
        logger.warning(
            "DailyAdvice v2 JSON 解析失败，将进入 fallback/retry | error=%s", exc
        )
        return None, _build_json_parse_repair_instruction(exc)
    return (parsed, "") if isinstance(parsed, dict) else (None, "")


def _looks_like_truncated_json(text: str) -> bool:
    """识别输出在对象中途被截断的 JSON。"""
    stripped = text.rstrip()
    if not stripped.startswith("{"):
        return False
    if stripped.endswith(("}", "]", "```")):
        return False
    return _has_unclosed_string(stripped)


def _has_unclosed_string(text: str) -> bool:
    escaped = False
    in_string = False
    for char in text:
        if escaped:
            escaped = False
            continue
        if char == "\\":
            escaped = True
            continue
        if char == '"':
            in_string = not in_string
    return in_string


def _build_json_parse_repair_instruction(error: ValueError) -> str:
    """生成 JSON 解析失败后的重试约束。"""
    return (
        "上次返回不是合法 JSON，解析错误："
        f"{error}。请只返回合法 JSON 对象，不要输出解释、Markdown、代码块、"
        "逗号后的中文说明或任何 JSON 外文本；字段必须使用英文双引号。"
    )


def _normalize_generation_payload(
    payload: dict[str, Any],
    *,
    mode: str,
    retry_count: int,
    candidate_fingerprint: str,
) -> dict[str, Any]:
    normalized = dict(payload)
    generation = dict(normalized.get("generation") or {})
    generation.update(
        {
            "schema_version": SCHEMA_VERSION,
            "mode": mode,
            "retry_count": retry_count,
            "cache_hit": False,
            "candidate_fingerprint": candidate_fingerprint,
        }
    )
    normalized["generation"] = generation
    normalized.setdefault("created_at", datetime.now().isoformat())
    normalized.setdefault(
        "overview",
        build_daily_advice_overview().model_dump(mode="json"),
    )
    return normalized


def _build_fallback_result(
    *,
    cycle_id: int | None,
    selected_candidates: list[DailyAdviceCandidate],
    candidate_fingerprint: str,
    retry_count: int,
    validation_errors: list[str],
    reflection: ReflectionResult | None,
) -> tuple[DailyAdviceResponse, dict[str, Any]]:
    response = DailyAdviceResponse(
        cycle_id=cycle_id,
        preview="今日建议",
        overview=build_daily_advice_overview(work_order_count=len(selected_candidates)),
        items=build_daily_advice_item_skeletons(selected_candidates),
        generation=DailyAdviceGeneration(
            mode="fallback",
            retry_count=retry_count,
            cache_hit=False,
            candidate_fingerprint=candidate_fingerprint,
        ),
        created_at=datetime.now(),
    )
    response.items = _limit_homepage_items(response.items)
    return response, _build_cache_meta(
        selected_candidates=selected_candidates,
        candidate_fingerprint=candidate_fingerprint,
        generation_mode="fallback",
        retry_count=retry_count,
        reflection_decision=(
            reflection.decision.value
            if reflection
            else ReflectionDecision.FALLBACK_RESPONSE.value
        ),
        validation_errors=validation_errors or ["llm_generation_failed"],
    )


def _save_daily_advice_record(
    db: Session,
    *,
    farm_id: int,
    cycle_id: int | None,
    response: DailyAdviceResponse,
    meta: dict[str, Any],
) -> AgentRecord:
    record = AgentRecord(
        cycle_id=cycle_id,
        record_type="daily",
        content=response.model_dump_json(),
        farm_id=farm_id,
        meta=json.dumps(meta, ensure_ascii=False),
    )
    try:
        record = run_maybe_awaitable(get_agent_record_repository(db).create(record))
    except Exception:
        db.rollback()
        raise
    return record


def _build_cache_meta(
    *,
    selected_candidates: list[DailyAdviceCandidate],
    candidate_fingerprint: str,
    generation_mode: str,
    retry_count: int,
    reflection_decision: str,
    validation_errors: list[str],
) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "generation_mode": generation_mode,
        "retry_count": retry_count,
        "reflection_decision": reflection_decision,
        "validation_errors": _dedupe(validation_errors),
        "candidate_fingerprint": candidate_fingerprint,
        "selected_candidates": [
            candidate.to_meta() for candidate in selected_candidates
        ],
    }


def _parse_record_meta(raw: str | None) -> dict[str, Any]:
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
    except (TypeError, json.JSONDecodeError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _limit_homepage_items(items: list[Any]) -> list[Any]:
    return items[:_HOMEPAGE_ADVICE_ITEM_MAX]


def _is_non_advice_response(text: str) -> bool:
    lowered = text.lower()
    if text in _NON_ADVICE_RESPONSES:
        return True
    return any(marker in lowered or marker in text for marker in _NON_ADVICE_MARKERS)


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


__all__ = ["generate_daily_advice"]
