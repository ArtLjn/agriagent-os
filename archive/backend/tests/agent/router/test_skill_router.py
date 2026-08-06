"""Skill Catalog 测试。"""

import logging
from unittest.mock import MagicMock

import pytest
from pydantic import BaseModel, Field

from app.agent.router.catalog import SkillCatalog
from app.agent.router.hybrid_retriever import HybridOperationRetriever
from app.agent.router.service import SkillRouter

pytestmark = pytest.mark.no_db


@pytest.fixture(autouse=True)
def _disable_external_vector_search_by_default(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.agent.router.service.build_skill_vector_search_fn",
        lambda: None,
    )


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


def test_catalog_uses_registry_active_status_without_metadata() -> None:
    catalog = SkillCatalog.from_tools([_tool("web_search")])

    assert catalog.get("web_search").enabled is True


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


def test_public_recent_activity_selects_enabled_search_tool() -> None:
    tool = _tool("web_search")
    tool.skill_metadata = type("SkillMetadataStub", (), {"enabled": True})()

    decision = SkillRouter().route(
        "最近特朗普有啥活动",
        [tool, _tool("get_farm_status")],
    )

    assert decision.selected_tools == ["web_search"]
    assert decision.frames[0].intent == "query_web_search"


def test_public_recent_what_doing_selects_enabled_search_tool() -> None:
    tool = _tool("web_search")
    tool.skill_metadata = type("SkillMetadataStub", (), {"enabled": True})()

    decision = SkillRouter().route(
        "特朗普最近在干嘛",
        [tool, _tool("get_farm_status")],
    )

    assert decision.selected_tools == ["web_search"]
    assert decision.frames[0].intent == "query_web_search"


def test_public_recent_activity_keeps_search_rule_over_vector_noise() -> None:
    tool = _tool("web_search")
    tool.skill_metadata = type("SkillMetadataStub", (), {"enabled": True})()
    router = SkillRouter()

    def vector_search(_query: str, candidates) -> dict[str, float]:
        return {
            f"{candidate.name}.{candidate.operation}": (
                0.95 if candidate.name == "get_farm_status" else 0.2
            )
            for candidate in candidates
        }

    router._hybrid_retriever = HybridOperationRetriever(vector_search=vector_search)

    decision = router.route(
        "最近特朗普有啥活动",
        [tool, _tool("get_farm_status")],
    )

    assert decision.selected_tools == ["web_search"]
    assert decision.frames[0].intent == "query_web_search"


def test_public_recent_what_doing_keeps_search_rule_over_vector_noise() -> None:
    tool = _tool("web_search")
    tool.skill_metadata = type("SkillMetadataStub", (), {"enabled": True})()
    router = SkillRouter()

    def vector_search(_query: str, candidates) -> dict[str, float]:
        return {
            f"{candidate.name}.{candidate.operation}": (
                0.95 if candidate.name == "manage_farm_logs" else 0.2
            )
            for candidate in candidates
        }

    router._hybrid_retriever = HybridOperationRetriever(vector_search=vector_search)

    decision = router.route(
        "特朗普最近在干嘛",
        [tool, _tool("manage_farm_logs"), _tool("get_farm_status")],
    )

    assert decision.selected_tools == ["web_search"]
    assert decision.frames[0].intent == "query_web_search"


def test_web_search_candidate_preserved_after_recall() -> None:
    """BM25+向量召回的 web_search 候选不再被关键词规则二次过滤.

    依据: docs/specs/2026-07-31-agent-harness-design.md 阶段 0 + openspec
    change `remove-web-search-rule-special-case`. Layer 1 召回结果应直接进入
    Layer 3 LLM 自选, 不得在 policy/service 层用关键词规则踢出 web_search.
    """
    router = SkillRouter()

    def vector_search(_query: str, candidates) -> dict[str, float]:
        return {
            f"{candidate.name}.{candidate.operation}": (
                0.97 if candidate.name == "web_search" else 0.18
            )
            for candidate in candidates
        }

    router._hybrid_retriever = HybridOperationRetriever(vector_search=vector_search)

    decision = router.route(
        "这个工人最近在干嘛",
        [_tool("web_search"), _tool("manage_workers"), _tool("weather")],
    )

    assert "web_search" in decision.selected_tools


def test_farm_blocker_with_external_price_intent_keeps_web_search() -> None:
    """boundary case: 含'农场'blocker 但意图是外部价格的输入, web_search 应保留.

    依据: router_c_spike.py 实证 farm_blocker case. 旧关键词规则会因'农场'
    blocker 踢出 web_search, 但用户真实意图是问外部价格. 删特判后 web_search
    保留, 由 LLM 自决.
    """
    decision = SkillRouter().route(
        "我农场的西瓜今天价格",
        [_tool("web_search"), _tool("get_farm_status")],
    )

    assert "web_search" in decision.selected_tools


def test_disabled_web_search_is_rejected_without_selection() -> None:
    tool = _tool("web_search")
    tool.skill_metadata = type("SkillMetadataStub", (), {"enabled": False})()

    decision = SkillRouter().route(
        "搜索一下天气新闻",
        [tool, _tool("get_farm_status")],
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
    tool.name = "weather"

    catalog = SkillCatalog.from_tools([tool])

    candidate = catalog.get("weather")
    assert candidate is not None
    assert candidate.schema_token_estimate >= 80


@pytest.mark.parametrize(
    "message",
    ["我的作物", "我家有哪些作物栽种", "当前种了哪些作物", "现在地里都种着什么"],
)
def test_crop_inventory_query_routes_to_crop_cycles(message: str) -> None:
    tools = [
        _tool("get_farm_status"),
        _tool("manage_crop_cycle"),
        _tool("manage_workers"),
        _tool("create_operation_work_order"),
    ]

    decision = SkillRouter().route(message, tools)

    assert len(decision.selected_tools) <= 2
    assert decision.selected_tools[0] == "manage_crop_cycle"
    assert set(decision.selected_tools) <= {"manage_crop_cycle", "get_farm_status"}
    assert decision.fallback != "fallback_all"
    assert "create_operation_work_order" not in decision.selected_tools


@pytest.mark.parametrize(
    ("message", "expected_tools"),
    [
        ("今日天气对作物有什么影响", ["weather", "get_farm_status"]),
        ("今天适合给作物打药吗", ["weather", "get_farm_status"]),
    ],
)
def test_crop_inventory_rule_does_not_capture_advice_or_overview(
    message: str, expected_tools: list[str]
) -> None:
    tools = [
        _tool("weather"),
        _tool("get_farm_status"),
        _tool("manage_crop_cycle"),
    ]

    decision = SkillRouter().route(message, tools)

    assert decision.selected_tools == expected_tools


@pytest.mark.parametrize("message", ["你好", "nihao", "ni hao"])
def test_greeting_binds_no_tools(message: str) -> None:
    tools = [_tool("get_farm_status"), _tool("create_cost_record")]

    decision = SkillRouter().route(message, tools)

    assert decision.selected_tools == []
    assert decision.fallback == "no_tools"


def test_unknown_farm_read_uses_naive_fulltool_injection() -> None:
    """朴素模式下,未命中规则但属于业务读意图,全量注入所有 read skill 给 LLM 自选。

    详见 docs/specs/2026-07-31-agent-harness-design.md §5.0。
    """
    tools = [
        _tool("get_farm_status"),
        _tool("manage_crop_cycle"),
    ]

    decision = SkillRouter().route("农场最近怎么样", tools)

    # manage_crop_cycle 是 write_confirm,不进 read pool;但 catalog 把它标 read
    # 朴素模式注入所有 risk=read 的 skill
    assert decision.selected_tools == ["get_farm_status", "manage_crop_cycle"]
    assert decision.fallback == "model_choice_read_default"
    assert decision.fallback_reason == "naive_fulltool_injection"
    assert decision.frames[0].intent == "naive_fulltool_read"


def test_retry_control_word_routes_to_fulltool_injection_in_naive_mode() -> None:
    """朴素模式下,"重试"等上下文短输入不再走 no_tools,而是全量注入让 LLM 看 chat history 自选。

    修复缺陷 #8:召回模式对上下文短输入彻底失效(query 无 hint,召回空 → LLM 看不到任何工具)。
    朴素模式:LLM bind_tools 全量 skill,基于 chat history 自行判断是否重放上轮调用。
    """
    decision = SkillRouter().route(
        "重试",
        [_tool("get_farm_status"), _tool("manage_cost"), _tool("manage_crop_cycle")],
    )

    # 重试不识别为寒暄(任务约束 #7),走全量注入
    assert decision.fallback == "model_choice_read_default"
    assert decision.fallback_reason == "naive_fulltool_injection"
    # 所有 read skill 都暴露给 LLM
    assert "get_farm_status" in decision.selected_tools
    assert "manage_crop_cycle" in decision.selected_tools


@pytest.mark.parametrize("message", ["明天苏州什么天气", "今天天气", "明天会下雨吗"])
def test_weather_query_selects_weather_tool(message: str) -> None:
    tools = [_tool("weather"), _tool("get_farm_status")]

    decision = SkillRouter().route(message, tools)

    assert decision.selected_tools == ["weather"]
    assert decision.frames[0].intent == "query_weather"


def test_temperature_sensor_question_does_not_select_weather_tool() -> None:
    tools = [_tool("weather"), _tool("get_farm_status")]

    decision = SkillRouter().route("温度传感器怎么安装", tools)

    assert decision.selected_tools == []


@pytest.mark.parametrize(
    "message", ["西瓜怎么种", "怎么种小麦"]
)
def test_planting_advice_tutorial_prefix_routes_to_chitchat(message: str) -> None:
    """朴素模式下,"X怎么种" 走 ChitchatClassifier 短路(fallback no_tools)。

    "怎么" 是教程类问句开头,ChitchatClassifier 识别为非业务,直接走兜底分支,
    跳过 LLM 工具调用。详见 chitchat.py 与 spec.md "寒暄仍走兜底分支"。
    """
    tools = [_tool("get_farm_status"), _tool("manage_crop_cycle")]

    decision = SkillRouter().route(message, tools)

    assert decision.selected_tools == []
    assert decision.fallback == "no_tools"
    assert decision.fallback_reason == "chitchat_short_circuit"


def test_planting_advice_business_query_routes_to_fulltool_injection() -> None:
    """朴素模式下,"种小麦要注意什么" 不含教程词,RuleIntentClassifier 仍能识别为
    query_planting_advice 走精确 frame 路径(朴素模式保留 RuleIntentClassifier 仅做
    写意图识别,read frame 在 RouterPolicy 内被 read/write mismatch reject 后落
    全量注入,但本例 frame.candidate_tools[0]=get_farm_status 是 read tool,
    不会被 mismatch reject)。
    """
    tools = [_tool("get_farm_status"), _tool("manage_crop_cycle")]

    decision = SkillRouter().route("种小麦要注意什么", tools)

    # RuleIntentClassifier 识别为 query_planting_advice frame,
    # candidate_tools=["get_farm_status"] (read tool),被 policy 选中
    assert decision.selected_tools == ["get_farm_status"]
    assert decision.frames[0].intent == "query_planting_advice"


@pytest.mark.parametrize(
    "message",
    ["今天适合做什么", "今天适合做啥", "今天适合打药吗"],
)
def test_daily_operation_advice_binds_weather_and_farm_status(message: str) -> None:
    tools = [_tool("weather"), _tool("get_farm_status")]

    decision = SkillRouter().route(message, tools)

    assert decision.selected_tools == ["weather", "get_farm_status"]
    assert decision.frames[0].intent == "query_daily_operation_advice"
    assert decision.frames[0].risk == "read"


def test_english_money_query_binds_finance_read_tools() -> None:
    tools = [_tool("get_cost_summary"), _tool("get_debt_summary")]

    decision = SkillRouter().route("money", tools)

    assert decision.selected_tools == ["get_cost_summary", "get_debt_summary"]
    assert decision.frames[0].intent == "query_finance_overview"
    assert decision.frames[0].risk == "read"


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
        _tool("manage_labor_payment"),
        _tool("manage_workers"),
    ]

    decision = SkillRouter().route("李海这个月干了15天压瓜", tools)

    assert decision.fallback != "no_tools"
    assert "create_operation_work_order" in decision.selected_tools
    assert "manage_labor_payment" not in decision.selected_tools
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


def test_attendance_sentence_routes_to_labor_payment_wage_record() -> None:
    decision = SkillRouter().route(
        "张三今天来了一天",
        [_tool("manage_farm_logs"), _tool("manage_labor_payment")],
    )

    assert decision.selected_tools == ["manage_labor_payment"]
    assert decision.selected_operations == {"manage_labor_payment": ["manage_wage"]}
    assert decision.frames[0].params_hint == {
        "operation": "manage_wage",
        "action": "save",
        "worker_name": "张三",
        "quantity": 1,
        "pay_type": "daily",
    }


def test_worker_operation_with_daily_price_routes_to_labor_wage_record() -> None:
    decision = SkillRouter().route(
        "张三今天打药一天180",
        [_tool("manage_farm_logs"), _tool("manage_labor_payment")],
    )

    assert decision.selected_tools == ["manage_labor_payment"]
    assert decision.selected_operations == {"manage_labor_payment": ["manage_wage"]}
    assert decision.frames[0].params_hint == {
        "operation": "manage_wage",
        "action": "save",
        "worker_name": "张三",
        "operation_type": "打药",
        "quantity": 1,
        "pay_type": "daily",
        "unit_price": 180,
    }


def test_implicit_labor_without_operation_asks_clarification() -> None:
    tools = [
        _tool("create_operation_work_order"),
        _tool("manage_labor_payment"),
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
        _tool("manage_labor_payment"),
        _tool("manage_workers"),
    ]

    decision = SkillRouter().route("今天李海去6号棚压蔓工资100一天", tools)

    assert decision.selected_tools == ["create_operation_work_order"]
    assert "manage_labor_payment" not in decision.selected_tools
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
        ("你好", [_tool("create_operation_work_order"), _tool("manage_labor_payment")]),
        (
            "李海最近挺忙的",
            [_tool("create_operation_work_order"), _tool("manage_labor_payment")],
        ),
        (
            "老王还欠多少人工钱",
            [_tool("create_operation_work_order"), _tool("manage_labor_payment")],
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
        assert decision.selected_tools == ["manage_labor_payment"]


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
        ("我的茬口有哪些", "manage_crop_cycle", "manage_crop_cycle", "query_cycles"),
        ("我的工人有哪些", "manage_workers", "manage_workers", "query_workers"),
        (
            "我的作业单有哪些",
            "get_operation_work_orders",
            "manage_work_orders",
            "query_work_orders",
        ),
        (
            "还欠多少人工钱",
            "manage_labor_payment",
            "manage_labor_payment",
            "query_payables",
        ),
        (
            "我的默认天气城市是什么",
            "manage_user_settings",
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


def test_expense_query_routes_to_manage_cost_when_crop_cycle_is_available() -> None:
    decision = SkillRouter().route(
        "我的花费多少",
        [_tool("manage_cost"), _tool("manage_crop_cycle"), _tool("get_farm_status")],
    )

    assert decision.selected_tools == ["manage_cost"]
    assert decision.selected_operations == {"manage_cost": ["query_summary"]}
    assert decision.frames[0].operation == "query_summary"


def test_rule_route_trace_explains_vector_recall_was_skipped() -> None:
    decision = SkillRouter().route(
        "明天天气怎么样？",
        [_tool("weather"), _tool("get_farm_status")],
    )

    payload = decision.to_trace_payload()
    recall = payload["evidence"]["recall"]
    explanations = payload["evidence"]["candidate_explanations"]

    assert recall["path"] == "rule_classifier"
    assert recall["retrieval_engine"] == "rule_intent_classifier"
    assert recall["bm25_used"] is False
    assert recall["vector_search_used"] is False
    assert recall["rag_service_used"] is False
    assert recall["external_embedding_requested"] is False
    assert recall["embedding_location"] == "none"
    assert recall["skip_reason"] == "rule_classifier_matched"
    assert explanations[0]["route"] == "weather.query_forecast"
    assert explanations[0]["selected"] is True
    assert explanations[0]["scores"]["operation"] >= 0.85


def test_rule_routing_logs_classification_and_router_mode(caplog) -> None:
    """朴素模式下,classification_completed event 携带 router_mode=naive_fulltool_injection。

    朴素模式不再触发 vector_recall_skipped event(那是 legacy 召回路径专属)。
    """
    tools = [_tool("manage_crop_cycle"), _tool("get_farm_status")]

    with caplog.at_level(logging.INFO, logger="app.agent.router.service"):
        SkillRouter().route("我现在有哪些进行中的茬口？", tools)

    messages = [record.getMessage() for record in caplog.records]
    assert any(
        "event=skill_router_classification_completed" in message
        and "frame_count=" in message
        and "query_active_crops" in message
        and "router_mode=naive_fulltool_injection" in message
        for message in messages
    ), f"missing classification_completed with router_mode, got: {messages}"
    # 朴素模式不应触发 vector_recall_skipped(那是 legacy 召回专属 event)
    assert not any(
        "event=skill_router_vector_recall_skipped" in message for message in messages
    ), f"naive mode should not emit vector_recall_skipped, got: {messages}"


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
        [_tool("manage_user_settings")],
    )

    assert decision.selected_tools == ["manage_user_settings"]
    assert decision.selected_operations == {"manage_settings": ["query_settings"]}
    assert decision.frames[0].risk == "read"


@pytest.mark.parametrize(
    "message",
    [
        "把默认天气城市改成苏州",
        "设置默认天气城市为苏州",
        "修改城市为睢宁",
        "城市改为睢宁",
        "修改助手回复角色",
        "设置默认经纬度为31.2,120.6",
        "把默认经纬度改成31.2,120.6",
    ],
)
def test_settings_update_uses_write_confirm_operation(message: str) -> None:
    decision = SkillRouter().route(
        message,
        [_tool("manage_user_settings")],
    )

    assert decision.selected_tools == ["manage_user_settings"]
    assert decision.selected_operations == {"manage_settings": ["update_settings"]}
    assert decision.frames[0].risk == "write_confirm"
    assert decision.frames[0].requires_confirmation is True


@pytest.mark.parametrize(
    "message",
    [
        "修改城市为睢宁",
        "城市改为睢宁",
    ],
)
def test_bare_city_update_prefers_settings_over_crop_cycle(message: str) -> None:
    decision = SkillRouter().route(
        message,
        [_tool("manage_user_settings"), _tool("manage_crop_cycle")],
    )

    assert decision.selected_tools == ["manage_user_settings"]
    assert decision.selected_operations == {"manage_settings": ["update_settings"]}
    assert decision.frames[0].risk == "write_confirm"


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
def test_worker_read_query_uses_read_operation(message: str) -> None:
    decision = SkillRouter().route(
        message,
        [_tool("manage_workers")],
    )

    assert decision.selected_tools == ["manage_workers"]
    assert decision.selected_operations == {"manage_workers": ["query_workers"]}
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
        [_tool("manage_workers")],
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
        [_tool("manage_planting_units")],
    )

    assert decision.selected_tools == ["manage_planting_units"]
    assert decision.selected_operations == {"manage_planting_units": ["query_units"]}
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
        [_tool("manage_planting_units")],
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
        [_tool("manage_planting_units")],
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
        [_tool("manage_cost_categories")],
    )

    assert decision.selected_tools == ["manage_cost_categories"]
    assert decision.selected_operations == {
        "manage_cost_categories": ["query_categories"]
    }
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
        [_tool("manage_cost_categories")],
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
        [_tool("manage_cost_categories")],
    )

    assert decision.selected_tools == []
    assert decision.clarification is not None
    assert "请补充" in decision.clarification
