"""Session dataset service 测试。"""

from app.domains.conversation.session_dataset_service import (
    build_sft_samples,
    build_tool_selection_samples,
)


def test_build_sft_samples_from_events():
    events = [
        {
            "event_type": "message.user",
            "turn_id": 1,
            "payload": {"content": "我家有哪些作物"},
        },
        {
            "event_type": "tool.call.finished",
            "turn_id": 1,
            "payload": {"tool_name": "get_farm_status", "result": {"crops": ["水稻"]}},
        },
        {
            "event_type": "message.assistant",
            "turn_id": 1,
            "payload": {"content": "当前有水稻"},
        },
    ]

    samples = build_sft_samples(events)

    assert samples == [
        {
            "turn_id": 1,
            "instruction": "我家有哪些作物",
            "tool_results": [
                {"tool_name": "get_farm_status", "result": {"crops": ["水稻"]}}
            ],
            "response": "当前有水稻",
            "source": "agent_event_log",
        }
    ]


def test_build_tool_selection_samples_from_router_events():
    events = [
        {
            "event_type": "message.user",
            "turn_id": 2,
            "payload": {"content": "停用李一凡"},
        },
        {
            "event_type": "router.decision",
            "turn_id": 2,
            "payload": {
                "selected_tools": ["manage_workers"],
                "rejected_tools": ["get_workers"],
                "fallback": False,
            },
        },
        {
            "event_type": "tool.call.finished",
            "turn_id": 2,
            "payload": {"tool_name": "manage_workers", "status": "pending"},
        },
    ]

    samples = build_tool_selection_samples(events)

    assert samples == [
        {
            "turn_id": 2,
            "input": "停用李一凡",
            "selected_tools": ["manage_workers"],
            "rejected_tools": ["get_workers"],
            "actual_tools": ["manage_workers"],
            "fallback": False,
            "source": "agent_event_log",
        }
    ]
