"""用隔离 Redis 实例验证真实 Lua 原子操作，不连接业务 Redis。"""

from __future__ import annotations

import asyncio
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio
from redis import Redis as SyncRedis
from redis.asyncio import Redis
from redis.exceptions import ConnectionError

from agent.platforms.persistence.redis import turn_store
from agent.application import worker
from agent.domains.harness.runtime.turn import Turn


@pytest.fixture(scope="module")
def redis_socket():
    binary = shutil.which("redis-server")
    if not binary:
        pytest.skip("需要 redis-server 运行 Lua 集成测试")
    with tempfile.TemporaryDirectory(prefix="fm-redis-") as directory:
        socket = str(Path(directory) / "redis.sock")
        process = subprocess.Popen(
            [
                binary,
                "--port",
                "0",
                "--unixsocket",
                socket,
                "--save",
                "",
                "--appendonly",
                "no",
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        try:
            with SyncRedis(unix_socket_path=socket, socket_timeout=1) as client:
                deadline = time.monotonic() + 5
                while True:
                    try:
                        client.ping()
                        break
                    except ConnectionError:
                        if process.poll() is not None or time.monotonic() > deadline:
                            raise RuntimeError("隔离 Redis 启动失败") from None
                        time.sleep(0.02)
            yield socket
        finally:
            process.terminate()
            process.wait(timeout=5)


@pytest_asyncio.fixture
async def isolated_redis(redis_socket, monkeypatch):
    client = Redis(unix_socket_path=redis_socket, decode_responses=True)
    monkeypatch.setattr(turn_store, "get_client", lambda: client)
    monkeypatch.setattr(turn_store, "key", lambda kind, value: f"test:{kind}:{value}")
    monkeypatch.setattr(turn_store, "record_event", lambda _event: None)
    await client.hset(turn_store.turn_key("turn-1"), mapping={"status": "running"})
    try:
        yield client
    finally:
        await client.flushdb()
        await client.aclose()


@pytest.mark.asyncio
async def test_timeout_cannot_be_overwritten_by_late_success(isolated_redis):
    assert await turn_store.update_turn(
        "turn-1",
        status="timeout",
        error_code="worker_restarted",
        final_answer="执行中断",
    )
    assert not await turn_store.update_turn(
        "turn-1", status="completed", error_code="", final_answer="成功答复"
    )
    state = await turn_store.get_turn("turn-1")
    assert state["status"] == "timeout"
    assert state["final_answer"] == "执行中断"
    assert state["error_code"] == "worker_restarted"


@pytest.mark.asyncio
async def test_competing_finalizers_have_one_winner(isolated_redis):
    results = await asyncio.gather(
        turn_store.update_turn(
            "turn-1",
            expected_statuses=("running",),
            status="timeout",
            final_answer="中断",
        ),
        turn_store.update_turn(
            "turn-1",
            expected_statuses=("running",),
            status="completed",
            final_answer="完成",
        ),
    )
    assert sorted(results) == [False, True]
    state = await turn_store.get_turn("turn-1")
    assert (state["status"], state["final_answer"]) in {
        ("timeout", "中断"),
        ("completed", "完成"),
    }


@pytest.mark.asyncio
async def test_done_fences_late_events_and_preserves_continuous_sequence(
    isolated_redis,
):
    await asyncio.gather(
        *[
            turn_store.publish_event(
                "turn-1", {"type": "assistant_delta", "data": {"text": str(i)}}
            )
            for i in range(20)
        ]
    )
    await turn_store.update_turn("turn-1", status="timeout", final_answer="中断")
    done_seq = await turn_store.publish_event(
        "turn-1", {"type": "done", "data": {"status": "timeout"}}
    )
    results = await asyncio.gather(
        *[
            turn_store.publish_event(
                "turn-1", {"type": kind, "data": {"text": "过期结果"}}
            )
            for kind in ("assistant_delta", "final_answer", "turn.completed", "done")
        ]
    )
    assert results == [done_seq] * 4
    events = await turn_store.read_events("turn-1")
    assert [event["seq"] for event in events] == list(range(1, 22))
    assert events[-1]["type"] == "done"
    assert await isolated_redis.ttl(turn_store.event_key("turn-1")) > 0
    assert await isolated_redis.ttl(turn_store.turn_key("turn-1")) > 0


@pytest.mark.asyncio
async def test_done_keeps_outcome_but_allows_persistence_cleanup(isolated_redis):
    await turn_store.update_turn("turn-1", status="completed", final_answer="完成")
    await turn_store.publish_event(
        "turn-1", {"type": "done", "data": {"status": "completed"}}
    )
    assert not await turn_store.update_turn("turn-1", final_answer="过期答复")
    assert await turn_store.update_turn(
        "turn-1", finalization_pending=False, message_persistence_status="ready"
    )
    state = await turn_store.get_turn("turn-1")
    assert state["final_answer"] == "完成"
    assert state["message_persistence_status"] == "ready"


@pytest.mark.asyncio
async def test_missing_turn_is_not_recreated_by_stale_worker(isolated_redis):
    assert not await turn_store.update_turn("expired-turn", status="completed")
    assert (
        await turn_store.publish_event("expired-turn", {"type": "done", "data": {}})
        == 0
    )
    assert not await isolated_redis.exists(turn_store.turn_key("expired-turn"))


@pytest.mark.asyncio
async def test_done_racing_with_output_remains_last_and_unique(isolated_redis):
    outputs = [
        turn_store.publish_event("turn-1", {"type": "assistant_delta", "data": {}})
        for _ in range(40)
    ]
    outputs.insert(20, turn_store.publish_event("turn-1", {"type": "done", "data": {}}))
    outputs.append(turn_store.publish_event("turn-1", {"type": "done", "data": {}}))
    await asyncio.gather(*outputs)
    events = await turn_store.read_events("turn-1")
    assert events[-1]["type"] == "done"
    assert sum(event["type"] == "done" for event in events) == 1
    assert [event["seq"] for event in events] == list(range(1, len(events) + 1))


@pytest.mark.asyncio
async def test_persistence_failure_after_done_keeps_original_error(
    isolated_redis, monkeypatch
):
    await turn_store.update_turn(
        "turn-1", status="timeout", error_code="turn_lease_lost"
    )
    await turn_store.publish_event(
        "turn-1", {"type": "done", "data": {"status": "timeout"}}
    )
    monkeypatch.setattr(worker, "append_message", AsyncMock(return_value=None))
    monkeypatch.setattr(worker, "update_turn", turn_store.update_turn)
    assert not await worker._persist_visible_assistant_message(
        Turn(turn_id="turn-1"),
        content="执行中断",
        message_kind="error_answer",
        trace_id="trace-1",
    )
    state = await turn_store.get_turn("turn-1")
    assert state["error_code"] == "turn_lease_lost"
    assert state["message_persistence_status"] == "unavailable"
