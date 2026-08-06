"""legacy_recall_mode=true 回滚通道测试。

确保朴素模式部署后,生产发现回归可切 flag 回滚到原召回路径。
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from app.agent.router.service import SkillRouter

pytestmark = pytest.mark.no_db


def _tool(name: str, description: str = ""):
    tool = MagicMock()
    tool.name = name
    tool.description = description
    return tool


def test_legacy_recall_mode_routes_through_hybrid_retriever(monkeypatch) -> None:
    """legacy_recall_mode=true 时,走原 _route_legacy 路径(含 _resolve_retrieval_frames)。"""
    retriever_called: list[bool] = []

    def _spy_retrieve(*_args, **_kwargs):
        retriever_called.append(True)
        result = MagicMock()
        result.selected_names = []
        result.selected_candidates = []
        result.scores = {}
        result.evidence = {}
        result.recall = {}
        result.top_candidates = []
        return result

    router = SkillRouter(legacy_recall_mode=True)
    monkeypatch.setattr(router._hybrid_retriever, "retrieve", _spy_retrieve)

    router.route(
        "还有没结清的钱吗",
        [_tool("get_farm_status"), _tool("manage_cost"), _tool("manage_crop_cycle")],
    )

    # legacy 模式应调用 retriever
    assert retriever_called, "legacy_recall_mode=true 时应调用 HybridOperationRetriever.retrieve"


def test_naive_mode_skips_hybrid_retriever(monkeypatch) -> None:
    """legacy_recall_mode=false(默认)时,不调用 HybridOperationRetriever.retrieve。"""
    retriever_called: list[bool] = []

    def _spy_retrieve(*_args, **_kwargs):
        retriever_called.append(True)
        return MagicMock()

    router = SkillRouter(legacy_recall_mode=False)
    monkeypatch.setattr(router._hybrid_retriever, "retrieve", _spy_retrieve)

    router.route(
        "还有没结清的钱吗",
        [_tool("get_farm_status"), _tool("manage_cost"), _tool("manage_crop_cycle")],
    )

    assert not retriever_called, "朴素模式不应调用 HybridOperationRetriever.retrieve"


def test_legacy_mode_uses_trim_candidates_by_budget() -> None:
    """legacy_recall_mode=true 时,RouterPolicy 走原 trim_candidates_by_budget 预选。

    用小 max_tools_default=2 限制,验证 selected 只有 2 个(legacy 模式行为)。
    """
    from app.agent.router.models import DisclosureBudget
    from app.agent.router.policy import RouterPolicy

    def _candidate(name: str, risk: str = "read"):
        from app.agent.router.models import ToolCandidate

        return ToolCandidate(
            name=name,
            domain="test",
            intents=[],
            risk=risk,
            schema_token_estimate=100,
            score=0.5,
        )

    candidates = [_candidate(f"read_{i}") for i in range(4)]

    decision = RouterPolicy(
        DisclosureBudget(max_tools_default=2),
        legacy_recall_mode=True,
    ).apply(message="看一下经营数据", frames=[], candidates=candidates)

    # legacy 模式按 max_tools_default=2 截断
    assert decision.selected_tools == ["read_0", "read_1"]


def test_naive_mode_ignores_max_tools_default_for_full_injection() -> None:
    """legacy_recall_mode=false 时,忽略 max_tools_default 限制,全量注入 read skill。"""
    from app.agent.router.models import DisclosureBudget, ToolCandidate
    from app.agent.router.policy import RouterPolicy

    def _candidate(name: str, risk: str = "read"):
        return ToolCandidate(
            name=name,
            domain="test",
            intents=[],
            risk=risk,
            schema_token_estimate=100,
            score=0.5,
        )

    candidates = [_candidate(f"read_{i}") for i in range(4)]

    decision = RouterPolicy(
        DisclosureBudget(max_tools_default=2),
        legacy_recall_mode=False,
    ).apply(message="看一下经营数据", frames=[], candidates=candidates)

    # 朴素模式忽略 max_tools_default 限制
    assert decision.selected_tools == ["read_0", "read_1", "read_2", "read_3"]
    assert decision.fallback_reason == "naive_fulltool_injection"
