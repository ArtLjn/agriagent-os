"""朴素全量注入模式集成测试。

对应 spec.md:
- Requirement: 全量 Skill 注入与 LLM 自选
- Scenario: 全量 read skill 注入 LLM
- Scenario: 上下文短输入走全量注入
- Scenario: 写操作仍走风险门禁
- Scenario: 寒暄仍走兜底分支
- Scenario: schema token 硬上限保护
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from app.agent.router.service import SkillRouter

pytestmark = pytest.mark.no_db


@pytest.fixture(autouse=True)
def _disable_external_vector_search_by_default(monkeypatch) -> None:
    """朴素模式默认不调外部向量服务。"""
    monkeypatch.setattr(
        "app.agent.router.service.build_skill_vector_search_fn",
        lambda: None,
    )


def _tool(name: str, description: str = "", risk: str = "read"):
    """构造 mock tool,默认 read risk。

    catalog 会根据 skill registry 元数据覆盖 risk,但单元测试场景下
    没有 registry,catalog 默认把工具标 read。
    """
    tool = MagicMock()
    tool.name = name
    tool.description = description
    return tool


def test_fulltool_injection_exposes_all_read_skills() -> None:
    """spec.md Scenario: 全量 read skill 注入 LLM。

    模糊业务查询(无明确 frame)走全量注入,所有 read skill 全部进入 bind_tools。
    """
    tools = [
        _tool("get_cost_summary"),
        _tool("get_debt_summary"),
        _tool("get_farm_status"),
        _tool("weather"),
    ]

    decision = SkillRouter(legacy_recall_mode=False).route(
        "看一下农场情况", tools
    )

    # 所有 read skill 都注入(缺陷 #8 的修复:不因召回预过滤剔除)
    assert "get_cost_summary" in decision.selected_tools
    assert "get_debt_summary" in decision.selected_tools
    assert "get_farm_status" in decision.selected_tools
    assert "weather" in decision.selected_tools
    assert decision.fallback == "model_choice_read_default"
    assert decision.fallback_reason == "naive_fulltool_injection"


def test_context_short_input_still_exposes_web_search_and_all_read_tools() -> None:
    """spec.md Scenario: 上下文短输入走全量注入。

    用户上轮调用 web_search 后输入"重试",朴素模式下 LLM 仍能看到 web_search
    (以及其他通过门禁的 read skill),LLM 基于 chat history 自行判断是否重放。
    """
    tools = [
        _tool("web_search"),
        _tool("get_farm_status"),
        _tool("weather"),
        _tool("get_cost_summary"),
    ]

    decision = SkillRouter(legacy_recall_mode=False).route("重试一下", tools)

    # 重试不识别为寒暄(任务约束 #7),走全量注入
    assert decision.fallback == "model_choice_read_default"
    assert decision.fallback_reason == "naive_fulltool_injection"
    # web_search 必须仍在 bind_tools 里(缺陷 #8 的修复)
    assert "web_search" in decision.selected_tools
    assert "get_farm_status" in decision.selected_tools


def test_chitchat_short_circuits_to_no_tools() -> None:
    """spec.md Scenario: 寒暄仍走兜底分支。

    寒暄走 ChitchatClassifier 兜底分支,直接回复,不进入 LLM 工具调用流程。
    """
    tools = [_tool("get_farm_status"), _tool("web_search")]

    decision = SkillRouter(legacy_recall_mode=False).route("你好", tools)

    assert decision.selected_tools == []
    assert decision.fallback == "no_tools"
    assert decision.fallback_reason == "chitchat_short_circuit"


def test_write_intent_still_goes_through_write_gate() -> None:
    """spec.md Scenario: 写操作仍走风险门禁。

    写操作 message 走 RuleIntentClassifier 写意图识别 + RouterPolicy 写门禁。
    本变更 MUST NOT 影响写操作路径。
    """
    tools = [
        _tool("manage_workers"),
        _tool("create_operation_work_order"),
    ]

    decision = SkillRouter(legacy_recall_mode=False).route(
        "帮我处理一下这个工人的事情", tools
    )

    # RuleIntentClassifier 识别 ambiguous_write frame
    # RouterPolicy 走 _has_ambiguous_write 路径,返回 clarify_write_intent
    assert decision.selected_tools == []
    assert decision.clarification is not None
    assert "请补充" in decision.clarification


def test_schema_token_budget_logs_warning_when_exceeded(caplog) -> None:
    """spec.md Scenario: schema token 硬上限保护。

    通过门禁的 skill 总 schema token 超过 9000 时,记 warning 日志(不静默截断)。
    """
    # 构造一个 read tool,description 极大,模拟 schema token 超预算
    big_description = "x" * 50000  # 远超 schema_token_estimate 默认值
    tools = [_tool(f"read_{i}", description=big_description) for i in range(50)]

    import logging

    with caplog.at_level(logging.WARNING, logger="app.agent.router.policy"):
        decision = SkillRouter(legacy_recall_mode=False).route("查询经营数据", tools)

    # 朴素模式下仍全量注入(不静默截断),但记 warning
    assert decision.fallback == "model_choice_read_default"
    # 至少有一条 warning 提到 schema_token_budget
    warning_messages = [r.message for r in caplog.records if r.levelno == logging.WARNING]
    assert any(
        "schema_token_budget_exceeded_naive" in msg for msg in warning_messages
    ), f"expected schema_token_budget warning, got: {warning_messages}"


def test_naive_mode_does_not_call_hybrid_retriever(monkeypatch) -> None:
    """朴素模式不调 HybridOperationRetriever.retrieve。"""
    retriever_calls: list[tuple] = []

    real_skill_router = SkillRouter(legacy_recall_mode=False)

    def _spy_retrieve(self, *_args, **_kwargs):
        retriever_calls.append((_args, _kwargs))
        return MagicMock(selected_names=[], selected_candidates=[], scores={}, evidence={}, recall={}, top_candidates=[])

    monkeypatch.setattr(
        "app.agent.router.hybrid_retriever.HybridOperationRetriever.retrieve",
        _spy_retrieve,
    )
    # monkeypatch 不影响已实例化的 retriever,直接打 patch 到实例上
    monkeypatch.setattr(
        real_skill_router._hybrid_retriever, "retrieve", lambda *a, **kw: retriever_calls.append((a, kw)) or MagicMock()
    )

    real_skill_router.route("查询经营数据", [_tool("get_farm_status")])

    assert retriever_calls == [], "朴素模式不应该调用 HybridOperationRetriever.retrieve"
