"""工具 metadata 辅助逻辑回归测试。"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.messages import AIMessage, HumanMessage

from app.agent.runtime import tool_executor, tool_metadata
from app.skills.metadata import SkillMetadata, SkillPermissionLevel

pytestmark = pytest.mark.no_db


def test_tool_executor_reexports_permission_decision() -> None:
    assert tool_executor._permission_decision is tool_metadata._permission_decision


@pytest.mark.asyncio
async def test_read_tool_trace_keeps_result_metadata_and_permission() -> None:
    class _Result:
        trace_data = {"status": "domain_ok", "rows": 2}

        def __str__(self) -> str:
            return "结构化结果"

    tool = SimpleNamespace(
        name="metadata_read_tool",
        args_schema=None,
        ainvoke=AsyncMock(return_value=_Result()),
        skill_metadata=SkillMetadata(permission_level=SkillPermissionLevel.READ),
    )
    collector = MagicMock()
    state = {
        "messages": [
            HumanMessage(content="查一下数据"),
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "id": "tc-read",
                        "name": "metadata_read_tool",
                        "args": {"limit": 2},
                    }
                ],
            ),
        ],
        "farm_id": 1,
    }

    with (
        patch(
            "app.agent.runtime.tool_executor.get_langchain_tools",
            return_value=[tool],
        ),
        patch(
            "app.agent.runtime.tool_executor.get_collector",
            return_value=collector,
        ),
    ):
        result = await tool_executor._parallel_tool_node(state)

    message = result["messages"][0]
    assert message.name == "metadata_read_tool"
    assert message.content == "结构化结果"
    output_data = collector.record.call_args.kwargs["output_data"]
    assert output_data["status"] == "domain_ok"
    assert output_data["rows"] == 2
    assert output_data["reply_preview"] == "结构化结果"
    assert output_data["permission_level"] == "read"
