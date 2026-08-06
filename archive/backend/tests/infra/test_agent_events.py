"""Agent JSONL event writer 测试。"""

import json
from pathlib import Path

import pytest

from app.infra.agent_events import AgentEvent, AgentEventWriter, read_event_segment

pytestmark = pytest.mark.no_db


def test_write_event_appends_jsonl_with_partitioned_path(tmp_path):
    writer = AgentEventWriter(base_dir=tmp_path)

    result = writer.write(
        event_type="message.user",
        farm_id=1,
        user_id="user-1",
        session_id="sess-event",
        turn_id=3,
        request_id="abcd1234",
        payload={"content": "查一下作物"},
    )

    assert result.status == "success"
    assert result.seq == 1
    path = Path(result.event_file)
    assert path.exists()
    assert "farm_id=1" in str(path)
    assert "session_id=sess-event" in str(path)
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    assert rows[0]["event_type"] == "message.user"
    assert rows[0]["payload"] == {"content": "查一下作物"}


def test_writer_increments_sequence_per_session_file(tmp_path):
    writer = AgentEventWriter(base_dir=tmp_path)

    first = writer.write(
        event_type="message.user",
        farm_id=1,
        user_id="user-1",
        session_id="sess-seq",
        turn_id=1,
        request_id="req1",
        payload={"content": "一"},
    )
    second = writer.write(
        event_type="message.assistant",
        farm_id=1,
        user_id="user-1",
        session_id="sess-seq",
        turn_id=1,
        request_id="req1",
        payload={"content": "二"},
    )

    assert first.seq == 1
    assert second.seq == 2
    assert first.event_file == second.event_file


def test_writer_keeps_unique_sequence_for_repeated_writes(tmp_path):
    writer = AgentEventWriter(base_dir=tmp_path)

    results = [
        writer.write(
            event_type="message.user",
            farm_id=1,
            user_id="user-1",
            session_id="sess-cache",
            turn_id=1,
            request_id="req1",
            payload={"index": index},
        )
        for index in range(5)
    ]

    assert [result.seq for result in results] == [1, 2, 3, 4, 5]
    assert len({result.seq for result in results}) == 5


def test_writer_uses_cached_sequence_after_first_write(tmp_path):
    writer = AgentEventWriter(base_dir=tmp_path)
    first = writer.write(
        event_type="message.user",
        farm_id=1,
        user_id="user-1",
        session_id="sess-cached-seq",
        turn_id=1,
        request_id="req1",
        payload={"content": "一"},
    )
    path = Path(first.event_file)
    path.write_text(
        path.read_text(encoding="utf-8")
        + json.dumps({"seq": 99, "event_type": "external"}, ensure_ascii=False)
        + "\n",
        encoding="utf-8",
    )

    second = writer.write(
        event_type="message.assistant",
        farm_id=1,
        user_id="user-1",
        session_id="sess-cached-seq",
        turn_id=1,
        request_id="req1",
        payload={"content": "二"},
    )

    assert second.seq == 2


def test_read_event_segment_filters_by_seq(tmp_path):
    writer = AgentEventWriter(base_dir=tmp_path)
    for index in range(3):
        writer.write(
            event_type="tool.call.finished",
            farm_id=1,
            user_id="user-1",
            session_id="sess-read",
            turn_id=1,
            request_id="req1",
            payload={"index": index},
        )

    rows = read_event_segment(
        writer.event_file_for(farm_id=1, session_id="sess-read"), 2, 3
    )

    assert [row["seq"] for row in rows] == [2, 3]
    assert rows[0]["payload"] == {"index": 1}


def test_agent_event_dataclass_to_dict_has_stable_shape():
    event = AgentEvent(
        event_id="evt-1",
        event_type="message.user",
        schema_version=1,
        created_at="2026-06-11T10:00:00+08:00",
        farm_id=1,
        user_id="user-1",
        session_id="sess",
        turn_id=1,
        request_id="req",
        seq=1,
        payload={"content": "hi"},
    )

    assert event.to_dict()["event_id"] == "evt-1"
    assert event.to_dict()["schema_version"] == 1
