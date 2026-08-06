"""Registry 驱动候选召回测试。"""

from unittest.mock import MagicMock

import pytest

from app.agent.router.candidate_retriever import CandidateRetriever
from app.agent.router.catalog import SkillCatalog

pytestmark = pytest.mark.no_db


def _tool(name: str):
    tool = MagicMock()
    tool.name = name
    tool.description = ""
    return tool


def _catalog(names: list[str]) -> SkillCatalog:
    return SkillCatalog.from_tools([_tool(name) for name in names])


def test_retriever_routes_english_unpaid_wages_to_labor_payment() -> None:
    catalog = _catalog(["manage_cost", "manage_labor_payment", "manage_workers"])

    result = CandidateRetriever().retrieve(
        "how much unpaid worker wages remain",
        catalog.candidates(),
    )

    assert result.selected_names[:1] == ["manage_labor_payment"]
    assert result.scores["manage_labor_payment"] > result.scores["manage_cost"]
    assert result.scores["manage_labor_payment"] > result.scores["manage_workers"]


def test_retriever_uses_anti_examples_to_avoid_worker_profile_for_wages() -> None:
    catalog = _catalog(["manage_labor_payment", "manage_workers"])

    result = CandidateRetriever().retrieve("我说的是工人工资", catalog.candidates())

    assert result.selected_names[:1] == ["manage_labor_payment"]
    assert "manage_workers" not in result.selected_names[:1]


def test_retriever_returns_no_candidate_for_greeting() -> None:
    catalog = _catalog(["manage_cost", "manage_crop_cycle"])

    result = CandidateRetriever().retrieve("hello", catalog.candidates())

    assert result.selected_names == []
