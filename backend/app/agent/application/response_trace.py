"""Agent 回复 trace 记录。"""

from app.infra.trace_collector import get_collector


def record_agent_response(
    *,
    node_name: str,
    user_input: str,
    reply: str,
    reason: str,
) -> None:
    """记录不一定经过工具节点的最终回复。"""
    get_collector().record(
        node_type="agent_response",
        node_name=node_name,
        input_data={"message": user_input},
        output_data={"reply": reply, "reason": reason},
    )
