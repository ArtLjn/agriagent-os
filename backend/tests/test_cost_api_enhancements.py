"""测试成本 API 增强：日期筛选、编辑和删除功能。"""

import pytest
from datetime import date
from decimal import Decimal
from sqlalchemy.orm import Session
from fastapi.testclient import TestClient

from app.models.cost import CostRecord
from app.models.farm import Farm
from app.api.deps import get_db, get_current_farm
from app.core.database import SessionLocal


@pytest.fixture
def client():
    """创建测试客户端。"""
    from app.api.cost import router
    from fastapi import FastAPI
    from app.models.farm import Farm

    app = FastAPI()
    app.include_router(router)

    def override_get_db():
        try:
            db = SessionLocal()
            yield db
        finally:
            db.close()

    def override_get_current_farm():
        # 返回测试农场
        return Farm(id=1, name="默认农场")

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_farm] = override_get_current_farm
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()


@pytest.fixture
def auth_headers():
    """模拟认证头（简化版，实际应包含有效 token）。"""
    return {"Authorization": "Bearer fake-token-for-testing"}


@pytest.fixture
def db():
    """创建数据库会话。"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def test_farm():
    """测试农场对象。"""
    return Farm(id=1, name="默认农场")


@pytest.fixture
def sample_cost_record(db: Session, test_farm: Farm):
    """创建测试用成本记录。"""
    record = CostRecord(
        cycle_id=None,
        record_type="cost",
        category="种子",
        amount=Decimal("100.00"),
        record_date=date(2026, 1, 15),
        note="测试记录",
        farm_id=test_farm.id,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


class TestListRecordsWithDateFilter:
    """测试列表记录日期筛选功能。"""

    def test_list_records_with_date_range(self, client, auth_headers, sample_cost_record):
        """测试按日期范围筛选记录。"""
        response = client.get(
            "/costs",
            headers=auth_headers,
            params={"date_from": "2026-01-01", "date_to": "2026-01-31"},
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["id"] == sample_cost_record.id
        assert data[0]["record_date"] == "2026-01-15"

    def test_list_records_date_from_only(self, client, auth_headers, sample_cost_record):
        """测试只使用起始日期筛选。"""
        response = client.get(
            "/costs",
            headers=auth_headers,
            params={"date_from": "2026-01-01"},
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1

    def test_list_records_date_to_only(self, client, auth_headers, sample_cost_record):
        """测试只使用结束日期筛选。"""
        response = client.get(
            "/costs",
            headers=auth_headers,
            params={"date_to": "2026-01-31"},
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1

    def test_list_records_no_match(self, client, auth_headers, sample_cost_record):
        """测试日期范围无匹配记录。"""
        response = client.get(
            "/costs",
            headers=auth_headers,
            params={"date_from": "2026-02-01", "date_to": "2026-02-28"},
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 0


class TestUpdateRecord:
    """测试更新记录功能。"""

    def test_update_record_success(self, client, auth_headers, sample_cost_record):
        """测试成功更新记录。"""
        update_data = {
            "category": "化肥",
            "amount": "150.00",
            "note": "更新后的备注",
        }
        response = client.put(
            f"/costs/{sample_cost_record.id}",
            headers=auth_headers,
            json=update_data,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["category"] == "化肥"
        assert data["amount"] == "150.00"
        assert data["note"] == "更新后的备注"

    def test_update_record_partial(self, client, auth_headers, sample_cost_record):
        """测试部分字段更新。"""
        update_data = {"note": "只更新备注"}
        response = client.put(
            f"/costs/{sample_cost_record.id}",
            headers=auth_headers,
            json=update_data,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["note"] == "只更新备注"
        # 其他字段保持不变
        assert data["category"] == "种子"
        assert data["amount"] == "100.00"

    def test_update_record_not_found(self, client, auth_headers):
        """测试更新不存在的记录。"""
        update_data = {"note": "测试"}
        response = client.put(
            "/costs/99999",
            headers=auth_headers,
            json=update_data,
        )
        assert response.status_code == 404


class TestDeleteRecord:
    """测试删除记录功能。"""

    def test_delete_record_success(self, client, auth_headers, db: Session, test_farm: Farm):
        """测试成功删除记录。"""
        # 创建测试记录
        record = CostRecord(
            cycle_id=None,
            record_type="cost",
            category="种子",
            amount=Decimal("100.00"),
            record_date=date(2026, 1, 15),
            farm_id=test_farm.id,
        )
        db.add(record)
        db.commit()
        db.refresh(record)

        # 删除记录
        response = client.delete(
            f"/costs/{record.id}",
            headers=auth_headers,
        )
        assert response.status_code == 200
        assert response.json()["message"] == "删除成功"

        # 验证记录已删除
        deleted_record = db.query(CostRecord).filter(CostRecord.id == record.id).first()
        assert deleted_record is None

    def test_delete_record_not_found(self, client, auth_headers):
        """测试删除不存在的记录。"""
        response = client.delete(
            "/costs/99999",
            headers=auth_headers,
        )
        assert response.status_code == 404
