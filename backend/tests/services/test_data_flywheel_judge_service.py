"""数据飞轮 LLM judge service primitives 测试。"""

from types import SimpleNamespace
from typing import Any

import pytest

from app.modules.data_flywheel.judge_service import (
    DEFAULT_PROMPT_VERSION,
    DataFlywheelJudgeClient,
    OpenAIDataFlywheelJudgeClient,
    build_judge_input,
    normalize_judge_output,
)

pytestmark = pytest.mark.no_db


def _sample_detail() -> dict[str, Any]:
    return {
        "sample": {
            "sample_id": "turn:1:sess-1:12",
            "sample_type": "session_turn",
            "session_id": "sess-1",
            "turn_id": 12,
            "request_id": "req-1",
            "user_input_preview": "preview user",
            "assistant_reply_preview": "preview assistant",
        },
        "messages": [
            {"role": "user", "content": "安排王大妈去5号棚收水稻"},
            {"role": "assistant", "content": "已安排王大妈去5号棚收水稻。"},
        ],
        "router_decision": {
            "selected_tools": ["create_operation_work_order"],
            "rejected_tools": ["query_weather"],
            "fallback": None,
            "reason": "用户要求创建作业",
            "raw_prompt": "不要传给 judge",
        },
        "tool_events": [
            {
                "event_type": "tool.call.finished",
                "payload": {
                    "tool_name": "create_operation_work_order",
                    "status": "success",
                    "params": {"worker": "王大妈"},
                    "result": {"id": 9},
                },
            }
        ],
        "pending_lifecycle": [
            {
                "event_type": "pending.plan.created",
                "payload": {
                    "plan_id": "plan-1",
                    "status": "created",
                    "skill_name": "create_operation_work_order",
                    "raw_user_input": "不要传给 judge",
                    "steps": [
                        {
                            "skill_name": "create_operation_work_order",
                            "status": "pending",
                            "action": "create",
                            "params": {"worker": "王大妈"},
                        }
                    ],
                },
            }
        ],
        "source": {
            "event_file": "events.jsonl",
            "event_seq_start": 1,
            "event_seq_end": 5,
            "event_log_status": "available",
            "chat_record_source": "mysql_conversation_messages",
            "missing_event_segments": [],
            "absolute_path": "/tmp/events.jsonl",
        },
        "debug_export": {
            "format": "farm-manager.chat-session-debug.v2",
            "session": {"session_id": "sess-1"},
            "turns": [
                {"id": 12, "request_id": "req-1"},
                {"id": 13, "request_id": "req-2"},
            ],
            "messages": [{"content": "不要完整传给 judge"}],
            "events": [{"payload": {"result": {"id": 9}}}],
        },
        "issue_candidates": [
            {
                "type": "pending_missed",
                "severity": "high",
                "reason": "缺少确认计划",
                "evidence": "create_operation_work_order",
                "suggested_label": "pending_missed",
            }
        ],
    }


def test_build_judge_input_includes_sample_detail_and_debug_evidence() -> None:
    payload = build_judge_input(_sample_detail())

    assert payload["task"] == "judge_agent_turn_quality"
    assert payload["prompt_version"] == DEFAULT_PROMPT_VERSION
    assert payload["sample"]["sample_id"] == "turn:1:sess-1:12"
    assert payload["sample"]["user_input"] == "安排王大妈去5号棚收水稻"
    assert payload["sample"]["assistant_reply"] == "已安排王大妈去5号棚收水稻。"
    assert payload["sample"]["selected_tools"] == ["create_operation_work_order"]
    assert payload["sample"]["actual_tools"] == ["create_operation_work_order"]
    assert payload["sample"]["issue_candidates"][0]["type"] == "pending_missed"
    assert payload["debug_evidence"]["router_decision"]["selected_tools"] == [
        "create_operation_work_order"
    ]
    assert payload["debug_evidence"]["router_decision"]["rejected_tools"] == [
        "query_weather"
    ]
    assert "raw_prompt" not in payload["debug_evidence"]["router_decision"]
    assert payload["debug_evidence"]["source"]["event_file"] == "events.jsonl"
    assert "absolute_path" not in payload["debug_evidence"]["source"]
    assert payload["debug_evidence"]["tool_events"] == [
        {
            "event_type": "tool.call.finished",
            "tool_name": "create_operation_work_order",
            "error": None,
            "status": "success",
        }
    ]
    assert "params" not in payload["debug_evidence"]["tool_events"][0]
    assert "result" not in payload["debug_evidence"]["tool_events"][0]
    assert payload["debug_evidence"]["pending_lifecycle"] == [
        {
            "event_type": "pending.plan.created",
            "plan_id": "plan-1",
            "status": "created",
            "skill_name": "create_operation_work_order",
            "steps": [
                {
                    "skill_name": "create_operation_work_order",
                    "status": "pending",
                    "action": "create",
                }
            ],
        }
    ]
    assert "debug_export" not in payload["debug_evidence"]
    assert payload["debug_evidence"]["debug_export_summary"] == {
        "session_id": "sess-1",
        "turn_count": 2,
        "request_ids": ["req-1", "req-2"],
    }
    assert "中文" in payload["judge_instructions"]
    assert payload["label_definitions"]["wrong_tool_selection"].startswith("工具")
    assert "not_actionable" in payload["label_selection_rules"]
    assert "labels" in payload["output_schema"]["required"]


def test_build_judge_input_falls_back_to_preview_when_messages_missing() -> None:
    detail = _sample_detail()
    detail["messages"] = []

    payload = build_judge_input(detail)

    assert payload["sample"]["user_input"] == "preview user"
    assert payload["sample"]["assistant_reply"] == "preview assistant"


def test_normalize_judge_output_filters_labels_and_clamps_confidence() -> None:
    normalized = normalize_judge_output(
        {
            "labels": ["bad_reply", "pending_missed", "not_allowed_label"],
            "root_cause": "router 缺少 pending 确认",
            "severity": "critical",
            "confidence": 1.4,
            "reason": "回复直接声称已安排，但缺少确认证据。",
            "recommended_fix": "补充 pending confirmation。",
        }
    )

    assert normalized == {
        "labels": ["bad_reply", "pending_missed"],
        "root_cause": "router 缺少 pending 确认",
        "severity": "critical",
        "confidence": 1.0,
        "reason": "回复直接声称已安排，但缺少确认证据。",
        "recommended_fix": "补充 pending confirmation。",
    }


def test_normalize_judge_output_defaults_invalid_values() -> None:
    normalized = normalize_judge_output(
        {
            "labels": ["not_allowed_label"],
            "severity": "urgent",
            "confidence": "not-a-number",
            "reason": "",
        }
    )

    assert normalized["labels"] == ["not_actionable"]
    assert normalized["severity"] == "medium"
    assert normalized["confidence"] == 0.0
    assert normalized["reason"] == "LLM judge 未返回判断理由。"
    assert normalized["root_cause"] == ""
    assert normalized["recommended_fix"] == ""


@pytest.mark.parametrize("raw", [None, "bad", ["bad"]])
def test_normalize_judge_output_defaults_non_dict_raw(raw: Any) -> None:
    assert normalize_judge_output(raw) == {
        "labels": ["not_actionable"],
        "root_cause": "",
        "severity": "medium",
        "confidence": 0.0,
        "reason": "LLM judge 未返回判断理由。",
        "recommended_fix": "",
    }


def test_normalize_judge_output_defaults_empty_labels() -> None:
    assert normalize_judge_output({"labels": None})["labels"] == ["not_actionable"]
    assert normalize_judge_output({"labels": []})["labels"] == ["not_actionable"]


@pytest.mark.parametrize("confidence", ["nan", "inf", "-inf"])
def test_normalize_judge_output_defaults_non_finite_confidence(
    confidence: str,
) -> None:
    assert normalize_judge_output({"confidence": confidence})["confidence"] == 0.0


def test_normalize_judge_output_converts_complex_text_fields() -> None:
    normalized = normalize_judge_output(
        {
            "labels": ["bad_reply"],
            "root_cause": {"code": "router"},
            "recommended_fix": ["补 pending"],
        }
    )

    assert normalized["root_cause"] == "{'code': 'router'}"
    assert normalized["recommended_fix"] == "['补 pending']"


def test_judge_client_protocol_accepts_fake_client_returning_raw_json() -> None:
    class FakeJudgeClient:
        judge_model = "fake-judge"
        prompt_version = DEFAULT_PROMPT_VERSION

        def judge(self, payload: dict[str, Any]) -> dict[str, Any]:
            return {
                "labels": ["pending_missed"],
                "severity": "high",
                "confidence": 0.8,
                "reason": payload["sample"]["sample_id"],
            }

    client: DataFlywheelJudgeClient = FakeJudgeClient()

    raw = client.judge(build_judge_input(_sample_detail()))

    assert raw == {
        "labels": ["pending_missed"],
        "severity": "high",
        "confidence": 0.8,
        "reason": "turn:1:sess-1:12",
    }


def test_openai_judge_client_parses_json_completion() -> None:
    calls = []

    class FakeCompletions:
        def create(self, **kwargs):
            calls.append(kwargs)
            return SimpleNamespace(
                choices=[
                    SimpleNamespace(
                        message=SimpleNamespace(
                            content=(
                                '{"labels":["bad_reply"],"root_cause":"缺证据",'
                                '"severity":"high","confidence":0.8,'
                                '"reason":"回复不可验证","recommended_fix":"补证据"}'
                            )
                        )
                    )
                ]
            )

    fake_client = SimpleNamespace(chat=SimpleNamespace(completions=FakeCompletions()))
    judge = OpenAIDataFlywheelJudgeClient(
        client=fake_client,
        judge_model="fake-model",
    )

    result = judge.judge({"sample": {"sample_id": "turn:1:s:1"}})

    assert result["labels"] == ["bad_reply"]
    assert calls[0]["model"] == "fake-model"
    assert calls[0]["temperature"] == 0
    assert calls[0]["response_format"] == {"type": "json_object"}
    system_prompt = calls[0]["messages"][0]["content"]
    assert "所有自然语言字段必须使用简体中文" in system_prompt
    assert "不要使用英文解释" in system_prompt


def test_openai_judge_client_defaults_invalid_json_to_empty_dict() -> None:
    class FakeCompletions:
        def create(self, **_kwargs):
            return SimpleNamespace(
                choices=[SimpleNamespace(message=SimpleNamespace(content="not-json"))]
            )

    fake_client = SimpleNamespace(chat=SimpleNamespace(completions=FakeCompletions()))
    judge = OpenAIDataFlywheelJudgeClient(
        client=fake_client,
        judge_model="fake-model",
    )

    assert judge.judge({}) == {}
