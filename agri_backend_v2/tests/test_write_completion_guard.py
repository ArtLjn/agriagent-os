"""写操作完成声明的防伪造校验。"""

from __future__ import annotations

import pytest

from agent.domains.harness.runtime import engine as react
from agent.domains.harness.runtime import verify
from agent.domains.harness.runtime.turn import Turn


def _tracker_with(risk_level: str) -> verify.ProgressLedger:
    tracker = verify.ProgressLedger()
    tracker.record("create_cost_record", {"amount": 200}, risk_level=risk_level)
    return tracker


def _issue(
    user_input: str,
    content: str,
    *,
    tracker: verify.ProgressLedger | None = None,
    committed_result: dict | None = None,
) -> str | None:
    return verify.write_completion_guard_issue(
        user_input=user_input,
        content=content,
        tracker=tracker or verify.ProgressLedger(),
        committed_result=committed_result,
    )


@pytest.mark.parametrize(
    "content",
    [
        "好的，已为您记录一笔 200 元的化肥支出。",
        "已经帮您创建好了。",
        "已成功提交。",
        "记账完成。",
        "已为您记好了。",
    ],
)
def test_blocks_write_claim_without_write_call(content: str) -> None:
    assert _issue("帮我记一笔：今天买了 200 元化肥", content)


def test_allows_claim_after_write_call() -> None:
    assert (
        _issue(
            "帮我记一笔：今天买了 200 元化肥",
            "好的，已为您记录一笔 200 元的化肥支出。",
            tracker=_tracker_with("write_confirm"),
        )
        is None
    )


def test_allows_claim_after_committed_result() -> None:
    assert (
        _issue(
            "帮我记一笔：今天买了 200 元化肥",
            "已为您记录。",
            committed_result={"record_id": 1},
        )
        is None
    )


def test_ignores_read_only_answers() -> None:
    assert _issue("查一下最近的支出", "已为您查询到 3 条支出记录。") is None


def test_ignores_non_write_requests() -> None:
    assert _issue("上次那笔账记好了吗", "已经记录好了。") is None


def test_write_risk_is_recorded_in_tracker() -> None:
    assert verify.has_write_call(_tracker_with("write_confirm"))
    assert verify.has_write_call(_tracker_with("write_high"))
    assert not verify.has_write_call(_tracker_with("read"))


@pytest.mark.asyncio
async def test_final_answer_guard_requests_corrective_step() -> None:
    turn = Turn(
        user_input="帮我记一笔：今天买了 200 元化肥",
        conversation_id="conversation-1",
    )
    turn.step_count = 2
    events = [
        event
        async for event in react._emit_final_answer(
            turn,
            "好的，已为您记录一笔 200 元的化肥支出。",
            None,
            verify.CallTracker(),
        )
    ]

    assert turn.status == "running"
    assert turn.write_guard_attempts == 1
    assert any(event["type"] == "verification_warning" for event in events)
    assert turn.messages[-1]["role"] == "system"
    assert "写工具" in turn.messages[-1]["content"]

