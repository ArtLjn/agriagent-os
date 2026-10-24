"""结构化推理边界：从模型类型生成协议，拒绝截断、歧义和不合规的结果。"""

from __future__ import annotations

import json
import re
from typing import TypeVar

from openai import pydantic_function_tool
from pydantic import BaseModel

Result = TypeVar("Result", bound=BaseModel)


class StructuredOutputError(ValueError):
    """只暴露阶段和类型，不把用户证据或模型原文写进异常日志。"""

    def __init__(self, code: str, schema: type[BaseModel]):
        self.code = code
        super().__init__(f"结构化输出无效 code={code} schema={schema.__name__}")


def _unique_fields(pairs: list[tuple]) -> dict:
    """拒绝重复键，避免授权布尔值被后一个同名字段悄悄覆盖。"""
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate_field")
        result[key] = value
    return result


def parse_structured_response(
    response, schema: type[Result], *, legacy_array_field: str | None = None
) -> Result:
    """只兼容完整 JSON 外壳；不修补残缺事实，也不从解释文本中猜测结果。"""
    choices = getattr(response, "choices", [])
    if len(choices) != 1:
        raise StructuredOutputError("structured_output_ambiguous", schema)
    choice = choices[0]
    if getattr(choice, "finish_reason", None) not in {None, "stop", "tool_calls"}:
        raise StructuredOutputError("structured_output_incomplete", schema)
    message = choice.message
    if getattr(message, "refusal", None):
        raise StructuredOutputError("structured_output_refused", schema)
    calls = getattr(message, "tool_calls", None) or []
    if calls:
        if len(calls) != 1 or calls[0].function.name != schema.__name__:
            raise StructuredOutputError("structured_output_wrong_tool", schema)
        raw = calls[0].function.arguments
    else:
        # 兼容既有网关的内容通道；其字段、类型、长度仍经过同一份模型验证。
        raw = message.content or ""
    try:
        raw = raw.strip()
        fenced = re.fullmatch(r"```(?:json)?\s*([\s\S]*?)\s*```", raw, re.IGNORECASE)
        payload = json.loads(
            fenced.group(1) if fenced else raw, object_pairs_hook=_unique_fields
        )
        if not calls and legacy_array_field and isinstance(payload, list):
            payload = {legacy_array_field: payload}
        return schema.model_validate(payload, strict=True)
    except (AttributeError, TypeError, ValueError):
        raise StructuredOutputError("structured_output_invalid", schema) from None


async def structured_completion(
    schema: type[Result], *, legacy_array_field: str | None = None, **request
) -> Result:
    """复用最终上下文预算；强制输出工具只承载结果，不进入业务工具执行器。"""
    from agent.platforms.llm.client import MODEL, bounded_completion

    # 当前兼容网关会忽略 json_schema，但支持强制工具输出；协议由类型生成，避免手写两份。
    response = await bounded_completion(
        model=MODEL,
        tools=[pydantic_function_tool(schema)],
        tool_choice={"type": "function", "function": {"name": schema.__name__}},
        parallel_tool_calls=False,
        **request,
    )
    return parse_structured_response(
        response, schema, legacy_array_field=legacy_array_field
    )
