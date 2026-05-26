from datetime import datetime
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


class TestAgentChat:
    """测试 Agent 对话接口。"""

    @patch("app.api.agent.chat_with_agent")
    def test_chat_endpoint(self, mock_chat) -> None:
        """验证 POST /agent/chat 返回回复。"""
        from app.schemas.agent import ChatResponse

        mock_chat.return_value = ChatResponse(reply="建议：浇水。")

        response = client.post("/agent/chat", json={"message": "今天做什么？"})

        assert response.status_code == 200
        assert response.json()["reply"] == "建议：浇水。"


class TestAgentDaily:
    """测试每日建议接口。"""

    @patch("app.api.agent.get_daily_advice")
    def test_daily_advice_endpoint(self, mock_daily) -> None:
        """验证 GET /agent/daily 返回建议。"""
        from app.schemas.agent import AdviceItem, DailyAdviceResponse

        items = [AdviceItem(title="施肥", detail="追施复合肥", priority=1)]
        mock_daily.return_value = DailyAdviceResponse(
            cycle_id=1, items=items, created_at=datetime.now()
        )

        response = client.get("/agent/daily?cycle_id=1")

        assert response.status_code == 200
        assert "施肥" in response.json()["advice"]


class TestAgentReport:
    """测试报告接口。"""

    @patch("app.api.agent.generate_report")
    def test_report_endpoint(self, mock_report) -> None:
        """验证 POST /agent/report 返回报告。"""
        from app.schemas.agent import ReportResponse

        mock_report.return_value = ReportResponse(
            cycle_id=1,
            report_type="weekly",
            content="周报内容",
            created_at=datetime.now(),
        )

        response = client.post(
            "/agent/report", json={"cycle_id": 1, "report_type": "weekly"}
        )

        assert response.status_code == 200
        assert response.json()["content"] == "周报内容"


class TestAgentHistory:
    """测试历史记录接口。"""

    @patch("app.api.agent.get_advice_history")
    def test_advice_history_endpoint(self, mock_history) -> None:
        """验证 GET /agent/advice-history 返回列表。"""
        mock_history.return_value = []

        response = client.get("/agent/advice-history")

        assert response.status_code == 200
        assert response.json() == []

    @patch("app.api.agent.get_report_history")
    def test_report_history_endpoint(self, mock_history) -> None:
        """验证 GET /agent/report-history 返回列表。"""
        mock_history.return_value = []

        response = client.get("/agent/report-history")

        assert response.status_code == 200
        assert response.json() == []
