"""报告历史列表 API 测试。"""

from datetime import datetime
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app
from app.schemas.agent import AdviceItem

client = TestClient(app)


class TestReportListAPI:
    """测试报告列表分页接口。"""

    def test_empty_list(self):
        """无报告时返回空列表和 total=0。"""
        resp = client.get("/agent/reports")

        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert "total" in data
        assert isinstance(data["items"], list)
        assert data["total"] == 0

    def test_pagination(self):
        """分页参数正常传递。"""
        resp = client.get("/agent/reports?page=1&size=5")

        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 0
        assert isinstance(data["items"], list)

    def test_pagination_page_two(self):
        """第二页参数正常。"""
        resp = client.get("/agent/reports?page=2&size=5")

        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert "total" in data

    def test_pagination_invalid_page(self):
        """page < 1 应返回 422。"""
        resp = client.get("/agent/reports?page=0&size=5")

        assert resp.status_code == 422

    def test_pagination_invalid_size(self):
        """size > 50 应返回 422。"""
        resp = client.get("/agent/reports?page=1&size=100")

        assert resp.status_code == 422


class TestRefreshDailyAdviceAPI:
    """测试强制刷新每日建议接口。"""

    @patch("app.application.advice_use_case.refresh_daily_advice")
    def test_refresh_endpoint(self, mock_refresh):
        """POST /agent/daily/refresh 返回新的建议。"""
        from app.schemas.agent import DailyAdviceResponse

        items = [AdviceItem(title="新建议", detail="施肥浇水", priority=1)]
        mock_refresh.return_value = DailyAdviceResponse(
            cycle_id=1, items=items, created_at=datetime.now()
        )

        resp = client.post("/agent/daily/refresh?cycle_id=1")

        assert resp.status_code == 200
        assert "新建议" in resp.json()["advice"]
        mock_refresh.assert_called_once()

    @patch("app.application.advice_use_case.refresh_daily_advice")
    def test_refresh_without_cycle_id(self, mock_refresh):
        """不带 cycle_id 也能正常刷新。"""
        from app.schemas.agent import DailyAdviceResponse

        items = [AdviceItem(title="综合建议", detail="注意天气", priority=2)]
        mock_refresh.return_value = DailyAdviceResponse(
            cycle_id=None, items=items, created_at=datetime.now()
        )

        resp = client.post("/agent/daily/refresh")

        assert resp.status_code == 200
        assert "综合建议" in resp.json()["advice"]
