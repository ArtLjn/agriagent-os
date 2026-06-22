"""MemoryService 会话摘要触发测试。"""

import logging
from datetime import datetime, timedelta
from unittest.mock import AsyncMock

import pytest
from sqlalchemy.orm import sessionmaker

from app.core.compat import UTC
from app.memory.service import InMemoryMemoryService
from app.models.conversation import Conversation, ConversationMessage


def _新建会话(db_session, *, summary=None, summary_updated_at=None):
    conversation = Conversation(
        farm_id=1,
        user_id="test-user-001",
        session_id="summary-session",
        summary=summary,
        summary_updated_at=summary_updated_at,
    )
    db_session.add(conversation)
    db_session.commit()
    db_session.refresh(conversation)
    return conversation


def _补充消息(db_session, conversation, count):
    for index in range(count):
        db_session.add(
            ConversationMessage(
                conversation_id=conversation.id,
                role="user" if index % 2 == 0 else "assistant",
                content=f"第 {index + 1} 条消息",
            )
        )
    db_session.commit()


def _配置摘要(monkeypatch, service_module, *, enabled=True, threshold=12, debounce=30):
    monkeypatch.setattr(
        service_module.settings.ai,
        "enable_session_summary",
        enabled,
    )
    monkeypatch.setattr(
        service_module.settings.ai,
        "session_summary_message_threshold",
        threshold,
    )
    monkeypatch.setattr(
        service_module.settings.ai,
        "session_summary_debounce_minutes",
        debounce,
    )


def _收集_trace(monkeypatch, service_module):
    records = []
    monkeypatch.setattr(
        service_module,
        "get_collector",
        lambda: type(
            "Collector",
            (),
            {"record": lambda self, **kwargs: records.append(kwargs)},
        )(),
    )
    return records


def _skip_reasons(records):
    return [
        record["output_data"]["reason"]
        for record in records
        if record["node_name"] == "summary_skipped"
    ]


@pytest.mark.asyncio
async def test_maybe_summarize_消息数低于阈值时跳过并记录_trace(
    db_session, monkeypatch, caplog
):
    from app.memory import service as service_module
    from app.observability.metrics import reset_metrics, session_summary_skipped_total

    reset_metrics()
    conversation = _新建会话(db_session)
    _补充消息(db_session, conversation, 11)
    _配置摘要(monkeypatch, service_module)
    records = _收集_trace(monkeypatch, service_module)
    generate_summary = AsyncMock()
    monkeypatch.setattr(service_module, "generate_summary", generate_summary)

    service = InMemoryMemoryService()
    with caplog.at_level(logging.INFO, logger="app.memory.service"):
        await service.maybe_summarize(
            db_session,
            conversation.id,
            farm_id=1,
            session_id="summary-session",
            messages=[],
        )

    assert _skip_reasons(records) == ["below_threshold"]
    log_record = next(
        record
        for record in caplog.records
        if record.message == "会话摘要跳过"
    )
    assert log_record.code == "MEMORY_SUMMARY_SKIPPED"
    assert log_record.reason == "below_threshold"
    assert log_record.message_count == 11
    assert log_record.threshold == 12
    event = records[0]
    assert event["input_data"]["farm_id"] == 1
    assert event["input_data"]["session_id"] == "summary-session"
    assert event["output_data"]["reason"] == "below_threshold"
    assert session_summary_skipped_total("below_threshold") == 1
    generate_summary.assert_not_awaited()


@pytest.mark.asyncio
async def test_maybe_summarize_防抖窗口内跳过(db_session, monkeypatch):
    from app.memory import service as service_module

    conversation = _新建会话(
        db_session,
        summary="旧摘要",
        summary_updated_at=datetime.now(UTC) - timedelta(minutes=5),
    )
    _补充消息(db_session, conversation, 12)
    _配置摘要(monkeypatch, service_module, debounce=30)
    records = _收集_trace(monkeypatch, service_module)
    generate_summary = AsyncMock()
    monkeypatch.setattr(service_module, "generate_summary", generate_summary)

    service = InMemoryMemoryService()
    await service.maybe_summarize(db_session, conversation.id, 1, "summary-session", [])

    assert _skip_reasons(records) == ["within_debounce_window"]
    generate_summary.assert_not_awaited()


@pytest.mark.asyncio
async def test_maybe_summarize_feature_flag_关闭时跳过(db_session, monkeypatch):
    from app.memory import service as service_module

    conversation = _新建会话(db_session)
    _补充消息(db_session, conversation, 12)
    _配置摘要(monkeypatch, service_module, enabled=False)
    records = _收集_trace(monkeypatch, service_module)
    generate_summary = AsyncMock()
    monkeypatch.setattr(service_module, "generate_summary", generate_summary)

    service = InMemoryMemoryService()
    await service.maybe_summarize(db_session, conversation.id, 1, "summary-session", [])

    assert _skip_reasons(records) == ["feature_disabled"]
    generate_summary.assert_not_awaited()


@pytest.mark.asyncio
async def test_maybe_summarize_熔断开启时跳过(db_session, monkeypatch):
    from app.memory import service as service_module

    conversation = _新建会话(db_session)
    _补充消息(db_session, conversation, 12)
    _配置摘要(monkeypatch, service_module)
    records = _收集_trace(monkeypatch, service_module)
    generate_summary = AsyncMock()
    monkeypatch.setattr(service_module, "generate_summary", generate_summary)
    monkeypatch.setattr(service_module, "_is_summary_circuit_open", lambda: True)

    service = InMemoryMemoryService()
    await service.maybe_summarize(db_session, conversation.id, 1, "summary-session", [])

    assert _skip_reasons(records) == ["circuit_open"]
    generate_summary.assert_not_awaited()


@pytest.mark.asyncio
async def test_maybe_summarize_乐观锁冲突时放弃写入(db_session, monkeypatch):
    from app.memory import service as service_module

    original_updated_at = datetime.now(UTC) - timedelta(hours=2)
    conversation = _新建会话(
        db_session,
        summary="旧摘要",
        summary_updated_at=original_updated_at,
    )
    _补充消息(db_session, conversation, 12)
    _配置摘要(monkeypatch, service_module, debounce=30)
    records = _收集_trace(monkeypatch, service_module)
    monkeypatch.setattr(service_module, "get_llm", lambda role: object())

    async def _生成后制造冲突(*_args, **_kwargs):
        db_session.refresh(conversation)
        conversation.summary_updated_at = datetime.now(UTC)
        conversation.summary = "并发写入的新摘要"
        db_session.commit()
        return "本次生成的过期摘要"

    monkeypatch.setattr(service_module, "generate_summary", _生成后制造冲突)

    service = InMemoryMemoryService()
    await service.maybe_summarize(db_session, conversation.id, 1, "summary-session", [])

    db_session.refresh(conversation)
    assert conversation.summary == "并发写入的新摘要"
    assert (
        await service.short_term.get_session_summary(
            "test-user-001", 1, "summary-session"
        )
        is None
    )
    assert _skip_reasons(records) == []


@pytest.mark.asyncio
async def test_maybe_summarize_首次摘要并发写入时条件更新失败(
    db_session,
    monkeypatch,
):
    from app.memory import service as service_module

    conversation = _新建会话(db_session, summary="旧摘要", summary_updated_at=None)
    _补充消息(db_session, conversation, 12)
    _配置摘要(monkeypatch, service_module)
    records = _收集_trace(monkeypatch, service_module)
    monkeypatch.setattr(service_module, "get_llm", lambda role: object())
    TestSession = sessionmaker(bind=db_session.get_bind())

    async def _生成期间由其他_session_抢先写入(*_args, **_kwargs):
        other_session = TestSession()
        try:
            other = other_session.get(Conversation, conversation.id)
            other.summary = "其他任务先写入的摘要"
            other.summary_updated_at = datetime.now(UTC)
            other_session.commit()
        finally:
            other_session.close()
        return "本次生成的过期摘要"

    monkeypatch.setattr(
        service_module,
        "generate_summary",
        _生成期间由其他_session_抢先写入,
    )

    service = InMemoryMemoryService()
    await service.maybe_summarize(db_session, conversation.id, 1, "summary-session", [])

    db_session.expire_all()
    refreshed = db_session.get(Conversation, conversation.id)
    assert refreshed.summary == "其他任务先写入的摘要"
    assert (
        await service.short_term.get_session_summary(
            "test-user-001", 1, "summary-session"
        )
        is None
    )
    assert _skip_reasons(records) == []


@pytest.mark.asyncio
async def test_maybe_summarize_正常生成后写入数据库并同步短时缓存(
    db_session,
    monkeypatch,
    caplog,
):
    from app.memory import service as service_module

    conversation = _新建会话(db_session, summary="旧摘要")
    _补充消息(db_session, conversation, 12)
    _配置摘要(monkeypatch, service_module)
    records = _收集_trace(monkeypatch, service_module)
    llm = object()
    monkeypatch.setattr(service_module, "get_llm", lambda role: llm)
    generate_summary = AsyncMock(return_value="新增摘要：西棚黄瓜预算 200 元。")
    monkeypatch.setattr(service_module, "generate_summary", generate_summary)

    service = InMemoryMemoryService()
    with caplog.at_level(logging.INFO, logger="app.memory.service"):
        await service.maybe_summarize(
            db_session,
            conversation.id,
            1,
            "summary-session",
            [],
        )

    db_session.refresh(conversation)
    assert conversation.summary == "新增摘要：西棚黄瓜预算 200 元。"
    assert conversation.summary_updated_at is not None
    assert (
        await service.short_term.get_session_summary(
            "test-user-001", 1, "summary-session"
        )
        == "新增摘要：西棚黄瓜预算 200 元。"
    )
    generate_summary.assert_awaited_once()
    assert generate_summary.await_args.args[0] is llm
    assert generate_summary.await_args.kwargs["current_summary"] == "旧摘要"
    assert len(generate_summary.await_args.kwargs["old_messages"]) == 12
    assert generate_summary.await_args.kwargs["persona"] is None
    assert _skip_reasons(records) == []
    started_record = next(
        record
        for record in caplog.records
        if record.message == "会话摘要开始生成"
    )
    assert started_record.code == "MEMORY_SUMMARY_STARTED"
    assert started_record.message_count == 12
    assert started_record.summary_message_count == 12
    success_record = next(
        record
        for record in caplog.records
        if record.message == "会话摘要写入成功"
    )
    assert success_record.code == "MEMORY_SUMMARY_UPDATED"
    assert success_record.summary_length == len("新增摘要：西棚黄瓜预算 200 元。")


@pytest.mark.asyncio
async def test_maybe_summarize_异常时记录结构化日志且不抛出(
    db_session,
    monkeypatch,
    caplog,
):
    from app.memory import service as service_module
    from app.observability.metrics import reset_metrics, session_summary_failed_total

    reset_metrics()
    conversation = _新建会话(db_session)
    _补充消息(db_session, conversation, 12)
    _配置摘要(monkeypatch, service_module)
    _收集_trace(monkeypatch, service_module)
    monkeypatch.setattr(service_module, "get_llm", lambda role: object())

    async def _生成失败(*_args, **_kwargs):
        raise RuntimeError("summary llm failed")

    monkeypatch.setattr(service_module, "generate_summary", _生成失败)

    service = InMemoryMemoryService()
    with caplog.at_level(logging.ERROR, logger="app.memory.service"):
        await service.maybe_summarize(
            db_session,
            conversation.id,
            farm_id=1,
            session_id="summary-session",
            messages=[],
        )

    error_record = next(
        record for record in caplog.records if record.message == "会话摘要触发失败"
    )
    assert error_record.code == "MEMORY_SUMMARY_FAILED"
    assert error_record.farm_id == 1
    assert error_record.session_id == "summary-session"
    assert error_record.conversation_id == conversation.id
    assert session_summary_failed_total() == 1
