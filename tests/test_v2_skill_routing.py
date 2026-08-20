from pathlib import Path
from types import SimpleNamespace

import pytest

from agent.skills.loader import _load_skill, load_all


def _ctx(user_input: str, business_client=None):
    return SimpleNamespace(
        turn=SimpleNamespace(user_input=user_input),
        business_client=business_client,
    )


def _loaded(name: str):
    return next(skill for skill in load_all() if skill.name == name)


def test_aggregate_manage_tools_are_not_exposed_to_model():
    names = {skill.name for skill in load_all()}

    assert "manage_crop_cycle" not in names
    assert "manage_cost" not in names
    assert "manage_workers" not in names
    assert "query_crop_cycles" in names
    assert "create_crop_cycle" in names
    assert "create_worker" in names


def test_user_settings_skill_exposes_query_and_update_operations():
    names = {skill.name for skill in load_all()}

    assert "manage_user_settings" not in names
    assert "get_user_settings" in names
    assert "update_user_settings" in names

    query = _loaded("get_user_settings")
    update = _loaded("update_user_settings")
    assert query.risk_level == "read"
    assert update.risk_level == "write_confirm"
    assert set(update.parameters_schema["properties"]) == {
        "default_city",
        "default_lat",
        "default_lon",
        "assistant_role",
    }


def test_operation_skill_schema_does_not_expose_internal_operation():
    skill = _loaded("create_crop_cycle")
    schema = skill.parameters_schema

    assert "operation" not in schema["properties"]
    assert schema["required"] == [
        "name",
        "crop_name",
        "crop_template_id",
        "start_date",
    ]
    assert set(schema["properties"]) == {
        "name",
        "crop_name",
        "crop_template_id",
        "start_date",
        "field_name",
        "total_area_mu",
        "season",
        "batch_note",
    }


def test_operation_skill_description_is_user_intent_facing():
    skill = _loaded("query_crop_cycles")
    description = skill.to_openai_tool()["function"]["description"]

    assert description == "查询当前农场的种植茬口列表。"
    assert "operation" not in description
    assert "MCP" not in description


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("skill_name", "business_tool", "operation", "arguments"),
    [
        ("create_worker", "manage_workers", "create", {"name": "张三"}),
        (
            "create_cost_record",
            "manage_cost",
            "create",
            {
                "record_type": "income",
                "category": "销售",
                "amount": 500,
                "record_date": "2026-08-07",
            },
        ),
        (
            "create_debt_record",
            "manage_debt",
            "create",
            {
                "record_type": "debt_payable",
                "amount": 500,
                "record_date": "2026-08-07",
            },
        ),
        (
            "create_crop_cycle",
            "manage_crop_cycle",
            "create",
            {
                "name": "秋季番茄",
                "crop_name": "番茄",
                "crop_template_id": 1,
                "start_date": "2026-08-07",
            },
        ),
        (
            "create_farm_log",
            "manage_farm_logs",
            "create",
            {"cycle_id": 1, "operation_type": "施肥"},
        ),
        (
            "create_work_order",
            "manage_work_orders",
            "create",
            {"operation_type": "浇水", "operation_date": "2026-08-07"},
        ),
    ],
)
async def test_write_skills_inject_internal_operation_for_business_mcp(
    skill_name: str,
    business_tool: str,
    operation: str,
    arguments: dict,
):
    calls = []

    class Business:
        async def call_tool(self, name, arguments):
            calls.append((name, arguments))
            return {"ok": True}

    skill = _loaded(skill_name)
    result = await skill.execute(arguments, _ctx("执行业务动作", Business()))

    assert result.ok
    assert calls == [(business_tool, {**arguments, "operation": operation})]


@pytest.mark.asyncio
async def test_missing_business_information_never_calls_mcp():
    class BusinessMustNotBeCalled:
        async def call_tool(self, *_args, **_kwargs):
            raise AssertionError("缺少业务信息时不应调用 Business MCP")

    skill = _loaded("create_worker")
    result = await skill.execute({}, _ctx("新来一个工人", BusinessMustNotBeCalled()))

    assert not result.ok
    assert "工人姓名" in result.error
    assert "operation" not in result.error


@pytest.mark.asyncio
async def test_weather_without_explicit_location_uses_farm_default():
    calls = []

    class Business:
        async def call_tool(self, name, arguments):
            calls.append((name, arguments))
            return {"location": "虎丘区"}

    skill = _loaded("get_weather")
    ctx = SimpleNamespace(
        turn=SimpleNamespace(user_input="查询天气如何", events=[]),
        business_client=Business(),
    )

    result = await skill.execute({}, ctx)

    assert result.ok
    assert calls == [("get_weather", {})]


@pytest.mark.parametrize(
    ("skill_name", "expected_risk"),
    [
        ("query_crop_cycles", "read"),
        ("create_crop_cycle", "write_confirm"),
        ("delete_crop_cycle", "write_high"),
        ("create_cost_record", "write_confirm"),
        ("deactivate_worker", "write_confirm"),
    ],
)
def test_operation_skill_uses_operation_risk(skill_name: str, expected_risk: str):
    assert _loaded(skill_name).dynamic_risk_level({}) == expected_risk


def test_public_tool_names_are_unique():
    names = [skill.name for skill in load_all()]

    assert len(names) == len(set(names))


def test_source_skill_still_maps_to_business_mcp():
    source = _load_skill(
        Path("//agent/skills/manage-crop-cycle")
    )

    assert source is not None
    assert source.mcp_tool == "manage_crop_cycle"
