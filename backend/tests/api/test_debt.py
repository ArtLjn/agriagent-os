"""债务管理 API 测试。"""

from datetime import date, timedelta
from decimal import Decimal

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


class TestCreateDebt:
    """测试创建赊账记录。"""

    def test_create_debt(self):
        """正常创建赊账记录。"""
        payload = {
            "record_type": "cost",
            "category": "化肥",
            "amount": "300",
            "record_date": date.today().isoformat(),
            "record_subtype": "赊账",
            "counterparty": "老张",
            "due_date": (date.today() + timedelta(days=30)).isoformat(),
        }

        resp = client.post("/debts", json=payload)

        assert resp.status_code == 200
        data = resp.json()
        assert data["record_subtype"] == "赊账"
        assert data["counterparty"] == "老张"
        assert Decimal(data["amount"]) == Decimal("300")

    def test_create_debt_missing_required_field(self):
        """缺少必填字段时返回 422。"""
        payload = {
            "record_type": "cost",
            "amount": "300",
            "record_date": date.today().isoformat(),
        }

        resp = client.post("/debts", json=payload)

        assert resp.status_code == 422


class TestListDebts:
    """测试查询赊账列表。"""

    def test_list_unsettled(self):
        """查询未结清赊账列表。"""
        resp = client.get("/debts")

        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert "total" in data
        assert "summary" in data

    def test_filter_by_counterparty(self):
        """按债权人筛选。"""
        resp = client.get("/debts?counterparty=老张")

        assert resp.status_code == 200

    def test_pagination(self):
        """分页参数生效。"""
        resp = client.get("/debts?page=1&size=10")

        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data["items"], list)


class TestSettleDebt:
    """测试结清赊账。"""

    def test_settle_full(self):
        """全额结清赊账。"""
        client.post(
            "/debts",
            json={
                "record_type": "cost",
                "category": "农药",
                "amount": "100",
                "record_date": date.today().isoformat(),
                "record_subtype": "赊账",
                "counterparty": "测试还款",
                "due_date": (date.today() + timedelta(days=15)).isoformat(),
            },
        )

        resp = client.post(
            "/debts/settle",
            json={
                "counterparty": "测试还款",
            },
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["category"] == "还款"
        assert Decimal(data["amount"]) == Decimal("100")

    def test_settle_partial(self):
        """部分还款。"""
        client.post(
            "/debts",
            json={
                "record_type": "cost",
                "category": "种子",
                "amount": "500",
                "record_date": date.today().isoformat(),
                "record_subtype": "赊账",
                "counterparty": "部分还款测试",
                "due_date": (date.today() + timedelta(days=15)).isoformat(),
            },
        )

        resp = client.post(
            "/debts/settle",
            json={
                "counterparty": "部分还款测试",
                "amount": "200",
            },
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["category"] == "还款"
        assert Decimal(data["amount"]) == Decimal("200")

    def test_settle_missing_counterparty(self):
        """缺少 counterparty 返回 400。"""
        resp = client.post("/debts/settle", json={})

        assert resp.status_code == 400
        assert "counterparty" in resp.json()["detail"]

    def test_settle_nonexistent_counterparty(self):
        """结清不存在的债权人返回 404。"""
        resp = client.post(
            "/debts/settle",
            json={
                "counterparty": "不存在的人",
            },
        )

        assert resp.status_code == 404
