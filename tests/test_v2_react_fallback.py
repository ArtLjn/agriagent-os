"""v2 Agent 空白响应降级与 trace 结果测试。"""

from agent.core.react import _build_fallback_answer
from agent.core.turn import Turn
from agent.infra.trace.summary import build_trace_request_summary


def test_fallback_answer_contains_completed_read_results() -> None:
    turn = Turn(user_input="你分析一下我的基本信息")
    turn.emit(
        "observation",
        {
            "tool_name": "get_farm_status",
            "result": {
                "location": "苏州",
                "active_cycles": [{"id": 1}, {"id": 2}],
                "workers_summary": {"active": 13, "total": 19},
                "cost_summary": {"month_total": 1200},
            },
        },
    )

    answer = _build_fallback_answer(turn, "本轮分析查询范围较大")

    assert "农场位置：苏州" in answer
    assert "当前活跃种植茬口：2 个" in answer
    assert "工人：在职 13 人，共 19 人" in answer
    assert "本轮分析查询范围较大" in answer


def test_failed_turn_trace_summary_is_not_success() -> None:
    summary = build_trace_request_summary(
        [
            {
                "request_id": "req-1",
                "conversation_id": "conv-1",
                "turn_id": "turn-1",
                "step_index": 5,
                "node_type": "turn",
                "node_name": "outcome",
                "input_data": {"status": "failed"},
                "output_data": {
                    "status": "failed",
                    "error": {"code": "max_steps_reached"},
                },
                "duration_ms": 0,
                "status": "error",
                "error_message": "max_steps_reached",
            }
        ]
    )

    assert summary is not None
    assert summary["status"] == "failed"
    assert summary["status_reason"] == "max_steps_reached"
