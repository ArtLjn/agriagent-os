"""直接执行 skillify Skill，保留结构化 SkillResult。"""

import time
from typing import Any

from skillify.models.schemas import ResultStatus, SkillResult

from app.agent.executor.pending_aliases import pending_alias_metadata
from app.infra.trace_collector import get_collector
from app.skills import build_skill_context, get_skill_registry


async def execute_write_skill_raw(
    farm_id: int,
    skill_name: str,
    params: dict[str, Any],
    farm_uid: str | None = None,
) -> SkillResult:
    """绕过 LangChain 字符串 wrapper，直接返回 SkillResult。"""
    start = time.time()
    error_msg = None
    alias_metadata: dict[str, Any] = {}
    result: SkillResult | None = None
    execution_params = dict(params or {})
    try:
        alias_metadata = pending_alias_metadata(skill_name, execution_params)
        resolved_skill_name = alias_metadata.get("resolved_capability") or skill_name
        if resolved_skill_name != skill_name and alias_metadata.get(
            "resolved_operation"
        ):
            execution_params.setdefault(
                "operation", alias_metadata["resolved_operation"]
            )

        registry = get_skill_registry()
        skill = registry.get(resolved_skill_name) or registry.get(skill_name)
        if skill is None:
            result = SkillResult(
                status=ResultStatus.FAILED,
                reply=f"未知工具: {skill_name}",
            )
            return result

        context = build_skill_context(farm_id=farm_id, farm_uid=farm_uid)
        result = await skill.execute(execution_params, context)
        return result
    except Exception as exc:
        error_msg = str(exc)
        raise
    finally:
        output_data = {
            "status": _result_status(result) if result is not None else "failed",
            "reply_preview": _result_reply(result)[:500] if result is not None else "",
            **alias_metadata,
        }
        if not alias_metadata:
            output_data["legacy_tool_name"] = skill_name
            output_data["alias_resolution"] = "missing"
        get_collector().record(
            node_type="skill_call",
            node_name=skill_name,
            input_data=execution_params,
            output_data=output_data,
            start_time=start,
            end_time=time.time(),
            error_message=error_msg,
        )


def _result_status(result: SkillResult | None) -> str:
    if result is None:
        return "failed"
    status = getattr(result, "status", None)
    text = str(getattr(status, "value", status) or "").lower()
    if "." in text:
        text = text.rsplit(".", maxsplit=1)[-1]
    return text


def _result_reply(result: SkillResult | None) -> str:
    return str(getattr(result, "reply", "") or "") if result is not None else ""
