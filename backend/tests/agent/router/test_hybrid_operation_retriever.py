"""Operation 级混合候选召回测试。"""

import logging
from dataclasses import replace
from unittest.mock import MagicMock

import pytest

from app.agent.router.catalog import SkillCatalog
from app.agent.router.hybrid_retriever import HybridOperationRetriever
from app.ops.skill_route_eval import _expand_candidate_operations

pytestmark = pytest.mark.no_db


def _tool(name: str):
    tool = MagicMock()
    tool.name = name
    tool.description = name
    return tool


def _operation_candidates(names: list[str]):
    catalog = SkillCatalog.from_tools([_tool(name) for name in names])
    candidates = []
    for candidate in catalog.candidates():
        candidates.extend(_expand_candidate_operations(candidate))
    return candidates


def test_hybrid_retriever_keeps_debt_operation_when_generic_query_terms_pollute_bm25() -> None:
    candidates = _operation_candidates(
        [
            "get_farm_status",
            "manage_cost",
            "manage_cost_categories",
            "manage_crop_cycle",
            "manage_crop_templates",
            "manage_planting_units",
            "manage_work_orders",
            "manage_workers",
        ]
    )

    result = HybridOperationRetriever().retrieve("我有哪些欠款", candidates, limit=5)

    top_routes = [
        f"{candidate.name}.{candidate.operation}"
        for candidate in result.selected_candidates
    ]
    assert top_routes[:1] == ["manage_cost.query_debt"]
    assert "manage_cost.query_debt" in top_routes
    assert "strong_rule" in result.evidence["manage_cost.query_debt"]["sources"]


def test_hybrid_retriever_penalizes_candidates_that_only_match_low_signal_terms() -> None:
    candidates = _operation_candidates(
        ["manage_cost", "manage_cost_categories", "manage_workers"]
    )

    result = HybridOperationRetriever().retrieve("我有哪些欠款", candidates, limit=5)

    debt_score = result.evidence["manage_cost.query_debt"]["score"]
    worker_score = result.evidence["manage_workers.query_workers"]["score"]
    category_score = result.evidence[
        "manage_cost_categories.query_categories"
    ]["score"]
    assert debt_score > worker_score
    assert debt_score > category_score


def test_hybrid_retriever_uses_embedding_source_when_available() -> None:
    candidates = [
        replace(
            candidate,
            trigger_examples=[],
            entities=[],
            intents=[candidate.operation or "", candidate.name],
        )
        for candidate in _operation_candidates(["manage_cost", "manage_workers"])
    ]

    def embed(text: str) -> list[float]:
        if "欠款" in text or "赊账" in text or "query_debt" in text:
            return [1.0, 0.0]
        return [0.0, 1.0]

    result = HybridOperationRetriever(embed=embed).retrieve(
        "我有哪些欠款",
        candidates,
        limit=3,
    )

    top_routes = [
        f"{candidate.name}.{candidate.operation}"
        for candidate in result.selected_candidates
    ]
    assert top_routes[:1] == ["manage_cost.query_debt"]
    assert "embedding" in result.evidence["manage_cost.query_debt"]["sources"]


def test_hybrid_retriever_logs_embedding_recall_lifecycle(caplog) -> None:
    candidates = [
        replace(
            candidate,
            trigger_examples=[],
            entities=[],
            intents=[candidate.operation or "", candidate.name],
        )
        for candidate in _operation_candidates(["manage_cost", "manage_workers"])
    ]

    def embed(text: str) -> list[float]:
        if "欠款" in text or "query_debt" in text:
            return [1.0, 0.0]
        return [0.0, 1.0]

    with caplog.at_level(logging.INFO, logger="app.agent.router.hybrid_retriever"):
        HybridOperationRetriever(embed=embed).retrieve("我有哪些欠款", candidates)

    messages = [record.getMessage() for record in caplog.records]
    assert any(
        "event=skill_router_embedding_recall_completed" in message
        and "status=success" in message
        and "candidate_count=" in message
        and "doc_embedding_calls=" in message
        for message in messages
    )
