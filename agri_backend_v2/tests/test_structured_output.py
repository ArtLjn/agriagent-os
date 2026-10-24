"""结构化输出协议回归：网关兼容不能放宽授权、证据或完整性校验。"""

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from pydantic import BaseModel, ConfigDict

from agent.domains.harness.memory import inference
from agent.domains.harness.memory.tools import (
    MemoryCommand,
    content_is_grounded,
)
from agent.platforms.llm import client
from agent.platforms.llm.structured import (
    StructuredOutputError,
    parse_structured_response,
    structured_completion,
)


class Decision(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    supported: bool


def response(content=None, *, calls=None, finish="stop", refusal=None):
    return SimpleNamespace(
        choices=[
            SimpleNamespace(
                finish_reason=finish,
                message=SimpleNamespace(
                    content=content, tool_calls=calls, refusal=refusal
                ),
            )
        ]
    )


def tool_call(payload, name="Decision"):
    return SimpleNamespace(
        function=SimpleNamespace(name=name, arguments=json.dumps(payload))
    )


@pytest.mark.parametrize("fenced", [False, True])
def test_complete_legacy_envelope_keeps_strict_types(fenced):
    raw = '{"supported":true}'
    if fenced:
        raw = f"```json\n{raw}\n```"
    assert parse_structured_response(response(raw), Decision).supported is True


@pytest.mark.parametrize("finish", ["stop", "tool_calls"])
def test_forced_tool_result_supports_gateway_finish_reason(finish):
    result = parse_structured_response(
        response(calls=[tool_call({"supported": True})], finish=finish), Decision
    )
    assert result.supported is True


@pytest.mark.parametrize(
    "raw",
    [
        "",
        "{",
        "{}",
        '{"supported":"true"}',
        '{"supported":1}',
        '{"supported":true,"extra":"不应接受"}',
        '{"supported":false,"supported":true}',
        '解释：{"supported":true}',
        '[{"supported":true}]',
    ],
)
def test_malformed_or_ambiguous_payload_is_never_repaired(raw):
    with pytest.raises(StructuredOutputError, match="structured_output_invalid"):
        parse_structured_response(response(raw), Decision)


@pytest.mark.parametrize("finish", ["length", "content_filter", "unknown"])
def test_even_valid_json_is_rejected_when_response_incomplete(finish):
    with pytest.raises(StructuredOutputError, match="structured_output_incomplete"):
        parse_structured_response(
            response('{"supported":true}', finish=finish), Decision
        )


def test_refusal_and_ambiguous_choices_cannot_authorize():
    with pytest.raises(StructuredOutputError, match="structured_output_refused"):
        parse_structured_response(
            response('{"supported":true}', refusal="拒绝"), Decision
        )
    for choices in [[], response().choices * 2]:
        with pytest.raises(StructuredOutputError, match="structured_output_ambiguous"):
            parse_structured_response(SimpleNamespace(choices=choices), Decision)


@pytest.mark.parametrize(
    "calls",
    [
        [tool_call({"supported": True}, "Unexpected")],
        [tool_call({"supported": True}), tool_call({"supported": False})],
    ],
)
def test_wrong_or_multiple_result_tools_are_rejected(calls):
    with pytest.raises(StructuredOutputError, match="structured_output_wrong_tool"):
        parse_structured_response(response(calls=calls), Decision)


def test_top_level_array_compatibility_only_for_legacy_extraction():
    result = parse_structured_response(
        response("[]"), inference.Extraction, legacy_array_field="candidates"
    )
    assert result.candidates == []
    with pytest.raises(StructuredOutputError):
        parse_structured_response(response("{}"), inference.Extraction)
    with pytest.raises(StructuredOutputError):
        parse_structured_response(
            response(calls=[tool_call([], "Extraction")]),
            inference.Extraction,
            legacy_array_field="candidates",
        )


@pytest.mark.asyncio
async def test_schema_generated_once_and_budgeted_request_forces_result_tool(
    monkeypatch,
):
    complete = AsyncMock(
        return_value=response(calls=[tool_call({"candidates": []}, "Extraction")])
    )
    monkeypatch.setattr(client, "bounded_completion", complete)
    result = await structured_completion(
        inference.Extraction,
        messages=[{"role": "user", "content": "天气如何"}],
        max_tokens=1500,
        timeout=30,
        temperature=0,
    )
    assert result.candidates == []
    request = complete.call_args.kwargs
    assert request["tool_choice"]["function"]["name"] == "Extraction"
    assert request["parallel_tool_calls"] is False
    schema = request["tools"][0]["function"]
    assert schema["strict"] is True
    assert schema["parameters"]["additionalProperties"] is False
    candidate = schema["parameters"]["$defs"]["Candidate"]
    assert set(candidate["required"]) == set(candidate["properties"])
    assert "response_format" not in request
    assert request["max_tokens"] == 1500
    complete.assert_awaited_once()


@pytest.mark.asyncio
async def test_malformed_grounding_cannot_be_treated_as_permission(monkeypatch):
    complete = AsyncMock(return_value=response('{"supported":"true"}'))
    monkeypatch.setattr(client, "bounded_completion", complete)
    with pytest.raises(StructuredOutputError):
        await content_is_grounded(
            MemoryCommand(action="remember", text="喜欢咖啡"), ["我喜欢咖啡"]
        )
    complete.assert_awaited_once()


@pytest.mark.asyncio
async def test_failed_decomposition_verification_never_mutates_record(monkeypatch):
    record = {"text": "喜欢咖啡"}
    complete = AsyncMock(
        side_effect=[
            response(
                calls=[
                    tool_call(
                        {
                            "facts": [
                                {
                                    "slot": "咖啡.偏好",
                                    "text": "喜欢咖啡",
                                    "evidence": "喜欢咖啡",
                                }
                            ]
                        },
                        "Decomposition",
                    )
                ]
            ),
            response(
                calls=[tool_call({"equivalent": True}, "DecompositionCheck")],
                finish="length",
            ),
        ]
    )
    monkeypatch.setattr(client, "bounded_completion", complete)
    with pytest.raises(StructuredOutputError, match="structured_output_incomplete"):
        await inference.normalize_record(record)
    assert record == {"text": "喜欢咖啡"}


def test_memory_release_fingerprint_covers_external_prompts_and_parser():
    from agent.api import health

    paths = {
        p.relative_to(health._AGENT_SOURCE).as_posix() for p in health._MEMORY_SOURCES
    }
    assert "platforms/llm/structured.py" in paths
    for task in (
        "extract",
        "extract_guard",
        "verify_extraction",
        "align_candidates",
        "normalize_record",
        "verify_decomposition",
        "read_context",
        "assess",
        "grounding",
    ):
        assert f"prompts/memory_{task}.md" in paths
