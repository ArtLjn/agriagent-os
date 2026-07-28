"""Operation 级混合候选召回测试。"""

import logging
from dataclasses import replace
from unittest.mock import MagicMock

import pytest

from app.agent.router.catalog import SkillCatalog
from app.agent.router.hybrid_retriever import (
    HybridOperationRetriever,
    HybridScoringWeights,
)
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
    assert "lexical" in result.evidence["manage_cost.query_debt"]["sources"]


def test_hybrid_retriever_penalizes_candidates_that_only_match_low_signal_terms() -> None:
    candidates = _operation_candidates(
        ["manage_cost", "manage_cost_categories", "manage_workers"]
    )

    result = HybridOperationRetriever().retrieve("我有哪些欠款", candidates, limit=5)

    debt_score = result.evidence["manage_cost.query_debt"]["score"]
    worker_score = result.evidence["manage_workers.query_workers"]["score"]
    category_score = result.evidence.get(
        "manage_cost_categories.query_categories",
        {"score": 0.0},
    )["score"]
    assert debt_score > worker_score
    assert debt_score > category_score


def test_hybrid_retriever_routes_expense_query_to_cost_summary() -> None:
    candidates = _operation_candidates(
        [
            "get_farm_status",
            "manage_cost",
            "manage_crop_cycle",
            "manage_planting_units",
            "manage_workers",
        ]
    )

    result = HybridOperationRetriever().retrieve("我的花费多少", candidates, limit=5)

    top_routes = [
        f"{candidate.name}.{candidate.operation}"
        for candidate in result.selected_candidates
    ]
    assert top_routes[:1] == ["manage_cost.query_summary"]
    assert "manage_cost.query_summary" in result.evidence


def test_hybrid_retriever_uses_vector_source_when_available() -> None:
    candidates = [
        replace(
            candidate,
            trigger_examples=[],
            entities=[],
            intents=[candidate.operation or "", candidate.name],
        )
        for candidate in _operation_candidates(["manage_cost", "manage_workers"])
    ]

    searched_queries: list[str] = []

    def vector_search(
        query_text: str,
        search_candidates,
    ) -> dict[str, float]:
        searched_queries.append(query_text)
        return {
            f"{candidate.name}.{candidate.operation}": (
                0.98 if candidate.operation == "query_debt" else 0.2
            )
            for candidate in search_candidates
        }

    result = HybridOperationRetriever(
        vector_search=vector_search,
    ).retrieve(
        "我有哪些欠款",
        candidates,
        limit=3,
    )

    top_routes = [
        f"{candidate.name}.{candidate.operation}"
        for candidate in result.selected_candidates
    ]
    assert searched_queries == ["我有哪些欠款"]
    assert top_routes[:1] == ["manage_cost.query_debt"]
    assert "vector" in result.evidence["manage_cost.query_debt"]["sources"]
    assert result.recall["path"] == "bm25_vector_hybrid"
    assert result.recall["vector_search_used"] is True
    assert result.recall["quillrag_retrieve_used"] is True
    assert result.recall["external_embedding_requested"] is True
    assert result.recall["local_doc_embedding_calls"] == 0
    assert result.top_candidates[0]["route"] == "manage_cost.query_debt"
    assert result.top_candidates[0]["vector"] == 0.98
    assert "bm25" in result.top_candidates[0]


def test_vector_score_has_priority_over_bm25_pollution() -> None:
    candidates = [
        replace(
            candidate,
            trigger_examples=[],
            entities=[],
            intents=[candidate.operation or "", candidate.name],
        )
        for candidate in _operation_candidates(["manage_cost", "manage_workers"])
    ]

    def vector_search(_query_text: str, search_candidates) -> dict[str, float]:
        return {
            f"{candidate.name}.{candidate.operation}": (
                0.95 if candidate.operation == "query_debt" else 0.05
            )
            for candidate in search_candidates
        }

    result = HybridOperationRetriever(vector_search=vector_search).retrieve(
        "工人欠款",
        candidates,
        limit=5,
    )

    top_routes = [
        f"{candidate.name}.{candidate.operation}"
        for candidate in result.selected_candidates
    ]
    assert top_routes[0] == "manage_cost.query_debt"
    assert result.evidence["manage_cost.query_debt"]["vector"] == 0.95


def test_vector_first_weights_win_semantic_log_query_over_bm25_pollution() -> None:
    candidates = []
    for candidate in _operation_candidates(["manage_farm_logs", "manage_work_orders"]):
        if candidate.operation not in {"query_logs", "query_work_orders"}:
            continue
        candidates.append(
            replace(
                candidate,
                trigger_examples=["我干了啥"]
                if candidate.operation == "query_work_orders"
                else [],
                entities=[],
                intents=[],
                anti_examples=[],
            )
        )

    def vector_search(_query_text: str, search_candidates) -> dict[str, float]:
        return {
            f"{candidate.name}.{candidate.operation}": (
                0.99 if candidate.operation == "query_logs" else 0.0
            )
            for candidate in search_candidates
        }

    bm25_heavy = HybridOperationRetriever(
        vector_search=vector_search,
        weights=HybridScoringWeights(
            bm25=0.45,
            vector=0.25,
            lexical=0.20,
            registry_prior=0.10,
        ),
    ).retrieve("我干了啥", candidates, limit=2)
    vector_first = HybridOperationRetriever(
        vector_search=vector_search,
    ).retrieve("我干了啥", candidates, limit=2)

    assert bm25_heavy.top_candidates[0]["route"] == (
        "manage_work_orders.query_work_orders"
    )
    assert vector_first.top_candidates[0]["route"] == "manage_farm_logs.query_logs"
    assert vector_first.top_candidates[0]["vector"] == 0.99
    assert vector_first.recall["scoring_formula"].startswith("0.15*bm25 + 0.70*vector")


def test_semantic_log_query_operation_prior_does_not_suppress_vector_hit() -> None:
    candidates = [
        candidate
        for candidate in _operation_candidates(
            [
                "manage_cost",
                "manage_crop_cycle",
                "manage_farm_logs",
                "manage_work_orders",
                "manage_workers",
            ]
        )
        if candidate.operation
        in {
            "query_summary",
            "query_cycles",
            "query_logs",
            "query_work_orders",
            "query_workers",
        }
    ]
    vector_scores = {
        "manage_cost.query_summary": 0.7985,
        "manage_crop_cycle.query_cycles": 0.7798,
        "manage_work_orders.query_work_orders": 0.6021,
        "manage_farm_logs.query_logs": 0.8000,
        "manage_workers.query_workers": 0.4591,
    }

    result = HybridOperationRetriever(
        vector_search=lambda _query, _candidates: vector_scores,
    ).retrieve("我干了啥", candidates, limit=5)

    assert result.top_candidates[0]["route"] == "manage_farm_logs.query_logs"
    assert result.evidence["manage_farm_logs.query_logs"]["vector"] == 0.8


def test_labor_wage_record_prior_overrides_settlement_vector_noise() -> None:
    candidates = [
        candidate
        for candidate in _operation_candidates(
            ["manage_labor_payment", "manage_farm_logs", "manage_cost"]
        )
        if candidate.operation
        in {
            "manage_wage",
            "settle_payment",
            "create_log",
            "create_record",
        }
    ]
    vector_scores = {
        "manage_labor_payment.settle_payment": 0.9124,
        "manage_farm_logs.create_log": 0.7623,
        "manage_cost.create_record": 0.7000,
    }

    result = HybridOperationRetriever(
        vector_search=lambda _query, _candidates: vector_scores,
    ).retrieve("张三今天打药一天180", candidates, limit=5)

    assert result.top_candidates[0]["route"] == "manage_labor_payment.manage_wage"
    assert result.evidence["manage_labor_payment.manage_wage"]["operation_prior"] > 0
    assert result.evidence["manage_labor_payment.settle_payment"][
        "operation_prior"
    ] < 0


def test_hybrid_retriever_never_calls_vector_search_without_index(caplog) -> None:
    candidates = _operation_candidates(["manage_cost", "manage_workers"])

    with caplog.at_level(logging.INFO, logger="app.agent.router.hybrid_retriever"):
        result = HybridOperationRetriever().retrieve(
            "我有哪些欠款",
            candidates,
            limit=3,
        )

    assert result.selected_candidates
    assert result.recall["vector_index_enabled"] is False
    assert result.recall["vector_search_used"] is False
    assert result.recall["external_embedding_requested"] is False
    messages = [record.getMessage() for record in caplog.records]
    assert any(
        "event=skill_router_vector_recall_completed" in message
        and "status=missing_index" in message
        and "local_query_embedding_calls=0" in message
        and "local_doc_embedding_calls=0" in message
        for message in messages
    )


def test_hybrid_retriever_logs_missing_vector_index_reason(caplog) -> None:
    candidates = _operation_candidates(["manage_cost", "manage_workers"])

    with caplog.at_level(logging.INFO, logger="app.agent.router.hybrid_retriever"):
        HybridOperationRetriever().retrieve("我有哪些欠款", candidates)

    messages = [record.getMessage() for record in caplog.records]
    assert any(
        "event=skill_router_vector_recall_completed" in message
        and "status=missing_index" in message
        and "candidate_count=" in message
        for message in messages
    )


def test_hybrid_retriever_logs_vector_recall_lifecycle(caplog) -> None:
    candidates = [
        replace(
            candidate,
            trigger_examples=[],
            entities=[],
            intents=[candidate.operation or "", candidate.name],
        )
        for candidate in _operation_candidates(["manage_cost", "manage_workers"])
    ]

    searched_queries: list[str] = []

    def vector_search(
        query_text: str,
        search_candidates,
    ) -> dict[str, float]:
        searched_queries.append(query_text)
        return {
            f"{candidate.name}.{candidate.operation}": (
                0.95 if candidate.operation == "query_debt" else 0.1
            )
            for candidate in search_candidates
        }

    with caplog.at_level(logging.INFO, logger="app.agent.router.hybrid_retriever"):
        HybridOperationRetriever(
            vector_search=vector_search,
        ).retrieve("我有哪些欠款", candidates)

    assert searched_queries == ["我有哪些欠款"]
    messages = [record.getMessage() for record in caplog.records]
    assert any(
        "event=skill_router_vector_recall_completed" in message
        and "status=success" in message
        and "candidate_count=" in message
        and "local_query_embedding_calls=0" in message
        and "local_doc_embedding_calls=0" in message
        and "vector_search_calls=1" in message
        for message in messages
    )
    candidate_summary = next(
        message
        for message in messages
        if "event=skill_router_candidate_scores" in message
    )
    assert "top_routes=" in candidate_summary
    assert "top_candidates=" not in candidate_summary
    assert any(
        "event=skill_router_candidate_scores_detail\nSkill Router Candidate Scores"
        in message
        and "manage_cost.query_debt" in message
        and "bm25=" in message
        and "vector=" in message
        for message in messages
    )
