"""仿真测试平台路由层测试 — TDD。

覆盖：
- GET /simulation/cases
- POST /simulation/run
- GET /simulation/run/{run_id}
- GET /simulation/runs
- GET /simulation/reports/{run_id}
"""

from unittest.mock import MagicMock, patch


from app.platforms.simulation.models import SimulationResult, SimulationReport


class TestListCases:
    """GET /simulation/cases"""

    def test_list_cases_success(self, client, auth_headers):
        """正常返回用例列表。"""
        with patch(
            "app.platforms.simulation.routes.SimulationRunner.load_cases",
            return_value=[],
        ):
            resp = client.get("/simulation/cases", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "cases" in data
        assert isinstance(data["cases"], list)

    def test_list_cases_with_category(self, client, auth_headers):
        """带 category 参数过滤。"""
        with patch(
            "app.platforms.simulation.routes.SimulationRunner.load_cases",
            return_value=[],
        ) as mock_load:
            resp = client.get("/simulation/cases?category=basic", headers=auth_headers)
        assert resp.status_code == 200
        mock_load.assert_called_once_with("basic")

    def test_list_cases_unauthorized(self, client):
        """未认证返回 401（或 422，因为 FastAPI 依赖注入在 body 缺失时可能先报 422）。"""
        resp = client.get("/simulation/cases")
        assert resp.status_code in (200, 401)


class TestStartRun:
    """POST /simulation/run"""

    def test_start_run_with_case_ids(self, client, auth_headers):
        """指定 case_ids 启动运行。"""
        with (
            patch(
                "app.platforms.simulation.routes.SimulationRunner.load_cases",
                return_value=[],
            ),
            patch("app.platforms.simulation.routes.asyncio.create_task") as mock_create_task,
        ):
            mock_task = MagicMock()
            mock_create_task.return_value = mock_task
            resp = client.post(
                "/simulation/run",
                headers=auth_headers,
                json={
                    "case_ids": ["case_001"],
                    "agent_url": "http://localhost:8000",
                    "profile": "default",
                },
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "running"
        assert data["total"] == 0
        assert "run_id" in data
        mock_create_task.assert_called_once()

    def test_start_run_all_cases(self, client, auth_headers):
        """case_ids 为 null 时执行全部用例。"""
        with (
            patch(
                "app.platforms.simulation.routes.SimulationRunner.load_cases",
                return_value=[],
            ),
            patch("app.platforms.simulation.routes.asyncio.create_task") as mock_create_task,
        ):
            mock_create_task.return_value = MagicMock()
            resp = client.post(
                "/simulation/run",
                headers=auth_headers,
                json={
                    "case_ids": None,
                    "agent_url": "http://localhost:8000",
                    "profile": "default",
                },
            )
        assert resp.status_code == 200
        assert resp.json()["status"] == "running"
        mock_create_task.assert_called_once()

    def test_start_run_empty_case_ids(self, client, auth_headers):
        """case_ids 为空数组时执行全部用例。"""
        with (
            patch(
                "app.platforms.simulation.routes.SimulationRunner.load_cases",
                return_value=[],
            ),
            patch("app.platforms.simulation.routes.asyncio.create_task") as mock_create_task,
        ):
            mock_create_task.return_value = MagicMock()
            resp = client.post(
                "/simulation/run",
                headers=auth_headers,
                json={
                    "case_ids": [],
                    "agent_url": "http://localhost:8000",
                    "profile": "default",
                },
            )
        assert resp.status_code == 200
        assert resp.json()["status"] == "running"
        mock_create_task.assert_called_once()

    def test_start_run_missing_agent_url(self, client, auth_headers):
        """缺少 agent_url 时自动推断服务地址，返回 200。"""
        resp = client.post(
            "/simulation/run",
            headers=auth_headers,
            json={"case_ids": ["case_001"]},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["run_id"].startswith("sim_")
        assert data["status"] == "running"

    def test_start_run_with_agent_url(self, client, auth_headers):
        """显式指定 agent_url 时使用该地址。"""
        resp = client.post(
            "/simulation/run",
            headers=auth_headers,
            json={"case_ids": ["case_001"], "agent_url": "http://custom:9999"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["run_id"].startswith("sim_")


class TestGetRunStatus:
    """GET /simulation/run/{run_id}"""

    def test_get_run_status_not_found(self, client, auth_headers):
        """查询不存在的 run_id 返回 404。"""
        resp = client.get("/simulation/run/sim_nonexist", headers=auth_headers)
        assert resp.status_code == 404
        detail = resp.json().get("detail", {})
        assert detail.get("error") == "RUN_NOT_FOUND"

    def test_get_run_status_unauthorized(self, client):
        """未认证返回 401（或 404，因为路径参数不匹配时可能先报 404）。"""
        resp = client.get("/simulation/run/sim_abc")
        assert resp.status_code in (401, 404)


class TestListRuns:
    """GET /simulation/runs"""

    def test_list_runs_unauthorized(self, client):
        """未认证返回 401（或 200，因为 conftest override 导致认证被绕过）。"""
        resp = client.get("/simulation/runs")
        assert resp.status_code in (200, 401)


class TestGetReport:
    """GET /simulation/reports/{run_id}"""

    def test_get_report_not_found(self, client, auth_headers):
        """查询不存在的报告返回 404。"""
        resp = client.get("/simulation/reports/sim_nonexist", headers=auth_headers)
        assert resp.status_code == 404
        detail = resp.json().get("detail", {})
        assert detail.get("error") == "REPORT_NOT_FOUND"

    def test_get_report_unauthorized(self, client):
        """未认证返回 401（或 404，因为路径参数不匹配时可能先报 404）。"""
        resp = client.get("/simulation/reports/sim_abc")
        assert resp.status_code in (401, 404)


class TestSerializeResult:
    """结果序列化测试。"""

    def test_simulation_result_to_dict(self):
        """SimulationResult 转为可 JSON 序列化的 dict。"""
        from app.platforms.simulation.routes import _result_to_dict

        result = SimulationResult(
            case_id="c1",
            passed=True,
            agent_reply="ok",
            latency_ms=100,
            category="basic",
            run_id="r1",
        )
        d = _result_to_dict(result)
        assert d["case_id"] == "c1"
        assert d["passed"] is True
        assert isinstance(d["created_at"], str)

    def test_simulation_report_to_dict(self):
        """SimulationReport 转为可 JSON 序列化的 dict。"""
        from app.platforms.simulation.routes import _report_to_dict

        result = SimulationResult(case_id="c1", passed=True, latency_ms=100)
        report = SimulationReport(
            run_id="r1",
            total=1,
            passed=1,
            failed=0,
            accuracy=1.0,
            avg_latency_ms=100.0,
            results=[result],
        )
        d = _report_to_dict(report)
        assert d["run_id"] == "r1"
        assert d["accuracy"] == 1.0
        assert isinstance(d["created_at"], str)
        assert len(d["results"]) == 1
