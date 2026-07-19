"""会话摘要生成器测试。"""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest
from langchain_core.messages import AIMessage, HumanMessage


@pytest.fixture(autouse=True)
def load_prompt_registry():
    from app.shared.config import settings
    from app.prompt.registry import get_registry

    get_registry().reload(settings.prompts_dir)
    yield
    get_registry().reload()


def test_render_summary_prompt_keeps_protected_field_requirements():
    from app.memory.summarizer import render_summary_prompt

    prompt = render_summary_prompt(
        current_summary="用户昨天提过西棚黄瓜。",
        recent_messages=[
            HumanMessage(content="明天给西棚黄瓜追肥，预算 200 元"),
            AIMessage(content="好的，我先记下，待确认后执行。"),
        ],
        persona="你是温和、可靠的农事助手。",
    )

    assert "用户昨天提过西棚黄瓜。" in prompt
    assert "明天给西棚黄瓜追肥，预算 200 元" in prompt
    assert "你是温和、可靠的农事助手。" in prompt
    assert "金额" in prompt
    assert "日期" in prompt
    assert "地块/作物名" in prompt
    assert "人名" in prompt
    assert "pending action 类型与关键参数" in prompt
    assert "追加段落" in prompt
    assert "不要重写" in prompt


def test_render_summary_prompt_uses_registry_template(monkeypatch):
    from app.memory import summarizer

    calls = []

    class Registry:
        def get(self, name):
            calls.append(name)
            return "摘要模板：{{ current_summary }} / {{ recent_messages }} / {{ persona }}"

    monkeypatch.setattr(summarizer, "get_registry", lambda: Registry())

    prompt = summarizer.render_summary_prompt(
        current_summary="旧摘要",
        recent_messages=[HumanMessage(content="新消息")],
        persona="助手人设",
    )

    assert calls == ["memory.running_summary"]
    assert "旧摘要" in prompt
    assert "新消息" in prompt
    assert "助手人设" in prompt


@pytest.mark.asyncio
async def test_generate_summary_returns_content_and_records_success(monkeypatch):
    from app.memory import summarizer
    from app.observability import (
        reset_metrics,
        session_summary_generated_total,
    )

    reset_metrics()
    llm = MagicMock()
    llm.model_name = "summary-model"
    bound_llm = MagicMock()
    bound_llm.ainvoke = AsyncMock()
    bound_llm.ainvoke.return_value = AIMessage(
        content="新增摘要：西棚黄瓜明天追肥，预算 200 元。"
    )
    llm.bind.return_value = bound_llm
    trace_records = []
    successes = []
    failures = []

    monkeypatch.setattr(summarizer, "_record_llm_success", successes.append)
    monkeypatch.setattr(
        summarizer,
        "_record_llm_failure",
        lambda key, exc: failures.append((key, exc)),
    )
    monkeypatch.setattr(
        summarizer,
        "get_collector",
        lambda: type(
            "Collector",
            (),
            {"record": lambda self, **kwargs: trace_records.append(kwargs)},
        )(),
    )

    result = await summarizer.generate_summary(
        llm,
        current_summary="旧摘要",
        old_messages=[HumanMessage(content="西棚黄瓜明天追肥，预算 200 元")],
        persona="农事助手",
    )

    assert result == "新增摘要：西棚黄瓜明天追肥，预算 200 元。"
    assert successes == ["summary-model"]
    assert failures == []
    llm.bind.assert_called_once_with(max_tokens=500)
    bound_llm.ainvoke.assert_awaited_once()
    assert trace_records
    event = trace_records[0]
    assert event["node_type"] == "memory_summary"
    assert event["node_name"] == "summary_generated"
    assert event["input_data"]["farm_id"] is None
    assert event["input_data"]["session_id"] is None
    assert event["input_data"]["current_summary_in_prompt"] is True
    assert event["token_usage"]["prompt_tokens"] > 0
    assert event["token_usage"]["completion_tokens"] > 0
    assert event["duration_ms"] >= 0
    assert session_summary_generated_total() == 1


@pytest.mark.asyncio
async def test_generate_summary_returns_none_when_llm_fails(monkeypatch):
    from app.memory import summarizer
    from app.observability import reset_metrics, session_summary_failed_total

    reset_metrics()
    llm = MagicMock()
    llm.model_name = "summary-model"
    llm.ainvoke = AsyncMock()
    error = RuntimeError("LLM 失败")
    llm.ainvoke.side_effect = error
    failures = []

    monkeypatch.setattr(summarizer, "_record_llm_success", lambda key: None)
    monkeypatch.setattr(
        summarizer,
        "_record_llm_failure",
        lambda key, exc: failures.append((key, exc)),
    )

    result = await summarizer.generate_summary(
        llm,
        current_summary="旧摘要",
        old_messages=[HumanMessage(content="消息")],
        persona="农事助手",
    )

    assert result is None
    assert failures == [("summary-model", error)]
    assert session_summary_failed_total() == 1


@pytest.mark.asyncio
async def test_generate_summary_returns_none_when_prompt_render_fails(monkeypatch):
    from app.memory import summarizer

    llm = MagicMock()
    llm.model_name = "summary-model"
    llm.ainvoke = AsyncMock()
    failures = []

    monkeypatch.setattr(
        summarizer,
        "render_summary_prompt",
        lambda **_kwargs: (_ for _ in ()).throw(RuntimeError("模板缺失")),
    )
    monkeypatch.setattr(summarizer, "_record_llm_success", lambda key: None)
    monkeypatch.setattr(
        summarizer,
        "_record_llm_failure",
        lambda key, exc: failures.append((key, exc)),
    )

    result = await summarizer.generate_summary(
        llm,
        current_summary="旧摘要",
        old_messages=[HumanMessage(content="消息")],
        persona="农事助手",
    )

    assert result is None
    assert failures
    assert failures[0][0] == "summary-model"
    llm.ainvoke.assert_not_awaited()


@pytest.mark.asyncio
async def test_generate_summary_returns_none_when_llm_times_out(monkeypatch):
    from app.memory import summarizer

    llm = MagicMock()
    llm.model_name = "summary-model"
    llm.ainvoke = AsyncMock()
    llm.ainvoke.side_effect = asyncio.TimeoutError()
    failures = []

    monkeypatch.setattr(summarizer, "_record_llm_success", lambda key: None)
    monkeypatch.setattr(
        summarizer,
        "_record_llm_failure",
        lambda key, exc: failures.append((key, exc)),
    )

    result = await summarizer.generate_summary(
        llm,
        current_summary="旧摘要",
        old_messages=[HumanMessage(content="消息")],
        persona="农事助手",
    )

    assert result is None
    assert failures
    assert failures[0][0] == "summary-model"
    assert isinstance(failures[0][1], asyncio.TimeoutError)


@pytest.mark.asyncio
async def test_generate_summary_returns_none_when_response_is_empty(monkeypatch):
    from app.memory import summarizer

    llm = MagicMock()
    llm.model_name = "summary-model"
    llm.ainvoke = AsyncMock()
    llm.ainvoke.return_value = AIMessage(content="   ")
    failures = []
    successes = []

    monkeypatch.setattr(summarizer, "_record_llm_success", successes.append)
    monkeypatch.setattr(
        summarizer,
        "_record_llm_failure",
        lambda key, exc: failures.append((key, exc)),
    )

    result = await summarizer.generate_summary(
        llm,
        current_summary="旧摘要",
        old_messages=[HumanMessage(content="消息")],
        persona="农事助手",
    )

    assert result is None
    assert successes == []
    assert failures
    assert failures[0][0] == "summary-model"


@pytest.mark.asyncio
async def test_generate_summary_returns_none_when_response_has_no_new_summary(
    monkeypatch,
):
    from app.memory import summarizer

    llm = MagicMock()
    llm.model_name = "summary-model"
    llm.ainvoke = AsyncMock()
    llm.ainvoke.return_value = AIMessage(content="无新增摘要")
    failures = []
    successes = []

    monkeypatch.setattr(summarizer, "_record_llm_success", successes.append)
    monkeypatch.setattr(
        summarizer,
        "_record_llm_failure",
        lambda key, exc: failures.append((key, exc)),
    )

    result = await summarizer.generate_summary(
        llm,
        current_summary="旧摘要",
        old_messages=[HumanMessage(content="只是寒暄")],
        persona="农事助手",
    )

    assert result is None
    assert successes == []
    assert failures == []
