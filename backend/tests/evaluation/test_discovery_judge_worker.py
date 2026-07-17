"""DataFlywheel discovery Judge 辅助函数测试。"""

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from app.platforms.evaluation.discovery.judge_worker import (
    JUDGE_MONTHLY_COST_LIMIT_USD,
    build_default_judge_client,
    build_judge_prompt,
    estimate_usage_cost_usd,
    run_judge_batch_async,
    run_judge_batch,
    should_degrade_for_cost,
    parse_judge_response,
)
from app.core.database import Base
from app.models.agent_turn import AgentTurn
from app.models.data_flywheel import AgentDataFlywheelLabel
from app.models.farm import Farm

pytestmark = pytest.mark.no_db


def _set_sqlite_pragma(dbapi_connection, _connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


_engine = create_engine(
    "sqlite:///tests/test_discovery_judge_worker.db",
    connect_args={"check_same_thread": False},
)
event.listen(_engine, "connect", _set_sqlite_pragma)
Session = sessionmaker(autocommit=False, autoflush=False, bind=_engine)


def setup_function():
    Base.metadata.drop_all(bind=_engine)
    Base.metadata.create_all(bind=_engine)
    db = Session()
    db.add(Farm(id=1, name="默认农场"))
    db.commit()
    db.close()


class FakeJudgeClient:
    def __init__(self):
        self.calls = []

    def judge(self, payload):
        self.calls.append(payload)
        return {
            "bad_prob": 0.82,
            "issue_type": "missing_wage",
            "suggested_label": "bad_reply",
            "evidence": ["缺少实发工资"],
            "usage": {"input_tokens": 1000, "output_tokens": 200},
        }


def test_build_judge_prompt_requests_required_json_fields() -> None:
    prompt = build_judge_prompt(
        {
            "user_message": "帮我查工资",
            "reply_preview": "工资是 3000",
            "intent": "wage_query",
            "tool_calls": [],
        }
    )

    assert "bad_prob" in prompt
    assert "issue_type" in prompt
    assert "suggested_label" in prompt
    assert "evidence" in prompt
    assert "帮我查工资" in prompt


def test_parse_judge_response_accepts_json_object() -> None:
    result = parse_judge_response(
        '{"bad_prob": 0.72, "issue_type": "missing_wage", '
        '"suggested_label": "bad", "evidence": ["缺少实发工资"]}'
    )

    assert result.bad_prob == 0.72
    assert result.issue_type == "missing_wage"
    assert result.suggested_label == "bad"
    assert result.evidence == ["缺少实发工资"]
    assert result.parse_error is None


def test_parse_judge_response_failure_returns_safe_fallback() -> None:
    result = parse_judge_response("这不是 JSON")

    assert result.bad_prob is None
    assert result.issue_type == "parse_error"
    assert result.suggested_label is None
    assert result.evidence == []
    assert result.parse_error is not None


def test_parse_judge_response_rejects_out_of_range_probability() -> None:
    result = parse_judge_response(
        '{"bad_prob": 1.5, "issue_type": "x", "suggested_label": "bad", "evidence": []}'
    )

    assert result.bad_prob is None
    assert result.issue_type == "parse_error"


def test_estimate_usage_cost_usd_from_token_usage() -> None:
    cost = estimate_usage_cost_usd(
        {"input_tokens": 1_000_000, "output_tokens": 1_000_000},
        input_cost_per_million=0.25,
        output_cost_per_million=1.25,
    )

    assert cost == pytest.approx(1.5)


def test_cost_limit_degrades_only_after_limit() -> None:
    below = should_degrade_for_cost(JUDGE_MONTHLY_COST_LIMIT_USD)
    above = should_degrade_for_cost(JUDGE_MONTHLY_COST_LIMIT_USD + 0.01)

    assert below.degraded is False
    assert above.degraded is True
    assert above.mode == "rule_only"


def test_run_judge_batch_writes_judge_fields_and_recalculates_risk() -> None:
    db = Session()
    turn = AgentTurn(
        farm_id=1,
        session_id="sess-judge",
        request_id="judge1",
        input_preview="查工资",
        reply_preview="工资是 3000",
        rule_score=0.2,
        risk_score=0.2,
        risk_dominant_signal="rule",
    )
    db.add(turn)
    db.commit()
    client = FakeJudgeClient()

    summary = run_judge_batch(db, judge_client=client, month_cost_usd=0)

    db.refresh(turn)
    assert summary.processed == 1
    assert summary.updated == 1
    assert client.calls
    assert turn.judge_bad_prob == 0.82
    assert turn.judge_issue_type == "missing_wage"
    assert turn.judge_suggested_label == "bad_reply"
    assert turn.risk_score == 0.82
    assert turn.risk_dominant_signal == "judge"
    db.close()


def test_run_judge_batch_skips_human_labeled_and_cost_degraded_turns() -> None:
    db = Session()
    turn = AgentTurn(
        farm_id=1,
        session_id="sess-human",
        request_id="judge2",
        input_preview="查工资",
        reply_preview="工资是 3000",
    )
    db.add(turn)
    db.commit()
    db.add(
        AgentDataFlywheelLabel(
            farm_id=1,
            sample_id=f"turn:1:sess-human:{turn.id}",
            sample_type="session_turn",
            session_id="sess-human",
            turn_id=turn.id,
            request_id="judge2",
            label="bad_reply",
            annotator_id="admin",
        )
    )
    db.commit()
    client = FakeJudgeClient()

    human_summary = run_judge_batch(db, judge_client=client, month_cost_usd=0)
    degraded_summary = run_judge_batch(
        db,
        judge_client=client,
        month_cost_usd=JUDGE_MONTHLY_COST_LIMIT_USD + 1,
    )

    assert human_summary.processed == 0
    assert degraded_summary.degraded is True
    assert client.calls == []
    db.close()


@pytest.mark.asyncio
async def test_run_judge_batch_async_uses_semaphore_wrapper() -> None:
    db = Session()
    turn = AgentTurn(
        farm_id=1,
        session_id="sess-async",
        request_id="judge3",
        input_preview="查工资",
        reply_preview="工资是 3000",
    )
    db.add(turn)
    db.commit()

    summary = await run_judge_batch_async(
        db,
        judge_client=FakeJudgeClient(),
        month_cost_usd=0,
        concurrency=32,
    )

    assert summary.updated == 1
    db.close()


def test_build_default_judge_client_uses_lightweight_llm_manager(monkeypatch) -> None:
    class FakeManager:
        def __init__(self):
            self.role = None

        def get_sync_client_with_info(self, *, role):
            self.role = role
            return object(), {"model": "claude-3-haiku"}

    fake_manager = FakeManager()

    monkeypatch.setattr(
        "app.core.llm_client_manager.get_llm_manager",
        lambda: fake_manager,
    )

    client = build_default_judge_client()

    assert fake_manager.role == "lightweight"
    assert client.judge_model == "claude-3-haiku"
