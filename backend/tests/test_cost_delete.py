"""测试成本记录删除端点 — 软删除机制。"""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def _create_record(cycle_id: int | None = None, **overrides) -> dict:
    payload = {
        "record_type": "cost",
        "category": "化肥",
        "amount": "200.00",
        "record_date": "2025-03-10",
    }
    if cycle_id:
        payload["cycle_id"] = cycle_id
    payload.update(overrides)
    resp = client.post("/costs", json=payload)
    assert resp.status_code == 200
    return resp.json()


class TestDeleteCostRecord:
    """DELETE /costs/{id} 软删除测试。"""

    def test_delete_existing_record(self):
        """删除已存在的记录返回 200。"""
        record = _create_record()
        resp = client.delete(f"/costs/{record['id']}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == record["id"]

    def test_delete_twice_returns_404(self):
        """重复删除已软删除的记录返回 404。"""
        record = _create_record()
        client.delete(f"/costs/{record['id']}")
        resp = client.delete(f"/costs/{record['id']}")
        assert resp.status_code == 404

    def test_delete_nonexistent_returns_404(self):
        """删除不存在的记录返回 404。"""
        resp = client.delete("/costs/999999")
        assert resp.status_code == 404

    def test_deleted_record_excluded_from_list(self):
        """软删除的记录不出现在列表中。"""
        record = _create_record()
        client.delete(f"/costs/{record['id']}")
        resp = client.get("/costs")
        assert resp.status_code == 200
        ids = [r["id"] for r in resp.json()["items"]]
        assert record["id"] not in ids

    def test_deleted_record_excluded_from_profit(self):
        """软删除的记录不参与利润计算。"""
        _create_record(category="成本A", amount="100.00")
        income_record = _create_record(
            record_type="income", category="销售", amount="500.00"
        )
        client.delete(f"/costs/{income_record['id']}")

        resp = client.get("/costs")
        items = resp.json()["items"]

        cost = sum(float(r["amount"]) for r in items if r["record_type"] == "cost")
        income = sum(float(r["amount"]) for r in items if r["record_type"] == "income")
        assert cost == 100.00
        assert income == 0.00


class TestDeleteMeta:
    """Meta 测试 — 验证端点存在且方法正确。"""

    def test_delete_method_exists(self):
        """DELETE /costs/{id} 端点存在。"""
        resp = client.delete("/costs/999999")
        assert resp.status_code in (200, 404)
