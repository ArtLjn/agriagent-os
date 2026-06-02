"""测试仿真测试执行引擎。"""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.simulation.models import SimulationResult, SimulationTestCase
from app.simulation.test_runner import SimulationRunner


class TestParseCase:
    def test_parse_case_full(self):
        raw = {
            "case_id": "tc-001",
            "description": "测试记账",
            "user_input": "买化肥花了200",
            "expected_response_matches": ["已记账"],
            "expected_db_changes": {"cost_records": {"added": 1}},
            "verify_tables": ["cost_records"],
            "category": "cost",
            "precondition": {"ensure_template_exists": "西瓜"},
        }
        case = SimulationRunner._parse_case(raw)
        assert case.case_id == "tc-001"
        assert case.description == "测试记账"
        assert case.user_input == "买化肥花了200"
        assert case.expected_response_matches == ["已记账"]
        assert case.expected_db_changes == {"cost_records": {"added": 1}}
        assert case.verify_tables == ["cost_records"]
        assert case.category == "cost"
        assert case.precondition == {"ensure_template_exists": "西瓜"}

    def test_parse_case_defaults(self):
        raw = {
            "case_id": "tc-002",
            "description": "测试",
            "user_input": "hello",
            "expected_response_matches": [],
            "expected_db_changes": {},
            "verify_tables": [],
        }
        case = SimulationRunner._parse_case(raw)
        assert case.category == "basic"
        assert case.precondition == {}


class TestLoadCases:
    def test_load_cases_from_directory(self, tmp_path, monkeypatch):
        cases_dir = tmp_path / "simulation_cases"
        cases_dir.mkdir()
        cases_file = cases_dir / "basic.json"
        cases_file.write_text(
            json.dumps(
                [
                    {
                        "case_id": "tc-001",
                        "description": "测试1",
                        "user_input": "input1",
                        "expected_response_matches": [],
                        "expected_db_changes": {},
                        "verify_tables": [],
                    },
                    {
                        "case_id": "tc-002",
                        "description": "测试2",
                        "user_input": "input2",
                        "expected_response_matches": [],
                        "expected_db_changes": {},
                        "verify_tables": [],
                        "category": "cost",
                    },
                ]
            )
        )

        monkeypatch.setattr(
            "app.simulation.test_runner.CASES_DIR", cases_dir
        )

        mock_db = MagicMock()
        runner = SimulationRunner(MagicMock(), mock_db)
        cases = runner.load_cases()

        assert len(cases) == 2
        assert cases[0].case_id == "tc-001"
        assert cases[1].case_id == "tc-002"

    def test_load_cases_filter_by_category(self, tmp_path, monkeypatch):
        cases_dir = tmp_path / "simulation_cases"
        cases_dir.mkdir()
        cases_file = cases_dir / "all.json"
        cases_file.write_text(
            json.dumps(
                [
                    {
                        "case_id": "tc-001",
                        "description": "测试1",
                        "user_input": "input1",
                        "expected_response_matches": [],
                        "expected_db_changes": {},
                        "verify_tables": [],
                        "category": "basic",
                    },
                    {
                        "case_id": "tc-002",
                        "description": "测试2",
                        "user_input": "input2",
                        "expected_response_matches": [],
                        "expected_db_changes": {},
                        "verify_tables": [],
                        "category": "cost",
                    },
                ]
            )
        )

        monkeypatch.setattr(
            "app.simulation.test_runner.CASES_DIR", cases_dir
        )

        mock_db = MagicMock()
        runner = SimulationRunner(MagicMock(), mock_db)
        cases = runner.load_cases(category="cost")

        assert len(cases) == 1
        assert cases[0].case_id == "tc-002"

    def test_load_cases_empty_directory(self, tmp_path, monkeypatch):
        cases_dir = tmp_path / "simulation_cases"
        cases_dir.mkdir()

        monkeypatch.setattr(
            "app.simulation.test_runner.CASES_DIR", cases_dir
        )

        mock_db = MagicMock()
        runner = SimulationRunner(MagicMock(), mock_db)
        cases = runner.load_cases()

        assert cases == []

    def test_load_cases_invalid_json(self, tmp_path, monkeypatch):
        cases_dir = tmp_path / "simulation_cases"
        cases_dir.mkdir()
        cases_file = cases_dir / "bad.json"
        cases_file.write_text("not json")

        monkeypatch.setattr(
            "app.simulation.test_runner.CASES_DIR", cases_dir
        )

        mock_db = MagicMock()
        runner = SimulationRunner(MagicMock(), mock_db)
        cases = runner.load_cases()

        assert cases == []


class TestSetupPrecondition:
    def test_setup_precondition_logs(self, caplog):
        mock_db = MagicMock()
        runner = SimulationRunner(MagicMock(), mock_db)
        with caplog.at_level("INFO"):
            runner._setup_precondition({"ensure_template_exists": "西瓜"})
        assert "前置条件" in caplog.text


class TestRunSingle:
    @pytest.mark.asyncio
    async def test_run_single_passed(self):
        mock_agent = MagicMock()
        mock_agent.send_message = AsyncMock(
            return_value={"reply": "已记账", "pending_action": None}
        )

        mock_db = MagicMock()
        runner = SimulationRunner(mock_agent, mock_db, farm_id=1)

        before_snapshot = {"cost_records": []}
        after_snapshot = {"cost_records": [{"id": 1, "amount": 200, "__table__": "cost_records"}]}

        with patch.object(
            runner._snapshot, "take", AsyncMock(side_effect=[before_snapshot, after_snapshot])
        ):
            case = SimulationTestCase(
                case_id="tc-001",
                description="测试记账",
                user_input="买化肥200块",
                expected_response_matches=["已记账"],
                expected_db_changes={"cost_records": {"added": 1}},
                verify_tables=["cost_records"],
            )
            result = await runner.run_single(case, run_id="run-001")

        assert isinstance(result, SimulationResult)
        assert result.case_id == "tc-001"
        assert result.passed is True
        assert result.agent_reply == "已记账"
        assert result.errors == []
        assert result.category == "basic"
        assert result.run_id == "run-001"
        assert result.latency_ms > 0

    @pytest.mark.asyncio
    async def test_run_single_with_pending_action(self):
        mock_agent = MagicMock()
        mock_agent.send_message = AsyncMock(
            return_value={
                "reply": "请确认",
                "pending_action": {
                    "action_id": "a1",
                    "skill_name": "create_cost_record",
                    "params": {"amount": 200},
                },
            }
        )
        mock_agent.send_confirm = AsyncMock(
            return_value={"reply": "已确认执行", "pending_action": None}
        )

        mock_db = MagicMock()
        runner = SimulationRunner(mock_agent, mock_db, farm_id=1)

        before_snapshot = {"cost_records": []}
        after_snapshot = {"cost_records": [{"id": 1, "amount": 200, "__table__": "cost_records"}]}

        with patch.object(
            runner._snapshot, "take", AsyncMock(side_effect=[before_snapshot, after_snapshot])
        ):
            case = SimulationTestCase(
                case_id="tc-002",
                description="测试确认流程",
                user_input="买化肥200块",
                expected_response_matches=["已确认"],
                expected_db_changes={"cost_records": {"added": 1}},
                verify_tables=["cost_records"],
            )
            result = await runner.run_single(case, run_id="run-001")

        assert result.passed is True
        mock_agent.send_confirm.assert_awaited_once()
        call_args = mock_agent.send_confirm.await_args
        assert call_args[0][0].startswith("sim-")  # session_id
        assert call_args[0][1] == "a1"

    @pytest.mark.asyncio
    async def test_run_single_failed(self):
        mock_agent = MagicMock()
        mock_agent.send_message = AsyncMock(
            return_value={"reply": "抱歉，系统繁忙", "pending_action": None}
        )

        mock_db = MagicMock()
        runner = SimulationRunner(mock_agent, mock_db, farm_id=1)

        before_snapshot = {"cost_records": []}
        after_snapshot = {"cost_records": []}

        with patch.object(
            runner._snapshot, "take", AsyncMock(side_effect=[before_snapshot, after_snapshot])
        ):
            case = SimulationTestCase(
                case_id="tc-003",
                description="测试失败",
                user_input="买化肥200块",
                expected_response_matches=["已记账"],
                expected_db_changes={"cost_records": {"added": 1}},
                verify_tables=["cost_records"],
            )
            result = await runner.run_single(case, run_id="run-001")

        assert result.passed is False
        assert any("response_mismatch" in e for e in result.errors)

    @pytest.mark.asyncio
    async def test_run_single_with_precondition(self):
        mock_agent = MagicMock()
        mock_agent.send_message = AsyncMock(
            return_value={"reply": "已记账", "pending_action": None}
        )

        mock_db = MagicMock()
        runner = SimulationRunner(mock_agent, mock_db, farm_id=1)

        before_snapshot = {"cost_records": []}
        after_snapshot = {"cost_records": [{"id": 1, "amount": 200, "__table__": "cost_records"}]}

        with patch.object(
            runner._snapshot, "take", AsyncMock(side_effect=[before_snapshot, after_snapshot])
        ):
            case = SimulationTestCase(
                case_id="tc-004",
                description="测试前置条件",
                user_input="买化肥200块",
                expected_response_matches=["已记账"],
                expected_db_changes={"cost_records": {"added": 1}},
                verify_tables=["cost_records"],
                precondition={"ensure_template_exists": "西瓜"},
            )
            result = await runner.run_single(case, run_id="run-001")

        assert result.passed is True


class TestRunBatch:
    @pytest.mark.asyncio
    async def test_run_batch(self):
        mock_agent = MagicMock()
        mock_agent.send_message = AsyncMock(
            return_value={"reply": "已记账", "pending_action": None}
        )

        mock_db = MagicMock()
        runner = SimulationRunner(mock_agent, mock_db, farm_id=1)

        before_snapshot = {"cost_records": []}
        after_snapshot = {"cost_records": [{"id": 1, "amount": 200, "__table__": "cost_records"}]}

        with patch.object(
            runner._snapshot, "take", AsyncMock(side_effect=[before_snapshot, after_snapshot] * 2)
        ):
            cases = [
                SimulationTestCase(
                    case_id="tc-001",
                    description="测试1",
                    user_input="input1",
                    expected_response_matches=["已记账"],
                    expected_db_changes={"cost_records": {"added": 1}},
                    verify_tables=["cost_records"],
                ),
                SimulationTestCase(
                    case_id="tc-002",
                    description="测试2",
                    user_input="input2",
                    expected_response_matches=["已记账"],
                    expected_db_changes={"cost_records": {"added": 1}},
                    verify_tables=["cost_records"],
                ),
            ]
            results = await runner.run_batch(cases, run_id="run-001")

        assert len(results) == 2
        assert results[0].case_id == "tc-001"
        assert results[1].case_id == "tc-002"
