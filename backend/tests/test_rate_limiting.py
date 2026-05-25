"""限流中间件测试。"""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


class TestRateLimiting:
    def test_health_limit_header_present(self):
        response = client.get("/health")
        assert response.status_code == 200
        # slowapi 会返回 X-RateLimit-Limit 等头部
        assert "X-RateLimit-Limit" in response.headers
