"""update_crop_cycle pending action flow tests。"""

from datetime import date
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.messages import AIMessage, HumanMessage

from app.agent.runtime import tool_executor
from app.agent.runtime.tool_executor import _parallel_tool_node
from app.agent.skills.metadata import SkillMetadata, SkillPermissionLevel
from app.infra.pending_actions import get_pending, remove_pending
from app.models.crop import CropTemplate
from app.models.cycle import CropCycle


@pytest.fixture(autouse=True)
def clean_pending():
    remove_pending(1)
    yield
    remove_pending(1)


def _create_cycle(
    db,
    *,
    name: str = "夏季玉米",
    crop_name: str = "玉米",
    start_date: date = date(2026, 6, 5),
) -> CropCycle:
    template = CropTemplate(farm_id=1, name=crop_name)
    db.add(template)
    db.flush()
    cycle = CropCycle(
        farm_id=1,
        name=name,
        crop_template_id=template.id,
        start_date=start_date,
        status="active",
    )
    db.add(cycle)
    db.commit()
    db.refresh(cycle)
    return cycle


def _write_confirm_tool() -> SimpleNamespace:
    return SimpleNamespace(
        name="update_crop_cycle",
        args_schema=None,
        ainvoke=AsyncMock(return_value="不应直接执行"),
        skill_metadata=SkillMetadata(
            permission_level=SkillPermissionLevel.WRITE_CONFIRM,
            cache_invalidation=["crop_cycle", "get_farm_status"],
        ),
    )


@pytest.mark.asyncio
async def test_update_crop_cycle_tool_call_stores_structured_pending_context(
    monkeypatch, db_session
):
    _create_cycle(db_session)
    tool = _write_confirm_tool()
    collector = MagicMock()
    monkeypatch.setattr(tool_executor, "SessionLocal", lambda: db_session, raising=False)

    with patch(
        "app.agent.runtime.tool_executor.get_langchain_tools",
        return_value=[tool],
    ), patch("app.agent.runtime.tool_executor.get_collector", return_value=collector):
        result = await _parallel_tool_node(
            {
                "farm_id": 1,
                "farm_uid": "farm-uid-1",
                "messages": [
                    HumanMessage(content="修改玉米茬口9月1开始"),
                    AIMessage(
                        content="",
                        tool_calls=[
                            {
                                "name": "update_crop_cycle",
                                "args": {
                                    "crop_name": "玉米",
                                    "start_date": "2026-09-01",
                                },
                                "id": "tc-1",
                            }
                        ],
                    ),
                ],
            }
        )

    pending = get_pending(1)
    assert pending is not None
    assert pending.skill_name == "update_crop_cycle"
    assert pending.params == {"crop_name": "玉米", "start_date": "2026-09-01"}
    assert pending.confirmation_context["target"]["name"] == "夏季玉米"
    assert pending.confirmation_context["target"]["id"] == 1
    assert pending.confirmation_context["changes"][0]["old"] == "2026-06-05"
    assert pending.confirmation_context["changes"][0]["new"] == "2026-09-01"
    assert pending.confirmation_context["original_input"] == "修改玉米茬口9月1开始"
    assert "[PENDING_ACTION]" in result["messages"][0].content
    assert "修改茬口" in result["messages"][0].content
    assert "夏季玉米" in result["messages"][0].content
    assert "2026-06-05" in result["messages"][0].content
    assert "2026-09-01" in result["messages"][0].content
    tool.ainvoke.assert_not_awaited()
    assert (
        collector.record.call_args.kwargs["output_data"]["confirmation_context"]
        == pending.confirmation_context
    )


@pytest.mark.asyncio
async def test_update_crop_cycle_pending_context_uses_cycle_id_when_provided(
    monkeypatch, db_session
):
    cycle = _create_cycle(db_session, name="夏季玉米", crop_name="玉米")
    _create_cycle(db_session, name="秋季玉米", crop_name="玉米")
    tool = _write_confirm_tool()
    monkeypatch.setattr(tool_executor, "SessionLocal", lambda: db_session, raising=False)

    with patch(
        "app.agent.runtime.tool_executor.get_langchain_tools",
        return_value=[tool],
    ), patch("app.agent.runtime.tool_executor.get_collector", return_value=MagicMock()):
        await _parallel_tool_node(
            {
                "farm_id": 1,
                "farm_uid": "farm-uid-1",
                "messages": [
                    HumanMessage(content="把这个茬口改到9月1开始"),
                    AIMessage(
                        content="",
                        tool_calls=[
                            {
                                "name": "update_crop_cycle",
                                "args": {
                                    "cycle_id": cycle.id,
                                    "start_date": "2026-09-01",
                                },
                                "id": "tc-1",
                            }
                        ],
                    ),
                ],
            }
        )

    pending = get_pending(1)
    assert pending is not None
    assert pending.confirmation_context["target"]["id"] == cycle.id
    assert pending.confirmation_context["target"]["name"] == "夏季玉米"
    assert pending.confirmation_context["changes"][0]["old"] == "2026-06-05"
