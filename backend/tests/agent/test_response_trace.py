from unittest.mock import patch

from app.agent.application.response_trace import record_agent_response


def test_record_agent_response_records_agent_response_node() -> None:
    with patch("app.agent.application.response_trace.get_collector") as mock_get:
        collector = mock_get.return_value

        record_agent_response(
            node_name="greeting_reply",
            user_input="你好",
            reply="你好呀",
            reason="greeting_shortcut",
        )

    collector.record.assert_called_once_with(
        node_type="agent_response",
        node_name="greeting_reply",
        input_data={"message": "你好"},
        output_data={"reply": "你好呀", "reason": "greeting_shortcut"},
    )
