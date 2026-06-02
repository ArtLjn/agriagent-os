"""Agent 仿真测试平台 FastAPI 路由层。"""

import asyncio
import logging
import secrets
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.api.deps import get_current_farm, get_db
from app.models.farm import Farm
from app.simulation.agent_client import AgentClient
from app.simulation.models import SimulationReport, SimulationResult
from app.simulation.reporter import SimulationReporter
from app.simulation.test_runner import SimulationRunner

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/simulation", tags=["Agent Simulation"])

# 内存存储（运行记录），后续可迁移到数据库
_runs_store: dict[str, dict] = {}
_reports_store: dict[str, dict] = {}
_background_tasks: set = set()


def _result_to_dict(result: SimulationResult) -> dict:
    """将 SimulationResult 转为可 JSON 序列化的 dict。"""
    return {
        "case_id": result.case_id,
        "passed": result.passed,
        "agent_reply": result.agent_reply,
        "errors": result.errors,
        "db_diff": {
            "added": result.db_diff.added,
            "removed": result.db_diff.removed,
            "modified": result.db_diff.modified,
        },
        "extracted_claims": [
            {
                "op_type": c.op_type,
                "description": c.description,
                "keywords_matched": c.keywords_matched,
            }
            for c in result.extracted_claims
        ],
        "latency_ms": result.latency_ms,
        "category": result.category,
        "run_id": result.run_id,
        "created_at": result.created_at.isoformat(),
    }


def _report_to_dict(report: SimulationReport) -> dict:
    """将 SimulationReport 转为可 JSON 序列化的 dict。"""
    return {
        "run_id": report.run_id,
        "total": report.total,
        "passed": report.passed,
        "failed": report.failed,
        "accuracy": report.accuracy,
        "avg_latency_ms": report.avg_latency_ms,
        "failure_breakdown": report.failure_breakdown,
        "results": [_result_to_dict(r) for r in report.results],
        "created_at": report.created_at.isoformat(),
    }


def _case_to_dict(case) -> dict:
    """将 SimulationTestCase 转为 dict。"""
    return {
        "case_id": case.case_id,
        "description": case.description,
        "user_input": case.user_input,
        "expected_response_matches": case.expected_response_matches,
        "expected_db_changes": case.expected_db_changes,
        "verify_tables": case.verify_tables,
        "category": case.category,
        "precondition": case.precondition,
    }


@router.get("/cases")
async def list_cases(
    category: str | None = None,
    farm: Farm = Depends(get_current_farm),
):
    """列出所有测试用例。"""
    runner = SimulationRunner(
        agent_client=AgentClient(), db=None, farm_id=farm.id
    )
    cases = runner.load_cases(category)
    return {"cases": [_case_to_dict(c) for c in cases]}


@router.post("/run")
async def start_run(
    request: Request,
    body: dict,
    db: Session = Depends(get_db),
    farm: Farm = Depends(get_current_farm),
):
    """
    启动仿真测试（后台异步执行）。
    如果 case_ids 为 None 或空数组，执行全部用例。
    返回：{run_id, status, total}
    """
    agent_url = body.get("agent_url", "")
    if not agent_url:
        raise HTTPException(status_code=422, detail="agent_url 不能为空")

    case_ids = body.get("case_ids")
    profile = body.get("profile", "default")

    # 加载全部用例
    runner = SimulationRunner(
        agent_client=AgentClient(), db=db, farm_id=farm.id
    )
    all_cases = runner.load_cases()

    # 过滤用例
    if case_ids:
        case_set = set(case_ids)
        cases = [c for c in all_cases if c.case_id in case_set]
    else:
        cases = all_cases

    run_id = f"sim_{secrets.token_hex(4)}"
    total = len(cases)

    _runs_store[run_id] = {
        "run_id": run_id,
        "status": "running",
        "total": total,
        "progress": {"current": 0, "total": total},
        "results": [],
        "profile": profile,
        "created_at": datetime.now().isoformat(),
    }

    # 获取当前请求的 token，用于后台任务调用 Agent
    auth_header = request.headers.get("Authorization", "")
    token = auth_header[7:] if auth_header.startswith("Bearer ") else ""

    agent_client = AgentClient(base_url=agent_url, token=token)
    task_runner = SimulationRunner(
        agent_client=agent_client, db=db, farm_id=farm.id
    )

    task = asyncio.create_task(_execute_run(run_id, cases, task_runner))
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)
    logger.info("仿真测试已启动 | run_id=%s total=%d", run_id, total)

    return {"run_id": run_id, "status": "running", "total": total}


async def _execute_run(
    run_id: str,
    cases: list,
    runner: SimulationRunner,
) -> None:
    """后台执行仿真测试。"""
    try:
        results = await runner.run_batch(cases, run_id=run_id)

        # 更新进度
        _runs_store[run_id]["progress"]["current"] = len(cases)
        _runs_store[run_id]["results"] = [_result_to_dict(r) for r in results]

        # 生成报告
        reporter = SimulationReporter()
        report = reporter.generate(results, run_id=run_id)

        _runs_store[run_id]["status"] = "completed"
        _reports_store[run_id] = _report_to_dict(report)

        logger.info(
            "仿真测试完成 | run_id=%s total=%d passed=%d",
            run_id,
            report.total,
            report.passed,
        )
    except Exception as exc:
        logger.exception("仿真测试执行失败 | run_id=%s", run_id)
        _runs_store[run_id]["status"] = "failed"
        _runs_store[run_id]["error"] = str(exc)


@router.get("/run/{run_id}")
async def get_run_status(
    run_id: str,
    farm: Farm = Depends(get_current_farm),
):
    """查询测试运行状态。"""
    run = _runs_store.get(run_id)
    if run is None:
        raise HTTPException(
            status_code=404,
            detail={"error": "RUN_NOT_FOUND", "message": "运行记录不存在"},
        )
    return run


@router.get("/runs")
async def list_runs(
    limit: int = 20,
    farm: Farm = Depends(get_current_farm),
):
    """列出历史运行记录。"""
    runs = sorted(
        _runs_store.values(),
        key=lambda r: r.get("created_at", ""),
        reverse=True,
    )
    return {"runs": runs[:limit]}


@router.get("/reports/{run_id}")
async def get_report(
    run_id: str,
    farm: Farm = Depends(get_current_farm),
):
    """获取测试报告。"""
    report = _reports_store.get(run_id)
    if report is None:
        raise HTTPException(
            status_code=404,
            detail={"error": "REPORT_NOT_FOUND", "message": "测试报告不存在"},
        )
    return report
