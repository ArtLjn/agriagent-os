"""Tests for Admin Dashboard API。"""

from datetime import date, timedelta

import pytest

from app.main import app
from app.domains.conversation.models import Conversation
from app.domains.finance.cost_models import CostRecord
from app.domains.planting.crop_models import CropTemplate
from app.domains.planting.cycle_models import CropCycle
from app.domains.farm.models import Farm
from app.domains.planting.log_models import FarmLog
from app.domains.users.models import User
from app.domains.users.dependencies import get_current_user


_ADMIN = User(
    id="admin-001",
    phone="99999999999",
    password_hash="h",
    nickname="管理员",
    role="admin",
    status="active",
)


@pytest.fixture
def admin_client(client):
    """conftest 的 client 默认普通用户，这里 override 为 admin。"""
    app.dependency_overrides[get_current_user] = lambda: _ADMIN
    yield client


def _add_farm(session, farm_id, name="测试农场", user_id=None):
    farm = Farm(
        id=farm_id,
        name=name,
        user_id=user_id or f"user-{farm_id}",
    )
    session.add(farm)
    session.commit()
    return farm


def _add_user(session, user_id, phone):
    user = User(id=user_id, phone=phone, password_hash="h", nickname=user_id)
    session.add(user)
    session.commit()
    return user


def _add_cycle(session, cycle_id, farm_id):
    template = session.query(CropTemplate).first()
    if template is None:
        template = CropTemplate(
            id=1,
            farm_id=farm_id,
            name="测试作物",
            category="粮食",
        )
        session.add(template)
        session.commit()
    cycle = CropCycle(
        id=cycle_id,
        farm_id=farm_id,
        crop_template_id=template.id,
        name=f"周期{cycle_id}",
        start_date=date.today(),
    )
    session.add(cycle)
    session.commit()
    return cycle


def _add_log(session, farm_id, op_date, cycle_id=1):
    _ensure_cycle(session, cycle_id, farm_id)
    log = FarmLog(
        farm_id=farm_id,
        cycle_id=cycle_id,
        operation_type="water",
        operation_date=op_date,
    )
    session.add(log)
    session.commit()


def _ensure_cycle(session, cycle_id, farm_id):
    if session.query(CropCycle).filter(CropCycle.id == cycle_id).first():
        return
    _add_cycle(session, cycle_id, farm_id)


def _add_cost(session, farm_id, record_date, deleted=False):
    from datetime import datetime

    cost = CostRecord(
        farm_id=farm_id,
        record_type="cost",
        category="化肥",
        amount=100,
        record_date=record_date,
        deleted_at=datetime.now() if deleted else None,
    )
    session.add(cost)
    session.commit()


class TestSummary:
    def test_空业务数据返回基准值(self, admin_client) -> None:
        """conftest 默认插入 1 user + 1 farm，无业务数据时 dau/records 应为 0。"""
        resp = admin_client.get("/admin/dashboard/summary")
        assert resp.status_code == 200
        data = resp.json()
        assert data["farm_count"] == 1
        assert data["user_count"] == 1
        assert data["dau_today"] == 0
        assert data["records_today"] == 0

    def test_返回4张卡片数据(self, admin_client, db_session) -> None:
        _add_farm(db_session, farm_id=10)
        _add_farm(db_session, farm_id=11)
        _add_user(db_session, "u1", "11111111111")
        _add_user(db_session, "u2", "22222222222")

        today = date.today()
        conv = Conversation(
            farm_id=10,
            user_id="u1",
            session_id="sess-1",
            status="active",
        )
        db_session.add(conv)
        db_session.commit()

        _add_log(db_session, farm_id=10, op_date=today)
        _add_cost(db_session, farm_id=10, record_date=today)
        _add_cost(db_session, farm_id=11, record_date=today)

        resp = admin_client.get("/admin/dashboard/summary")
        assert resp.status_code == 200
        data = resp.json()
        assert data["farm_count"] == 3
        assert data["user_count"] == 3
        assert data["dau_today"] == 1
        assert data["records_today"] == 3

    def test_成本软删除不计入(self, admin_client, db_session) -> None:
        _add_farm(db_session, farm_id=10)
        today = date.today()
        _add_cost(db_session, farm_id=10, record_date=today, deleted=False)
        _add_cost(db_session, farm_id=10, record_date=today, deleted=True)

        resp = admin_client.get("/admin/dashboard/summary")
        data = resp.json()
        assert data["records_today"] == 1


class TestTrend:
    def test_默认7天(self, admin_client) -> None:
        resp = admin_client.get("/admin/dashboard/trend")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["days"]) == 7
        assert data["days"][-1]["date"] == date.today().isoformat()
        assert data["days"][-1]["count"] == 0

    def test_聚合日志和成本(self, admin_client, db_session) -> None:
        _add_farm(db_session, farm_id=10)
        today = date.today()
        yesterday = today - timedelta(days=1)

        _add_log(db_session, farm_id=10, op_date=today)
        _add_log(db_session, farm_id=10, op_date=today)
        _add_cost(db_session, farm_id=10, record_date=yesterday)

        resp = admin_client.get("/admin/dashboard/trend?days=7")
        data = resp.json()
        by_date = {item["date"]: item["count"] for item in data["days"]}
        assert by_date[today.isoformat()] == 2
        assert by_date[yesterday.isoformat()] == 1

    def test_天数参数校验(self, admin_client) -> None:
        assert admin_client.get("/admin/dashboard/trend?days=0").status_code == 422
        assert admin_client.get("/admin/dashboard/trend?days=31").status_code == 422

    def test_非admin被拒(self, client) -> None:
        normal_user = User(
            id="user-002",
            phone="88888888888",
            password_hash="h",
            nickname="普通",
            role="user",
            status="active",
        )
        app.dependency_overrides[get_current_user] = lambda: normal_user
        try:
            resp = client.get("/admin/dashboard/trend")
            assert resp.status_code == 403
        finally:
            app.dependency_overrides.pop(get_current_user, None)


class TestActiveUsers:
    def test_空列表(self, admin_client) -> None:
        resp = admin_client.get("/admin/dashboard/active-users")
        assert resp.status_code == 200
        assert resp.json() == {"items": []}

    def test_返回今日活跃用户(self, admin_client, db_session) -> None:
        _add_farm(db_session, farm_id=10, user_id="u-active")
        _add_farm(db_session, farm_id=11, user_id="u-other")
        _add_user(db_session, "u-active", "13912345678")
        _add_user(db_session, "u-other", "13800000000")

        from datetime import datetime

        db_session.add(
            Conversation(
                farm_id=10,
                user_id="u-active",
                session_id="sess-active",
                status="active",
                last_active_at=datetime.now(),
            )
        )
        db_session.commit()

        resp = admin_client.get("/admin/dashboard/active-users")
        assert resp.status_code == 200
        items = resp.json()["items"]
        assert len(items) == 1
        assert items[0]["user_id"] == "u-active"
        assert items[0]["phone_masked"] == "139****5678"
        assert items[0]["farm_name"] == "测试农场"
        assert items[0]["last_active_at"] is not None

    def test_同一用户多会话去重(self, admin_client, db_session) -> None:
        _add_farm(db_session, farm_id=10, user_id="u1")
        _add_user(db_session, "u1", "13912345678")

        from datetime import datetime

        for i in range(3):
            db_session.add(
                Conversation(
                    farm_id=10,
                    user_id="u1",
                    session_id=f"sess-{i}",
                    status="active",
                    last_active_at=datetime.now(),
                )
            )
        db_session.commit()

        resp = admin_client.get("/admin/dashboard/active-users")
        items = resp.json()["items"]
        assert len(items) == 1
