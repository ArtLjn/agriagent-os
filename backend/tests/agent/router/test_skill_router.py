"""Skill Catalog 测试。"""

from unittest.mock import MagicMock

import pytest
from pydantic import BaseModel, Field

from app.agent.router.catalog import SkillCatalog
from app.agent.router.service import SkillRouter

pytestmark = pytest.mark.no_db


def _tool(name: str, description: str = ""):
    tool = MagicMock()
    tool.name = name
    tool.description = description
    return tool


def test_catalog_enriches_work_order_metadata() -> None:
    catalog = SkillCatalog.from_tools(
        [
            _tool(
                "create_operation_work_order",
                "创建农事作业单，可同时记录多个工人",
            )
        ]
    )

    candidate = catalog.get("create_operation_work_order")

    assert candidate is not None
    assert candidate.domain == "operation"
    assert candidate.risk == "write_confirm"
    assert "create_work_order" in candidate.intents
    assert "workers" in candidate.context_dependencies
    assert "今天李树去6号棚收水稻" in candidate.trigger_examples


def test_catalog_marks_disabled_tools() -> None:
    tool = _tool("web_search")
    tool.skill_metadata = type("SkillMetadataStub", (), {"enabled": False})()

    catalog = SkillCatalog.from_tools([tool])

    assert catalog.get("web_search").enabled is False


def test_catalog_falls_back_to_disabled_skills() -> None:
    catalog = SkillCatalog.from_tools([_tool("web_search")])

    assert catalog.get("web_search").enabled is False


def test_catalog_metadata_enabled_overrides_disabled_skills() -> None:
    tool = _tool("web_search")
    tool.skill_metadata = type("SkillMetadataStub", (), {"enabled": True})()

    catalog = SkillCatalog.from_tools([tool])

    assert catalog.get("web_search").enabled is True


def test_explicit_web_search_selects_enabled_search_tool() -> None:
    tool = _tool("web_search")
    tool.skill_metadata = type("SkillMetadataStub", (), {"enabled": True})()

    decision = SkillRouter().route("搜索一下天气新闻", [tool, _tool("get_farm_status")])

    assert decision.selected_tools == ["web_search"]
    assert decision.frames[0].intent == "query_web_search"
    assert decision.frames[0].risk == "read"


def test_catalog_defaults_write_skill_risk() -> None:
    catalog = SkillCatalog.from_tools([_tool("create_cost_record")])

    assert catalog.get("create_cost_record").risk == "write_confirm"


def test_catalog_estimates_schema_tokens_from_pydantic_fields() -> None:
    class WorkOrderArgs(BaseModel):
        worker_name: str = Field(
            description="工人姓名，用于从工人档案中匹配具体作业人员"
        )
        planting_unit_name: str = Field(
            description="种植单元名称，用于定位地块、大棚或棚区"
        )
        operation_type: str = Field(
            description="农事作业类型，例如采收、授粉、整枝、打杈、装车"
        )
        quantity: int = Field(description="作业数量或用工数量，必须是正整数")

    tool_with_schema = _tool("custom_schema_tool", "创建作业单")
    tool_with_schema.args_schema = WorkOrderArgs
    tool_without_schema = _tool("custom_schema_tool", "创建作业单")
    tool_without_schema.args_schema = None

    catalog_with_schema = SkillCatalog.from_tools([tool_with_schema])
    catalog_without_schema = SkillCatalog.from_tools([tool_without_schema])

    with_schema = catalog_with_schema.get("custom_schema_tool")
    without_schema = catalog_without_schema.get("custom_schema_tool")

    assert with_schema.schema_token_estimate > 300
    assert with_schema.schema_token_estimate > without_schema.schema_token_estimate


def test_catalog_handles_magicmock_tool_metadata() -> None:
    """MagicMock 工具的非标准 metadata 不应让 catalog 构建崩溃。"""
    tool = MagicMock()
    tool.name = "get_weather_forecast"

    catalog = SkillCatalog.from_tools([tool])

    candidate = catalog.get("get_weather_forecast")
    assert candidate is not None
    assert candidate.schema_token_estimate >= 80


def test_session5_active_crop_query_selects_at_most_two_tools() -> None:
    tools = [
        _tool("get_farm_status"),
        _tool("get_crop_cycle_info"),
        _tool("create_crop_cycle"),
        _tool("manage_workers"),
        _tool("create_operation_work_order"),
    ]

    decision = SkillRouter().route("我家有哪些作物栽种", tools)

    assert len(decision.selected_tools) <= 2
    assert set(decision.selected_tools) <= {"get_farm_status", "get_crop_cycle_info"}
    assert decision.fallback != "fallback_all"
    assert "create_operation_work_order" not in decision.selected_tools


def test_greeting_binds_no_tools() -> None:
    tools = [_tool("get_farm_status"), _tool("create_cost_record")]

    decision = SkillRouter().route("你好", tools)

    assert decision.selected_tools == []
    assert decision.fallback == "no_tools"


def test_unknown_farm_read_uses_safe_default() -> None:
    tools = [_tool("get_farm_status"), _tool("create_crop_cycle")]

    decision = SkillRouter().route("农场最近怎么样", tools)

    assert decision.selected_tools == ["get_farm_status"]
    assert decision.fallback == "safe_read_default"


@pytest.mark.parametrize("message", ["明天苏州什么天气", "今天天气", "明天会下雨吗"])
def test_weather_query_selects_weather_tool(message: str) -> None:
    tools = [_tool("get_weather_forecast"), _tool("get_farm_status")]

    decision = SkillRouter().route(message, tools)

    assert decision.selected_tools == ["get_weather_forecast"]
    assert decision.frames[0].intent == "query_weather"


def test_temperature_sensor_question_does_not_select_weather_tool() -> None:
    tools = [_tool("get_weather_forecast"), _tool("get_farm_status")]

    decision = SkillRouter().route("温度传感器怎么安装", tools)

    assert decision.selected_tools == []


@pytest.mark.parametrize("message", ["西瓜怎么种", "怎么种小麦", "种小麦要注意什么"])
def test_planting_advice_uses_read_frame(message: str) -> None:
    tools = [_tool("get_farm_status"), _tool("create_crop_cycle")]

    decision = SkillRouter().route(message, tools)

    assert decision.selected_tools == ["get_farm_status"]
    assert decision.frames[0].intent == "query_planting_advice"
    assert decision.frames[0].risk == "read"


def test_unknown_write_asks_clarification_without_write_tool() -> None:
    tools = [_tool("manage_workers"), _tool("create_operation_work_order")]

    decision = SkillRouter().route("帮我处理一下这个工人的事情", tools)

    assert decision.selected_tools == []
    assert decision.clarification is not None
    assert "请补充" in decision.clarification


@pytest.mark.parametrize(
    "message",
    ["帮我删一下这个工人", "帮我改一下这个作业", "帮我停用一下这个工人"],
)
def test_unknown_mutating_intent_asks_clarification_without_write_tool(
    message: str,
) -> None:
    tools = [_tool("manage_workers"), _tool("create_operation_work_order")]

    decision = SkillRouter().route(message, tools)

    assert decision.selected_tools == []
    assert decision.clarification is not None
    assert "请补充" in decision.clarification


def test_session4_create_worker_and_work_order_keeps_single_write_tool() -> None:
    tools = [_tool("manage_workers"), _tool("create_operation_work_order")]

    router = SkillRouter()
    decision = router.route(
        "我招了一个工人王大妈工资100一天，早上来了让他去5号棚收水稻了",
        tools,
    )

    assert [frame.intent for frame in decision.frames] == [
        "create_worker",
        "create_work_order",
    ]
    assert decision.selected_tools == ["manage_workers"]
    worker_frame = decision.frames[0]
    assert worker_frame.params_hint is not None
    assert worker_frame.params_hint["name"] == "王大妈"
    assert worker_frame.params_hint["default_unit_price"] == 100
    assert worker_frame.params_hint["default_pay_type"] == "daily"
    work_order_frame = decision.frames[1]
    assert work_order_frame.depends_on == ["create_worker"]
    assert work_order_frame.params_hint is not None
    assert work_order_frame.params_hint["unit_price"] == 100
    assert work_order_frame.params_hint["workers"] == ["王大妈"]
    assert work_order_frame.params_hint["unit_names"] == ["5号棚"]
    assert work_order_frame.params_hint["operation_type"] == "采收"

    assert router.build_pending_plan_steps(decision) == [
        {
            "step_id": "create_worker",
            "tool_name": "manage_workers",
            "params": {
                "action": "create",
                "name": "王大妈",
                "default_pay_type": "daily",
                "default_unit_price": 100,
            },
            "depends_on": [],
        },
        {
            "step_id": "create_work_order",
            "tool_name": "create_operation_work_order",
            "params": {
                "workers": ["王大妈"],
                "unit_names": ["5号棚"],
                "operation_type": "采收",
                "unit_price": 100,
            },
            "depends_on": ["create_worker"],
        },
    ]


def test_income_receipt_does_not_select_create_work_order() -> None:
    tools = [_tool("create_cost_record"), _tool("create_operation_work_order")]

    decision = SkillRouter().route("收到客户付款100元", tools)

    assert "create_operation_work_order" not in decision.selected_tools
    assert all(frame.intent != "create_work_order" for frame in decision.frames)


def test_session4_extracts_wage_after_greenhouse_number() -> None:
    tools = [_tool("manage_workers"), _tool("create_operation_work_order")]

    decision = SkillRouter().route("让王大妈去5号棚收水稻，工资100一天", tools)

    work_order_frame = next(
        frame for frame in decision.frames if frame.intent == "create_work_order"
    )
    assert work_order_frame.params_hint is not None
    assert work_order_frame.params_hint["unit_price"] == 100
    assert work_order_frame.params_hint["unit_names"] == ["5号棚"]
    assert "create_operation_work_order" in work_order_frame.candidate_tools


def test_multi_intent_worker_name_with_digit_and_field_name_are_extracted() -> None:
    tools = [_tool("manage_workers"), _tool("create_operation_work_order")]

    decision = SkillRouter().route(
        "今天来了一个工人李1工资100一天他收水稻厉害今天让他去大豆地采收",
        tools,
    )

    worker_frame = next(
        frame for frame in decision.frames if frame.intent == "create_worker"
    )
    work_order_frame = next(
        frame for frame in decision.frames if frame.intent == "create_work_order"
    )
    assert worker_frame.params_hint is not None
    assert worker_frame.params_hint["name"] == "李1"
    assert worker_frame.params_hint["default_unit_price"] == 100
    assert work_order_frame.params_hint is not None
    assert work_order_frame.params_hint["workers"] == ["李1"]
    assert work_order_frame.params_hint["unit_names"] == ["大豆地"]
    assert work_order_frame.params_hint["operation_type"] == "采收"
    assert SkillRouter().build_pending_plan_steps(decision) == [
        {
            "step_id": "create_worker",
            "tool_name": "manage_workers",
            "params": {
                "action": "create",
                "name": "李1",
                "default_pay_type": "daily",
                "default_unit_price": 100,
            },
            "depends_on": [],
        },
        {
            "step_id": "create_work_order",
            "tool_name": "create_operation_work_order",
            "params": {
                "workers": ["李1"],
                "unit_names": ["大豆地"],
                "operation_type": "采收",
                "unit_price": 100,
            },
            "depends_on": ["create_worker"],
        },
    ]


def test_build_pending_plan_steps_deep_copies_params_hint() -> None:
    router = SkillRouter()
    decision = router.route(
        "我招了一个工人王大妈工资100一天，早上来了让他去5号棚收水稻了",
        [_tool("manage_workers"), _tool("create_operation_work_order")],
    )
    work_order_frame = next(
        frame for frame in decision.frames if frame.intent == "create_work_order"
    )

    steps = router.build_pending_plan_steps(decision)
    steps[1]["params"]["workers"].append("李师傅")

    assert work_order_frame.params_hint is not None
    assert work_order_frame.params_hint["workers"] == ["王大妈"]


@pytest.mark.parametrize("message", ["我的作业单有哪些", "采收作业有哪些"])
def test_work_order_read_queries_do_not_expose_write_tool(message: str) -> None:
    tools = [_tool("get_operation_work_orders"), _tool("create_operation_work_order")]

    decision = SkillRouter().route(message, tools)

    assert decision.selected_tools == ["get_operation_work_orders"]
    assert "create_operation_work_order" not in decision.selected_tools
