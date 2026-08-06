"""Final Agent 上下文边界与输出防泄漏。"""

import json
import logging
import re
from dataclasses import dataclass, field
from typing import Any

from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)

from app.agent.runtime.exception_logging import log_silent_exception
from app.agent.runtime.messages import _extract_tool_calls_from_content
from app.agent.runtime.audit_logging import log_agent_audit
from app.context.core.models import ContextBundle
from app.context.pipeline import compact_tool_result, safe_preview, safe_trace_value

logger = logging.getLogger(__name__)

_STRICT_FINAL_SUFFIX = (
    "\n\n【最终回复边界】你现在处于 final_response 阶段。"
    "只能基于用户问题、上下文和工具结果摘要生成自然中文；"
    "不得输出 JSON、工具名参数结构或任何工具协议字段；"
    "不得声称还需要先调用工具。"
)
_RETRY_FINAL_SUFFIX = (
    "\n\n【更严格的最终回复要求】上一版回复包含工具协议或 JSON。"
    "请重新生成一句或多句自然中文答案，只保留面向用户的结论。"
)
_PROTOCOL_KEYWORD_RE = re.compile(
    r"\b(tool_calls?|function_call|arguments|tool_call_id|bind_tools)\b"
    r"|需要先调用工具|不需要.*调用工具|无需.*调用工具|不用.*调用工具",
    re.IGNORECASE,
)
_JSON_OBJECT_RE = re.compile(r"\{(?:[^{}]|\{[^{}]*\})*\}", re.DOTALL)
_FAILED_TOOL_CONTENT_RE = re.compile(
    r"(工具调用失败|未知工具|参数校验失败|tool_not_found|validation_error|skill_call_failed)",
    re.IGNORECASE,
)


@dataclass(slots=True)
class ToolResultSummary:
    """Final Agent 可消费的工具结果摘要。"""

    tool_name: str
    status: str
    facts: list[str] = field(default_factory=list)
    tool_call_id: str = ""

    def to_prompt_text(self) -> str:
        facts = "；".join(self.facts) if self.facts else "工具返回了结果。"
        return f"- {self.tool_name}（{self.status}）：{facts}"

    def to_trace_payload(self) -> dict[str, Any]:
        return {
            "tool_name": self.tool_name,
            "status": self.status,
            "fact_count": len(self.facts),
            "facts": list(self.facts[:5]),
            "tool_call_id": self.tool_call_id,
        }


@dataclass(slots=True)
class FinalResponseConstraints:
    """Final Agent 输出约束。"""

    language: str = "zh-CN"
    forbid_tool_protocol: bool = True
    forbid_json_output: bool = True
    strict_final_only: bool = False


@dataclass(slots=True)
class SafeContextBlock:
    """Final Agent 安全上下文块摘要。"""

    key: str
    source: str
    content_preview: str

    def to_prompt_text(self) -> str:
        return f"- {self.key}（{self.source}）：{self.content_preview}"

    def to_trace_payload(self) -> dict[str, str]:
        return {
            "key": self.key,
            "source": self.source,
            "content_preview": self.content_preview,
        }


@dataclass(slots=True)
class FinalResponseRequest:
    """Final LLM 调用的唯一安全输入契约。"""

    system_prompt: str
    user_query: str
    tool_results: list[ToolResultSummary]
    context_blocks: list[SafeContextBlock] = field(default_factory=list)
    constraints: FinalResponseConstraints = field(
        default_factory=FinalResponseConstraints
    )
    trace_metadata: dict[str, Any] = field(default_factory=dict)

    def to_llm_input(self, *, strict: bool = False) -> tuple[SystemMessage, list]:
        system_text = self.system_prompt + _STRICT_FINAL_SUFFIX
        if strict:
            system_text += _RETRY_FINAL_SUFFIX
        return SystemMessage(content=system_text), [
            HumanMessage(content=self._user_text())
        ]

    def has_reliable_tool_results(self) -> bool:
        return any(result.status == "success" for result in self.tool_results)

    def _user_text(self) -> str:
        sections = [f"用户问题：{self.user_query}"]
        if self.tool_results:
            sections.append(
                "工具结果摘要：\n"
                + "\n".join(result.to_prompt_text() for result in self.tool_results)
            )
        if self.context_blocks:
            sections.append(
                "可引用上下文：\n"
                + "\n".join(block.to_prompt_text() for block in self.context_blocks)
            )
        sections.append("请直接给用户自然中文结论，不要输出工具协议或 JSON。")
        return "\n\n".join(sections)


@dataclass(slots=True)
class OutputGuardCheck:
    """Output Guard 单次检测结果。"""

    passed: bool
    leak_type: str | None = None


class FinalContextBuilder:
    """把 ReAct 历史投影为 Final Agent 安全输入。"""

    def build(
        self,
        *,
        state: dict,
        system_text: str,
        context_bundle: ContextBundle | None,
        collector=None,
    ) -> FinalResponseRequest:
        messages = list(state.get("messages") or [])
        user_query = _last_human_content(messages)
        tool_names_by_id, dropped_tool_call_history = _tool_call_names(messages)
        tool_results = _tool_result_summaries(messages, tool_names_by_id)
        dropped_tool_call_history = dropped_tool_call_history or bool(tool_results)
        context_blocks = _safe_context_blocks(context_bundle)
        request = FinalResponseRequest(
            system_prompt=system_text,
            user_query=user_query,
            tool_results=tool_results,
            context_blocks=context_blocks,
            trace_metadata={
                "source_message_count": len(messages),
                "final_message_count": 1,
                "tool_result_count": len(tool_results),
                "dropped_tool_call_history": dropped_tool_call_history,
            },
        )
        _record_final_context_trace(collector, request)
        return request


def check_final_output_leak(response: AIMessage) -> OutputGuardCheck:
    """检测 final 回复是否泄漏工具协议或 JSON。"""
    if getattr(response, "tool_calls", None):
        return OutputGuardCheck(False, "native_tool_calls")
    content = str(response.content or "").strip()
    if not content:
        return OutputGuardCheck(True)
    if _extract_tool_calls_from_content(content):
        return OutputGuardCheck(False, "content_tool_call_json")
    parsed = _parse_json(content)
    if _looks_like_tool_call_json(parsed):
        return OutputGuardCheck(False, "content_tool_call_json")
    if _PROTOCOL_KEYWORD_RE.search(content):
        return OutputGuardCheck(False, "protocol_keyword")
    if isinstance(parsed, dict):
        return OutputGuardCheck(False, "raw_json_object")
    if isinstance(parsed, list):
        return OutputGuardCheck(False, "raw_json_output")
    fragment_leak_type = _json_fragment_leak_type(content)
    if fragment_leak_type:
        return OutputGuardCheck(False, fragment_leak_type)
    return OutputGuardCheck(True)


async def guard_final_response(
    *,
    response: AIMessage,
    llm,
    request: FinalResponseRequest,
    collector,
) -> AIMessage:
    """执行 final 输出防泄漏、一次重试和 fail-closed。"""
    first_check = check_final_output_leak(response)
    if first_check.passed:
        _record_output_guard_trace(
            collector,
            passed=True,
            leak_type=None,
            action="pass",
            retry_count=0,
        )
        return _with_final_response_metadata(response, request=request, action="pass")

    try:
        retry_response = await _retry_final_response(llm=llm, request=request)
    except Exception as exc:
        log_silent_exception(
            logger,
            level=logging.WARNING,
            function="guard_final_response",
            agent_event="final_response.guard_final_response",
            exc=exc,
        )
        _record_output_guard_trace(
            collector,
            passed=False,
            leak_type=first_check.leak_type,
            action="fail_closed",
            retry_count=1,
        )
        return _guarded_message(
            response,
            fail_closed_final_response(request),
            action="fail_closed",
            request=request,
        )
    retry_check = check_final_output_leak(retry_response)
    if retry_check.passed:
        _record_output_guard_trace(
            collector,
            passed=True,
            leak_type=first_check.leak_type,
            action="retry_passed",
            retry_count=1,
        )
        return _with_final_response_metadata(
            retry_response,
            request=request,
            action="retry_passed",
        )

    extracted = extract_safe_natural_language(str(retry_response.content or ""))
    if extracted:
        _record_output_guard_trace(
            collector,
            passed=False,
            leak_type=retry_check.leak_type or first_check.leak_type,
            action="extract_natural_language",
            retry_count=1,
        )
        return _guarded_message(
            retry_response,
            extracted,
            action="extract_natural_language",
            request=request,
        )

    _record_output_guard_trace(
        collector,
        passed=False,
        leak_type=retry_check.leak_type or first_check.leak_type,
        action="fail_closed",
        retry_count=1,
    )
    return _guarded_message(
        retry_response,
        fail_closed_final_response(request),
        action="fail_closed",
        request=request,
    )


def extract_safe_natural_language(content: str) -> str | None:
    """从二次泄漏文本中抽取明确的自然语言部分。"""
    text = str(content or "").strip()
    if not text:
        return None
    without_json = _JSON_OBJECT_RE.sub("", text).strip()
    without_json = re.sub(r"\s+", " ", without_json).strip(" \n\t:：,，")
    if not without_json or without_json == text:
        return None
    probe = AIMessage(content=without_json)
    if check_final_output_leak(probe).passed:
        return without_json
    return None


def fail_closed_final_response(request: FinalResponseRequest) -> str:
    """返回区分工具结果可靠性的 fail-closed 文案。"""
    if request.has_reliable_tool_results():
        return (
            "已拿到工具结果，但最终回复格式异常。"
            "为避免返回工具协议内容，我先不展示这次异常回复。"
            "请你换个问法或稍后重试。"
        )
    return "没有可靠结果可展示。请你换个问法或稍后再试。"


def _last_human_content(messages: list[BaseMessage]) -> str:
    for message in reversed(messages):
        if isinstance(message, HumanMessage):
            return str(message.content or "")
    return ""


def _tool_call_names(messages: list[BaseMessage]) -> tuple[dict[str, str], bool]:
    names: dict[str, str] = {}
    dropped = False
    for message in messages:
        calls = getattr(message, "tool_calls", None) or []
        if not calls:
            continue
        dropped = True
        for call in calls:
            call_id = str(call.get("id") or "")
            name = str(call.get("name") or "")
            if call_id and name:
                names[call_id] = name
    return names, dropped


def _tool_result_summaries(
    messages: list[BaseMessage], tool_names_by_id: dict[str, str]
) -> list[ToolResultSummary]:
    summaries: list[ToolResultSummary] = []
    for message in messages:
        if not isinstance(message, ToolMessage):
            continue
        tool_call_id = str(getattr(message, "tool_call_id", "") or "")
        tool_name = (
            str(getattr(message, "name", "") or "")
            or tool_names_by_id.get(tool_call_id)
            or "unknown"
        )
        content = str(message.content or "")
        status = _tool_result_status(message, content)
        summaries.append(
            ToolResultSummary(
                tool_name=tool_name,
                status=status,
                facts=_facts_from_tool_content(content, tool_name),
                tool_call_id=tool_call_id,
            )
        )
    return summaries


def _tool_result_status(message: ToolMessage, content: str) -> str:
    """在 final 边界识别未显式标记 status 的失败工具结果。"""
    if _looks_like_failed_tool_content(content):
        return "error"
    return str(getattr(message, "status", "") or "success")


def _looks_like_failed_tool_content(content: str) -> bool:
    text = str(content or "").strip()
    if not text:
        return False
    if _FAILED_TOOL_CONTENT_RE.search(text):
        return True
    parsed = _parse_json(text)
    if not isinstance(parsed, dict):
        return False
    if "error" in parsed:
        return True
    status = str(parsed.get("status") or "").lower()
    return status in {"error", "failed", "failure", "validation_error"}


def _facts_from_tool_content(content: str, tool_name: str) -> list[str]:
    compacted = compact_tool_result(
        content=content,
        tool_name=tool_name,
        tool_call_id="",
        max_summary_chars=600,
    )
    parsed = _parse_json(content)
    if isinstance(parsed, dict):
        ordered_items = sorted(
            parsed.items(),
            key=lambda item: (
                0
                if str(item[0]).lower() in {"result", "answer", "output", "value"}
                else 1
            ),
        )
        facts = []
        for key, value in ordered_items:
            if key in {"tool_calls", "function_call", "arguments"}:
                continue
            fact = f"{key}: {safe_trace_value(value, max_chars=120)}"
            facts.append(_bounded_fact_preview(fact, max_chars=180))
        if facts:
            return facts[:8]
    return [safe_preview(compacted, max_chars=600)] if compacted else []


def _safe_context_blocks(
    context_bundle: ContextBundle | None,
) -> list[SafeContextBlock]:
    if context_bundle is None:
        return []
    blocks: list[SafeContextBlock] = []
    for block in context_bundle.blocks[:8]:
        blocks.append(
            SafeContextBlock(
                key=str(block.key),
                source=str(block.source),
                content_preview=safe_preview(str(block.content or ""), max_chars=300),
            )
        )
    return blocks


def _parse_json(content: str):
    try:
        return json.loads(content)
    except (TypeError, json.JSONDecodeError):
        return None


def _json_fragment_leak_type(content: str) -> str | None:
    decoder = json.JSONDecoder()
    text = str(content or "")
    for index, char in enumerate(text):
        if char not in "{[":
            continue
        try:
            parsed, _end = decoder.raw_decode(text[index:])
        except json.JSONDecodeError:
            continue
        if _looks_like_tool_call_json(parsed):
            return "content_tool_call_json"
        if isinstance(parsed, dict):
            return "raw_json_object"
        if isinstance(parsed, list):
            return "raw_json_output"
    return None


def _bounded_fact_preview(text: str, *, max_chars: int) -> str:
    preview = safe_preview(text, max_chars=max_chars)
    if len(preview) <= max_chars:
        return preview
    if max_chars <= 3:
        return preview[:max_chars]
    return preview[: max_chars - 3] + "..."


def _looks_like_tool_call_json(parsed) -> bool:
    if not isinstance(parsed, dict):
        return False
    name_keys = {"name", "action", "tool", "function"}
    args_keys = {"parameters", "params", "args", "arguments"}
    return bool(name_keys & parsed.keys()) and bool(args_keys & parsed.keys())


def _retry_final_response(*, llm, request: FinalResponseRequest):
    system, messages = request.to_llm_input(strict=True)
    return llm.ainvoke([system] + messages)


def _guarded_message(
    response: AIMessage,
    content: str,
    *,
    action: str,
    request: FinalResponseRequest,
) -> AIMessage:
    return _with_final_response_metadata(
        response,
        content=content,
        request=request,
        action=action,
    )


def _with_final_response_metadata(
    response: AIMessage,
    *,
    request: FinalResponseRequest,
    action: str,
    content: str | None = None,
) -> AIMessage:
    metadata = dict(response.response_metadata or {})
    metadata["output_guard"] = {"action": action}
    metadata["final_response"] = {
        "boundary": "final_response",
        "has_reliable_tool_results": request.has_reliable_tool_results(),
        "tool_result_count": len(request.tool_results),
    }
    return AIMessage(
        content=response.content if content is None else content,
        additional_kwargs=response.additional_kwargs,
        response_metadata=metadata,
        id=response.id,
        name=response.name,
        tool_calls=[],
        invalid_tool_calls=[],
        usage_metadata=getattr(response, "usage_metadata", None),
    )


def _record_final_context_trace(collector, request: FinalResponseRequest) -> None:
    log_agent_audit(
        phase="final_response",
        boundary="FINAL_NO_TOOLS",
        sop="final_context_valid",
        status="success",
        tool_results=len(request.tool_results),
        context_blocks=len(request.context_blocks),
        dropped_tool_call_history=request.trace_metadata.get(
            "dropped_tool_call_history"
        ),
    )
    if collector is None:
        return
    try:
        collector.record(
            node_type="final_context",
            node_name="build",
            input_data={
                "user_query": request.user_query[:500],
                "context_block_count": len(request.context_blocks),
            },
            output_data={
                **request.trace_metadata,
                "tool_results": [
                    result.to_trace_payload() for result in request.tool_results
                ],
                "context_blocks": [
                    block.to_trace_payload() for block in request.context_blocks
                ],
            },
        )
    except Exception as exc:
        log_silent_exception(
            logger,
            level=logging.WARNING,
            function="_record_final_context_trace",
            agent_event="final_response.record_final_context_trace",
            exc=exc,
        )
        return


def _record_output_guard_trace(
    collector,
    *,
    passed: bool,
    leak_type: str | None,
    action: str,
    retry_count: int,
) -> None:
    log_agent_audit(
        phase="output_guard",
        boundary="FINAL_NO_TOOLS",
        sop="output_guard_check",
        status="success" if passed else "fallback",
        leak_type=leak_type,
        action=action,
        retry_count=retry_count,
    )
    if collector is None:
        return
    try:
        collector.record(
            node_type="output_guard",
            node_name="final_json_leak_check",
            input_data={"boundary": "final_response"},
            output_data={
                "passed": passed,
                "leak_type": leak_type,
                "action": action,
                "retry_count": retry_count,
            },
        )
    except Exception as exc:
        log_silent_exception(
            logger,
            level=logging.WARNING,
            function="_record_output_guard_trace",
            agent_event="final_response.record_output_guard_trace",
            exc=exc,
        )
        return


__all__ = [
    "FinalContextBuilder",
    "FinalResponseConstraints",
    "FinalResponseRequest",
    "OutputGuardCheck",
    "ToolResultSummary",
    "check_final_output_leak",
    "extract_safe_natural_language",
    "fail_closed_final_response",
    "guard_final_response",
]
