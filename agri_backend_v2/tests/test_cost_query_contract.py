"""财务汇总分类键到 MCP 明细查询的契约与租户隔离回归。"""

from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from farm_business.models import CostRecord
from farm_business.services import cost_service
from farm_business.tools import cost


@pytest.fixture
def cost_db(monkeypatch):
    engine = create_engine("sqlite://")
    CostRecord.__table__.create(engine)
    sessions = sessionmaker(bind=engine)
    with sessions.begin() as db:
        db.add_all(
            [
                CostRecord(
                    farm_id=farm,
                    record_type=kind,
                    category=category,
                    amount=Decimal(amount),
                    record_date=date(2026, 10, 20),
                )
                for farm, kind, category, amount in [
                    (1, "cost", "化肥", "900"),
                    (1, "income", "化肥", "100"),
                    (2, "cost", "化肥", "888"),
                    (1, "cost", "其他:运费", "20"),
                ]
            ]
        )
    monkeypatch.setattr(cost, "session_scope", sessions.begin)
    monkeypatch.setattr(
        cost, "require_farm_operation_permission", lambda *a, **kw: {"farm_id": 1}
    )
    yield sessions
    engine.dispose()


def test_summary_key_round_trips_to_matching_tenant_and_record_type(cost_db):
    with cost_db() as db:
        summary = cost_service.get_yearly_summary(db, farm_id=1, year=2026)
    assert summary["by_category"]["cost:化肥"] == 900
    result = cost.manage_cost(operation="query", category="cost:化肥")
    assert result["count"] == 1
    assert result["records"][0]["amount"] == 900
    assert result["records"][0]["record_type"] == "cost"
    assert result["records"][0]["category"] == "化肥"


def test_plain_category_and_explicit_record_type_preserve_scope(cost_db):
    assert cost.manage_cost(operation="query", category="化肥")["count"] == 2
    result = cost.manage_cost(
        operation="query", category="化肥", record_type="income", limit=1
    )
    assert [row["amount"] for row in result["records"]] == [100]
    assert (
        cost.manage_cost(
            operation="query", category="化肥", record_type="income", skip=1
        )["records"]
        == []
    )
    assert cost.manage_cost(operation="query", category="其他:运费")["count"] == 1


def test_conflicting_summary_key_returns_actionable_error(cost_db):
    result = cost.manage_cost(
        operation="query", category="cost:化肥", record_type="income"
    )
    assert result["code"] == "category_record_type_conflict"
    assert "records" not in result
