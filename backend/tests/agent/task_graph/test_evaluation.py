"""Task Graph 评测报告聚合测试。"""

import pytest

from app.agent.task_graph.evaluation import aggregate_reports, create_evaluation_report

pytestmark = pytest.mark.no_db


def test_evaluation_report_creation_and_grouped_aggregation() -> None:
    reports = [
        create_evaluation_report(
            evaluation_id="e1",
            request_id="r1",
            task_type="planting_plan",
            planner_version="planner.v1",
            slot_score=1.0,
            plan_ir_valid=True,
            graph_compile_success=True,
            contract_pass_rate=1.0,
            capability_success_rate=1.0,
            repair_count=0,
            retry_count=0,
            hallucination_count=0,
            latency_ms=100,
            token_count=50,
            capability_metrics={"QueryFarmStatus": {"success": True}},
        ),
        create_evaluation_report(
            evaluation_id="e2",
            request_id="r2",
            task_type="planting_plan",
            planner_version="planner.v1",
            slot_score=0.5,
            plan_ir_valid=False,
            graph_compile_success=False,
            contract_pass_rate=0.0,
            capability_success_rate=0.0,
            repair_count=1,
            retry_count=2,
            hallucination_count=1,
            latency_ms=200,
            token_count=150,
            capability_metrics={"QueryFarmStatus": {"success": False}},
        ),
    ]

    by_planner = aggregate_reports(reports, by="planner_version")
    by_task = aggregate_reports(reports, by="task_type")
    by_capability = aggregate_reports(reports, by="capability")
    by_request = aggregate_reports(reports, by="request_id")

    assert by_planner["planner.v1"]["count"] == 2
    assert by_planner["planner.v1"]["slot_score_avg"] == 0.75
    assert by_task["planting_plan"]["retry_count_sum"] == 2
    assert by_capability["QueryFarmStatus"]["success_rate"] == 0.5
    assert by_request["r1"]["latency_ms_avg"] == 100
