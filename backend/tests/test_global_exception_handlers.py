"""全局异常处理器测试。"""

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


class TestGlobalExceptionHandlers:
    def test_http_exception_returns_detail(self):
        """HTTP 异常原样返回，保留 status code 和 detail。"""
        response = client.get("/crops/templates/99999")

        assert response.status_code == 404
        data = response.json()
        assert "detail" in data

    def test_validation_error_returns_structured_errors(self):
        """请求参数校验失败，返回 422 和结构化字段错误。"""
        response = client.post("/costs", json={"record_type": "invalid"})

        assert response.status_code == 422
        data = response.json()
        assert data["detail"] == "请求参数校验失败"
        assert "errors" in data
        assert isinstance(data["errors"], list)
        assert all(
            "field" in err and "message" in err and "type" in err
            for err in data["errors"]
        )

    def test_graph_recursion_error(self):
        """通过调用 Agent 接口触发步数超限（需配合 recursion_limit=1 测试）。"""
        pytest.skip("需要配合 Agent 步数限制配置，暂跳过")

    def test_500_error_masked(self):
        """未捕获异常不泄漏堆栈。"""
        pytest.skip("需要构造内部异常端点，暂跳过")
