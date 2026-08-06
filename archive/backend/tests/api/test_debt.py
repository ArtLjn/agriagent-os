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
        assert Decimal(data["settled_amount"]) == Decimal("0")
        assert Decimal(data["unsettled_amount"]) == Decimal("300")
        assert data["settlement_status"] == "unsettled"

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
        assert data["category"] == "农药"
        assert Decimal(data["amount"]) == Decimal("100")
        assert Decimal(data["settled_amount"]) == Decimal("100")
        assert Decimal(data["unsettled_amount"]) == Decimal("0")
        assert data["settlement_status"] == "settled"
        assert data["settled_at"] is not None

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
        assert data["category"] == "种子"
        assert Decimal(data["amount"]) == Decimal("500")
        assert Decimal(data["settled_amount"]) == Decimal("200")
        assert Decimal(data["unsettled_amount"]) == Decimal("300")
        assert data["settlement_status"] == "partial"
        assert data["settled_at"] is None

    def test_settle_partial_twice_accumulates_settled_amount(self):
        """连续两次部分还款会累加原账单 settled_amount。"""
        created = client.post(
            "/debts",
            json={
                "record_type": "cost",
                "category": "种子",
                "amount": "500",
                "record_date": date.today().isoformat(),
                "record_subtype": "赊账",
                "counterparty": "连续部分还款测试",
                "due_date": (date.today() + timedelta(days=15)).isoformat(),
            },
        ).json()

        first = client.post(
            "/debts/settle",
            json={"counterparty": "连续部分还款测试", "amount": "100"},
        )
        second = client.post(
            "/debts/settle",
            json={"counterparty": "连续部分还款测试", "amount": "150"},
        )

        assert first.status_code == 200
        assert second.status_code == 200
        data = second.json()
        assert data["id"] == created["id"]
        assert Decimal(data["settled_amount"]) == Decimal("250")
        assert Decimal(data["unsettled_amount"]) == Decimal("250")
        assert data["settlement_status"] == "partial"

    def test_settle_debt_does_not_create_income_record(self):
        """还款只更新原赊账，不创建普通收入记录。"""
        client.post(
            "/debts",
            json={
                "record_type": "cost",
                "category": "农药",
                "amount": "80",
                "record_date": date.today().isoformat(),
                "record_subtype": "赊账",
                "counterparty": "不进收入测试",
                "due_date": (date.today() + timedelta(days=15)).isoformat(),
            },
        )

        resp = client.post(
            "/debts/settle",
            json={"counterparty": "不进收入测试", "amount": "80"},
        )
        records = client.get("/costs").json()["items"]

        assert resp.status_code == 200
        assert [
            item
            for item in records
            if item["record_type"] == "income" and item["category"] == "还款"
        ] == []

    def test_settle_legacy_note_not_persisted_or_child_record_created(self):
        """旧 payload 的 note 不写入原账单，也不创建还款子记录。"""
        created = client.post(
            "/debts",
            json={
                "record_type": "cost",
                "category": "农药",
                "amount": "120",
                "record_date": date.today().isoformat(),
                "record_subtype": "赊账",
                "counterparty": "旧备注兼容测试",
                "due_date": (date.today() + timedelta(days=15)).isoformat(),
                "note": "原始账单备注",
            },
        ).json()

        resp = client.post(
            "/debts/settle",
            json={
                "counterparty": "旧备注兼容测试",
                "amount": "50",
                "note": "旧还款备注",
            },
        )
        records = client.get("/costs").json()["items"]

        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == created["id"]
        assert data["note"] == "原始账单备注"
        assert [
            item
            for item in records
            if item["id"] != created["id"] and item["parent_record_id"] == created["id"]
        ] == []
        assert [
            item
            for item in records
            if item["record_type"] == "income" and item["category"] == "还款"
        ] == []

    def test_settle_receivable_income_updates_original_record(self):
        """收入未收款在收款时更新原收入账单，不新增收支记录。"""
        created = client.post(
            "/debts",
            json={
                "record_type": "income",
                "category": "销售",
                "amount": "200",
                "record_date": date.today().isoformat(),
                "record_subtype": "赊账",
                "counterparty": "收瓜商",
                "due_date": (date.today() + timedelta(days=15)).isoformat(),
            },
        ).json()

        resp = client.post(
            "/debts/settle",
            json={"counterparty": "收瓜商"},
        )
        records = client.get("/costs").json()["items"]

        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == created["id"]
        assert data["record_type"] == "income"
        assert data["category"] == "销售"
        assert Decimal(data["settled_amount"]) == Decimal("200")
        assert Decimal(data["unsettled_amount"]) == Decimal("0")
        assert data["settlement_status"] == "settled"
        assert [
            item
            for item in records
            if item["id"] != created["id"] and item["parent_record_id"] == created["id"]
        ] == []

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

    def test_settle_rejects_non_positive_amount(self):
        """结算金额小于等于 0 返回参数错误。"""
        client.post(
            "/debts",
            json={
                "record_type": "cost",
                "category": "农药",
                "amount": "100",
                "record_date": date.today().isoformat(),
                "record_subtype": "赊账",
                "counterparty": "非法金额测试",
                "due_date": (date.today() + timedelta(days=15)).isoformat(),
            },
        )

        resp = client.post(
            "/debts/settle",
            json={
                "counterparty": "非法金额测试",
                "amount": "0",
            },
        )

        assert resp.status_code == 400
        assert "结算金额" in resp.json()["detail"]

    def test_settle_rejects_non_positive_amount_before_counterparty_lookup(self):
        """非正数 amount 优先返回 400，不因 counterparty 不存在返回 404。"""
        for amount in ["0", "-10"]:
            resp = client.post(
                "/debts/settle",
                json={"counterparty": f"不存在的人{amount}", "amount": amount},
            )

            assert resp.status_code == 400
            assert "结算金额" in resp.json()["detail"]

    def test_settle_rejects_invalid_amount(self):
        """结算金额不是有效数字时返回参数错误。"""
        client.post(
            "/debts",
            json={
                "record_type": "cost",
                "category": "农药",
                "amount": "100",
                "record_date": date.today().isoformat(),
                "record_subtype": "赊账",
                "counterparty": "非法数字金额测试",
                "due_date": (date.today() + timedelta(days=15)).isoformat(),
            },
        )

        resp = client.post(
            "/debts/settle",
            json={
                "counterparty": "非法数字金额测试",
                "amount": "abc",
            },
        )

        assert resp.status_code == 400
        assert "amount" in resp.json()["detail"]

    def test_settle_rejects_non_finite_amount(self):
        """结算金额为非有限数字时返回参数错误。"""
        error_client = TestClient(app, raise_server_exceptions=False)

        for amount in ["NaN", "Infinity"]:
            counterparty = f"非有限金额测试{amount}"
            error_client.post(
                "/debts",
                json={
                    "record_type": "cost",
                    "category": "农药",
                    "amount": "100",
                    "record_date": date.today().isoformat(),
                    "record_subtype": "赊账",
                    "counterparty": counterparty,
                    "due_date": (date.today() + timedelta(days=15)).isoformat(),
                },
            )
            resp = error_client.post(
                "/debts/settle",
                content=f'{{"counterparty":"{counterparty}","amount":{amount}}}',
                headers={"Content-Type": "application/json"},
            )

            assert resp.status_code == 400
            assert "amount" in resp.json()["detail"]
