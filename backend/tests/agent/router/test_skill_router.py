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
    assert candidate.capability == "manage_work_orders"
    assert candidate.operation == "create_work_order"
    assert candidate.legacy_alias == "create_operation_work_order"
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


def test_disabled_web_search_is_rejected_without_selection() -> None:
    decision = SkillRouter().route(
        "搜索一下天气新闻",
        [_tool("web_search"), _tool("get_farm_status")],
    )

    assert decision.selected_tools == []
    assert decision.rejected_tools == ["web_search"]
    assert decision.rejected_candidates[0]["reason"] == "disabled"
    assert "disabled_candidate_rejected" in decision.policy_violations


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


@pytest.mark.parametrize(
    "message",
    ["我的作物", "我家有哪些作物栽种", "当前种了哪些作物", "现在地里都种着什么"],
)
def test_crop_inventory_query_routes_to_crop_cycles(message: str) -> None:
    tools = [
        _tool("get_farm_status"),
        _tool("get_crop_cycles"),
        _tool("get_crop_cycle_info"),
        _tool("create_crop_cycle"),
        _tool("manage_workers"),
        _tool("create_operation_work_order"),
    ]

    decision = SkillRouter().route(message, tools)

    assert len(decision.selected_tools) <= 2
    assert decision.selected_tools[0] == "get_crop_cycles"
    assert set(decision.selected_tools) <= {"get_crop_cycles", "get_farm_status"}
    assert decision.fallback != "fallback_all"
    assert "create_operation_work_order" not in decision.selected_tools


@pytest.mark.parametrize(
    ("message", "expected_tools"),
    [
        ("今日天气对作物有什么影响", ["get_weather_forecast", "get_farm_status"]),
        ("今天适合给作物打药吗", ["get_weather_forecast", "get_farm_status"]),
    ],
)
def test_crop_inventory_rule_does_not_capture_advice_or_overview(
    message: str, expected_tools: list[str]
) -> None:
    tools = [
        _tool("get_weather_forecast"),
        _tool("get_farm_status"),
        _tool("get_crop_cycles"),
        _tool("get_crop_cycle_info"),
    ]

    decision = SkillRouter().route(message, tools)

    assert decision.selected_tools == expected_tools


def test_farm_overview_read_exposes_shortlisted_read_pool_to_model() -> None:
    tools = [
        _tool("get_weather_forecast"),
        _tool("get_farm_status"),
        _tool("get_crop_cycles"),
        _tool("get_crop_cycle_info"),
    ]

    decision = SkillRouter().route("农场整体状态怎么样", tools)

    assert decision.selected_tools == [
        "get_weather_forecast",
        "get_farm_status",
        "get_crop_cycles",
    ]
    assert decision.frames[0].intent == "model_choice_read"
    assert decision.fallback != "fallback_all"
    assert decision.fallback_reason == "no_explicit_candidate"


@pytest.mark.parametrize("message", ["你好", "nihao", "ni hao"])
def test_greeting_binds_no_tools(message: str) -> None:
    tools = [_tool("get_farm_status"), _tool("create_cost_record")]

    decision = SkillRouter().route(message, tools)

    assert decision.selected_tools == []
    assert decision.fallback == "no_tools"


def test_unknown_farm_read_uses_model_choice_read() -> None:
    tools = [
        _tool("get_farm_status"),
        _tool("get_crop_cycles"),
        _tool("create_crop_cycle"),
    ]

    decision = SkillRouter().route("农场最近怎么样", tools)

    assert decision.selected_tools == ["get_farm_status", "get_crop_cycles"]
    assert decision.fallback == "model_choice_read_default"
    assert decision.frames[0].intent == "model_choice_read"


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


@pytest.mark.parametrize(
    "message",
    ["今天适合做什么", "今天适合做啥", "今天适合打药吗"],
)
def test_daily_operation_advice_binds_weather_and_farm_status(message: str) -> None:
    tools = [_tool("get_weather_forecast"), _tool("get_farm_status")]

    decision = SkillRouter().route(message, tools)

    assert decision.selected_tools == ["get_weather_forecast", "get_farm_status"]
    assert decision.frames[0].intent == "query_daily_operation_advice"
    assert decision.frames[0].risk == "read"


def test_english_money_query_binds_finance_read_tools() -> None:
    tools = [_tool("get_cost_summary"), _tool("get_debt_summary")]

    decision = SkillRouter().route("money", tools)

    assert decision.selected_tools == ["get_cost_summary", "get_debt_summary"]
    assert decision.frames[0].intent == "query_finance_overview"
    assert decision.frames[0].risk == "read"


@pytest.mark.parametrize("message", ["查询我的财务", "查一下账务", "我的财务情况"])
def test_chinese_finance_query_exposes_read_pool_to_model(message: str) -> None:
    tools = [
        _tool("get_cost_summary"),
        _tool("get_debt_summary"),
        _tool("get_farm_status"),
        _tool("create_cost_record"),
    ]

    decision = SkillRouter().route(message, tools)

    assert decision.selected_tools == [
        "get_cost_summary",
        "get_debt_summary",
        "get_farm_status",
    ]
    assert decision.frames[0].intent == "model_choice_read"
    assert decision.frames[0].risk == "read"


@pytest.mark.parametrize(
    "message", ["你可以查询哪些", "你能查什么", "你的功能是啥", "你可以做啥"]
)
def test_capability_question_exposes_shortlisted_read_pool_to_model(
    message: str,
) -> None:
    tools = [
        _tool("get_cost_summary"),
        _tool("get_debt_summary"),
        _tool("get_farm_status"),
        _tool("get_weather_forecast"),
        _tool("create_cost_record"),
    ]

    decision = SkillRouter().route(message, tools)

    assert decision.selected_tools == [
        "get_cost_summary",
        "get_debt_summary",
        "get_farm_status",
    ]
    assert decision.frames[0].intent == "model_choice_read"
    assert decision.frames[0].risk == "read"
    assert decision.fallback != "fallback_all"


@pytest.mark.parametrize(
    "message", ["帮我检查代码", "排查一下这个问题", "为什么会这样"]
)
def test_non_business_debug_or_explanation_keeps_no_tools(
    message: str,
) -> None:
    tools = [_tool("get_cost_summary"), _tool("get_farm_status")]

    decision = SkillRouter().route(message, tools)

    assert decision.selected_tools == []
    assert decision.fallback == "no_tools"


def test_uncategorized_business_read_exposes_read_pool_to_model() -> None:
    tools = [
        _tool("get_cost_summary"),
        _tool("get_debt_summary"),
        _tool("get_farm_status"),
        _tool("create_cost_record"),
    ]

    decision = SkillRouter().route("我要看一下经营数据", tools)

    assert decision.selected_tools == [
        "get_cost_summary",
        "get_debt_summary",
        "get_farm_status",
    ]
    assert decision.frames[0].intent == "model_choice_read"


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
                "workers": "王大妈",
                "unit_names": "5号棚",
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


def test_implicit_labor_operation_routes_to_work_order_not_no_tool() -> None:
    tools = [
        _tool("create_operation_work_order"),
        _tool("get_labor_payables"),
        _tool("manage_workers"),
    ]

    decision = SkillRouter().route("李海这个月干了15天压瓜", tools)

    assert decision.fallback != "no_tools"
    assert "create_operation_work_order" in decision.selected_tools
    assert "get_labor_payables" not in decision.selected_tools
    work_order_frame = next(
        frame for frame in decision.frames if frame.intent == "create_work_order"
    )
    assert work_order_frame.params_hint is not None
    assert work_order_frame.params_hint["workers"] == ["李海"]
    assert work_order_frame.params_hint["operation_type"] == "压瓜"
    assert work_order_frame.params_hint["quantity"] == 15
    assert work_order_frame.params_hint["pay_type"] == "daily"
    assert "unit_price" not in work_order_frame.params_hint
    assert work_order_frame.planning_evidence == {
        "worker": "李海",
        "operation_type": "压瓜",
        "quantity": 15,
        "pay_type": "daily",
        "write_risk": "implicit_farm_labor_work",
    }
    assert work_order_frame.missing_fields == ["unit_price_or_default_wage"]


def test_implicit_labor_without_operation_asks_clarification() -> None:
    tools = [
        _tool("create_operation_work_order"),
        _tool("get_labor_payables"),
        _tool("manage_workers"),
    ]

    decision = SkillRouter().route("李海这个月干了15天", tools)

    assert decision.selected_tools == []
    assert decision.clarification is not None
    assert "作业类型" in decision.clarification
    assert len(decision.frames) == 1
    frame = decision.frames[0]
    assert frame.intent == "clarify_farm_labor_work"
    assert frame.planning_evidence["worker"] == "李海"
    assert frame.planning_evidence["quantity"] == 15
    assert frame.missing_fields == ["operation_type"]


def test_farm_labor_statement_extracts_worker_unit_operation_and_daily_wage() -> None:
    tools = [
        _tool("create_operation_work_order"),
        _tool("get_labor_payables"),
        _tool("manage_workers"),
    ]

    decision = SkillRouter().route("今天李海去6号棚压蔓工资100一天", tools)

    assert decision.selected_tools == ["create_operation_work_order"]
    assert "get_labor_payables" not in decision.selected_tools
    work_order_frame = next(
        frame for frame in decision.frames if frame.intent == "create_work_order"
    )
    assert work_order_frame.params_hint is not None
    assert work_order_frame.params_hint["workers"] == ["李海"]
    assert work_order_frame.params_hint["unit_names"] == ["6号棚"]
    assert work_order_frame.params_hint["operation_type"] == "压蔓"
    assert work_order_frame.params_hint["unit_price"] == 100


def test_new_worker_and_work_order_keeps_two_step_dependency() -> None:
    tools = [_tool("manage_workers"), _tool("create_operation_work_order")]

    decision = SkillRouter().route(
        "新来一个工人李丽工资100一天，今天去6号棚收水稻", tools
    )

    assert [
        frame.intent for frame in decision.frames if frame.requires_confirmation
    ] == [
        "create_worker",
        "create_work_order",
    ]
    assert decision.selected_tools == ["manage_workers"]
    steps = SkillRouter().build_pending_plan_steps(decision)
    assert steps == [
        {
            "step_id": "create_worker",
            "tool_name": "manage_workers",
            "params": {
                "action": "create",
                "name": "李丽",
                "default_pay_type": "daily",
                "default_unit_price": 100,
            },
            "depends_on": [],
        },
        {
            "step_id": "create_work_order",
            "tool_name": "create_operation_work_order",
            "params": {
                "workers": "李丽",
                "unit_names": "6号棚",
                "operation_type": "采收",
                "unit_price": 100,
            },
            "depends_on": ["create_worker"],
        },
    ]


@pytest.mark.parametrize(
    ("message", "tools"),
    [
        ("你好", [_tool("create_operation_work_order"), _tool("get_labor_payables")]),
        (
            "李海最近挺忙的",
            [_tool("create_operation_work_order"), _tool("get_labor_payables")],
        ),
        (
            "老王还欠多少人工钱",
            [_tool("create_operation_work_order"), _tool("get_labor_payables")],
        ),
    ],
)
def test_farm_labor_semantic_gate_keeps_greeting_chitchat_and_query_negative_cases(
    message: str,
    tools: list,
) -> None:
    decision = SkillRouter().route(message, tools)

    assert "create_operation_work_order" not in decision.selected_tools
    if "人工钱" in message:
        assert decision.selected_tools == ["get_labor_payables"]


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
                "workers": "李1",
                "unit_names": "大豆地",
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
    steps[1]["params"]["workers"] = "王大妈,李师傅"

    assert work_order_frame.params_hint is not None
    assert work_order_frame.params_hint["workers"] == ["王大妈"]


@pytest.mark.parametrize("message", ["我的作业单有哪些", "采收作业有哪些"])
def test_work_order_read_queries_do_not_expose_write_tool(message: str) -> None:
    tools = [_tool("get_operation_work_orders"), _tool("create_operation_work_order")]

    decision = SkillRouter().route(message, tools)

    assert decision.selected_tools == ["get_operation_work_orders"]
    assert "create_operation_work_order" not in decision.selected_tools


@pytest.mark.parametrize(
    ("message", "tool_name", "capability", "operation"),
    [
        ("这个月花了多少钱", "get_cost_summary", "manage_cost", "query_summary"),
        ("我的茬口有哪些", "get_crop_cycles", "manage_crop_cycle", "query_cycles"),
        ("我的工人有哪些", "get_workers", "manage_workers", "query_workers"),
        (
            "我的作业单有哪些",
            "get_operation_work_orders",
            "manage_work_orders",
            "query_work_orders",
        ),
        (
            "还欠多少人工钱",
            "get_labor_payables",
            "manage_labor_payment",
            "query_payables",
        ),
        (
            "我的默认天气城市是什么",
            "get_user_settings",
            "manage_settings",
            "query_settings",
        ),
        (
            "把默认天气城市改成苏州",
            "manage_user_settings",
            "manage_settings",
            "update_settings",
        ),
    ],
)
def test_registry_capability_routing_metadata_is_preserved(
    message: str,
    tool_name: str,
    capability: str,
    operation: str,
) -> None:
    decision = SkillRouter().route(message, [_tool(tool_name)])

    assert decision.selected_tools == [tool_name]
    assert decision.selected_operations == {capability: [operation]}
    assert decision.scores["capability"][capability] >= 0.85
    assert decision.scores["operation"][operation] >= 0.85
    assert decision.frames[0].capability == capability
    assert decision.frames[0].operation == operation


@pytest.mark.parametrize(
    "message",
    [
        "我的设置",
        "查看我的设置",
        "查询我的设置",
        "我的默认天气城市是什么",
        "默认天气城市设置是什么",
        "当前助手回复角色是什么",
        "我的默认经纬度是什么",
        "当前默认经纬度是多少",
    ],
)
def test_settings_read_query_does_not_expose_write_tool(message: str) -> None:
    decision = SkillRouter().route(
        message,
        [_tool("get_user_settings"), _tool("manage_user_settings")],
    )

    assert decision.selected_tools == ["get_user_settings"]
    assert decision.selected_operations == {"manage_settings": ["query_settings"]}
    assert "manage_user_settings" not in decision.selected_tools


@pytest.mark.parametrize(
    "message",
    [
        "把默认天气城市改成苏州",
        "设置默认天气城市为苏州",
        "修改助手回复角色",
        "设置默认经纬度为31.2,120.6",
        "把默认经纬度改成31.2,120.6",
    ],
)
def test_settings_update_uses_write_confirm_operation(message: str) -> None:
    decision = SkillRouter().route(
        message,
        [_tool("get_user_settings"), _tool("manage_user_settings")],
    )

    assert decision.selected_tools == ["manage_user_settings"]
    assert decision.selected_operations == {"manage_settings": ["update_settings"]}
    assert decision.frames[0].risk == "write_confirm"
    assert decision.frames[0].requires_confirmation is True


@pytest.mark.parametrize(
    "message",
    [
        "我的工人",
        "工人列表",
        "有哪些工人",
        "看看工人",
        "查询工人",
        "查一下工人",
    ],
)
def test_worker_read_query_does_not_expose_write_tool(message: str) -> None:
    decision = SkillRouter().route(
        message,
        [_tool("get_workers"), _tool("manage_workers")],
    )

    assert decision.selected_tools == ["get_workers"]
    assert decision.selected_operations == {"manage_workers": ["query_workers"]}
    assert "manage_workers" not in decision.selected_tools
    assert decision.frames[0].risk == "read"


@pytest.mark.parametrize(
    "message",
    [
        "新增工人张三",
        "添加一个工人李四",
        "把张三的电话改成13800000000",
        "删除工人张三",
    ],
)
def test_worker_management_uses_write_confirm_operation(message: str) -> None:
    decision = SkillRouter().route(
        message,
        [_tool("get_workers"), _tool("manage_workers")],
    )

    assert decision.selected_tools == ["manage_workers"]
    assert decision.selected_operations == {"manage_workers": ["manage_worker"]}
    assert decision.frames[0].risk == "write_confirm"
    assert decision.frames[0].requires_confirmation is True


@pytest.mark.parametrize(
    "message",
    [
        "有哪些地块",
        "地块列表",
        "有哪些大棚",
        "看看种植单元",
        "查询种植单元",
    ],
)
def test_planting_unit_read_query_does_not_expose_write_tool(
    message: str,
) -> None:
    decision = SkillRouter().route(
        message,
        [_tool("get_planting_units"), _tool("manage_planting_units")],
    )

    assert decision.selected_tools == ["get_planting_units"]
    assert decision.selected_operations == {"manage_planting_units": ["query_units"]}
    assert "manage_planting_units" not in decision.selected_tools
    assert decision.frames[0].risk == "read"


@pytest.mark.parametrize(
    "message",
    [
        "新增地块一号棚",
        "添加一个大棚A区",
        "把一号棚面积改成20亩",
        "删除地块一号棚",
    ],
)
def test_planting_unit_management_uses_write_confirm_operation(
    message: str,
) -> None:
    decision = SkillRouter().route(
        message,
        [_tool("get_planting_units"), _tool("manage_planting_units")],
    )

    assert decision.selected_tools == ["manage_planting_units"]
    assert decision.selected_operations == {"manage_planting_units": ["manage_units"]}
    assert decision.frames[0].risk == "write_confirm"
    assert decision.frames[0].requires_confirmation is True


@pytest.mark.parametrize(
    "message",
    [
        "处理一下这个地块",
        "删除地块",
        "删除这个地块",
        "删除大棚",
        "把这个地块面积改成20亩",
    ],
)
def test_ambiguous_planting_unit_management_asks_clarification(
    message: str,
) -> None:
    decision = SkillRouter().route(
        message,
        [_tool("get_planting_units"), _tool("manage_planting_units")],
    )

    assert decision.selected_tools == []
    assert decision.clarification is not None
    assert "请补充" in decision.clarification


@pytest.mark.parametrize(
    "message",
    [
        "有哪些成本分类",
        "成本分类列表",
        "有哪些收入分类",
        "费用分类有哪些",
        "查询分类",
    ],
)
def test_cost_category_read_query_does_not_expose_write_tool(
    message: str,
) -> None:
    decision = SkillRouter().route(
        message,
        [_tool("get_cost_categories"), _tool("manage_cost_categories")],
    )

    assert decision.selected_tools == ["get_cost_categories"]
    assert decision.selected_operations == {
        "manage_cost_categories": ["query_categories"]
    }
    assert "manage_cost_categories" not in decision.selected_tools
    assert decision.frames[0].risk == "read"


@pytest.mark.parametrize(
    "message",
    [
        "新增成本分类农药",
        "添加一个收入分类销售收入",
        "删除成本分类农药",
        "删除分类 12",
    ],
)
def test_cost_category_management_uses_write_confirm_operation(
    message: str,
) -> None:
    decision = SkillRouter().route(
        message,
        [_tool("get_cost_categories"), _tool("manage_cost_categories")],
    )

    assert decision.selected_tools == ["manage_cost_categories"]
    assert decision.selected_operations == {
        "manage_cost_categories": ["manage_category"]
    }
    assert decision.frames[0].risk == "write_confirm"
    assert decision.frames[0].requires_confirmation is True


@pytest.mark.parametrize(
    "message",
    ["处理一下这个分类", "删除分类", "把化肥分类改成农资"],
)
def test_ambiguous_cost_category_management_asks_clarification(
    message: str,
) -> None:
    decision = SkillRouter().route(
        message,
        [_tool("get_cost_categories"), _tool("manage_cost_categories")],
    )

    assert decision.selected_tools == []
    assert decision.clarification is not None
    assert "请补充" in decision.clarification
