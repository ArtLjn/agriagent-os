"""Agent 仿真测试平台 FastAPI 路由层。"""

import asyncio
import logging
import secrets
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.shared.database import get_db
from app.modules.farm.dependencies import get_current_farm
from app.models.farm import Farm
from app.models.simulation import SimulationRun, SimulationResultRecord
from app.simulation.agent_client import AgentClient
from app.simulation.models import SimulationReport, SimulationResult
from app.simulation.reporter import SimulationReporter
from app.simulation.test_runner import SimulationRunner
from app.shared.config import settings

logger = logging.getLogger(__name__)


def _get_service_base_url() -> str:
    """获取当前服务的完整 base URL。"""
    host = (
        "127.0.0.1"
        if settings.server.host in ("0.0.0.0", "::")
        else settings.server.host
    )
    return f"http://{host}:{settings.server.port}"


router = APIRouter(prefix="/simulation", tags=["Agent Simulation"])

# 内存缓存：仅用于 running 状态的进度追踪（后台任务更新用）
_progress_cache: dict[str, dict] = {}
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
        "user_input": result.user_input,
        "pending_action": result.pending_action,
        "expected_db_changes": result.expected_db_changes,
        "skill_traces": result.skill_traces,
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


def _run_to_dict(run: SimulationRun) -> dict:
    """将 SimulationRun ORM 对象转为 dict。"""
    return {
        "run_id": run.run_id,
        "status": run.status,
        "total": run.total,
        "passed": run.passed,
        "failed": run.failed,
        "profile": run.profile,
        "progress": _progress_cache.get(
            run.run_id, {"current": run.total, "total": run.total}
        ),
        "created_at": run.created_at.isoformat()
        if run.created_at
        else datetime.now().isoformat(),
    }


def _run_with_results_to_dict(
    run: SimulationRun, results: list[SimulationResultRecord]
) -> dict:
    """将 SimulationRun + 结果列表 转为完整 dict。"""
    d = _run_to_dict(run)
    d["results"] = [_result_record_to_dict(r) for r in results]
    d["error"] = run.error
    return d


def _result_record_to_dict(r: SimulationResultRecord) -> dict:
    """将 SimulationResultRecord ORM 对象转为 dict。"""
    return {
        "case_id": r.case_id,
        "passed": bool(r.passed),
        "agent_reply": r.agent_reply or "",
        "errors": r.errors,
        "db_diff": r.db_diff or {"added": [], "removed": [], "modified": []},
        "extracted_claims": r.extracted_claims or [],
        "latency_ms": r.latency_ms,
        "category": r.category or "basic",
        "run_id": r.run_id,
        "user_input": r.user_input or "",
        "pending_action": r.pending_action,
        "expected_db_changes": r.expected_db_changes or {},
        "skill_traces": getattr(r, "skill_traces", None) or [],
    }


def _report_from_run(run: SimulationRun, results: list[SimulationResultRecord]) -> dict:
    """从 DB 记录组装报告 dict。"""
    result_dicts = [_result_record_to_dict(r) for r in results]
    total = len(results)
    passed = sum(1 for r in results if r.passed)
    failed = total - passed
    accuracy = round(passed / total, 4) if total > 0 else 0.0
    avg_latency = (
        round(sum(r.latency_ms for r in results) / total, 2) if total > 0 else 0.0
    )

    # 失败分类统计
    failure_breakdown: dict[str, int] = {}
    for r in results:
        if not r.passed:
            for err in r.errors:
                typ = err.split(":")[0] if ":" in err else "unknown"
                failure_breakdown[typ] = failure_breakdown.get(typ, 0) + 1

    return {
        "run_id": run.run_id,
        "total": total,
        "passed": passed,
        "failed": failed,
        "accuracy": accuracy,
        "avg_latency_ms": avg_latency,
        "failure_breakdown": failure_breakdown,
        "results": result_dicts,
        "created_at": run.created_at.isoformat()
        if run.created_at
        else datetime.now().isoformat(),
    }


@router.get("/cases")
async def list_cases(
    category: str | None = None,
    farm: Farm = Depends(get_current_farm),
):
    """列出所有测试用例。"""
    runner = SimulationRunner(agent_client=AgentClient(), db=None, farm_id=farm.id)
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
        agent_url = _get_service_base_url()

    case_ids = body.get("case_ids")
    profile = body.get("profile", "default")

    runner = SimulationRunner(agent_client=AgentClient(), db=db, farm_id=farm.id)
    all_cases = runner.load_cases()

    if case_ids:
        case_set = set(case_ids)
        cases = [c for c in all_cases if c.case_id in case_set]
    else:
        cases = all_cases

    run_id = f"sim_{secrets.token_hex(4)}"
    total = len(cases)

    # 写入 DB
    db_run = SimulationRun(
        run_id=run_id,
        farm_id=farm.id,
        status="running",
        total=total,
        profile=profile,
    )
    db.add(db_run)
    db.commit()

    # 内存进度缓存
    _progress_cache[run_id] = {"current": 0, "total": total}

    # 获取当前请求的 token
    auth_header = request.headers.get("Authorization", "")
    token = auth_header[7:] if auth_header.startswith("Bearer ") else ""

    task = asyncio.create_task(_execute_run(run_id, cases, agent_url, token, farm.id))
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)
    logger.info("仿真测试已启动 | run_id=%s total=%d", run_id, total)

    return {"run_id": run_id, "status": "running", "total": total}


async def _execute_run(
    run_id: str,
    cases: list,
    agent_url: str,
    token: str,
    farm_id: int,
) -> None:
    """后台执行仿真测试。内部独立管理 session，不依赖请求级 session。"""
    from app.shared.database import SessionLocal

    db = SessionLocal()
    try:
        agent_client = AgentClient(base_url=agent_url, token=token)
        runner = SimulationRunner(agent_client=agent_client, db=db, farm_id=farm_id)

        results = await runner.run_batch(cases, run_id=run_id)

        # 保存每个结果到 DB
        for result in results:
            record = SimulationResultRecord(
                run_id=run_id,
                farm_id=farm_id,
                case_id=result.case_id,
                passed=1 if result.passed else 0,
                agent_reply=result.agent_reply,
                errors=result.errors,
                db_diff=_result_to_dict(result)["db_diff"],
                extracted_claims=_result_to_dict(result)["extracted_claims"],
                latency_ms=result.latency_ms,
                category=result.category,
                user_input=result.user_input,
                pending_action=result.pending_action,
                expected_db_changes=result.expected_db_changes,
            )
            db.add(record)

        # 更新进度
        if run_id in _progress_cache:
            _progress_cache[run_id]["current"] = len(cases)

        # 生成报告
        reporter = SimulationReporter()
        report = reporter.generate(results, run_id=run_id)

        # 更新运行记录状态
        db_run = db.query(SimulationRun).filter(SimulationRun.run_id == run_id).first()
        if db_run:
            db_run.status = "completed"
            db_run.passed = report.passed
            db_run.failed = report.failed

        db.commit()

        logger.info(
            "仿真测试完成 | run_id=%s total=%d passed=%d",
            run_id,
            report.total,
            report.passed,
        )
    except Exception as exc:
        logger.exception("仿真测试执行失败 | run_id=%s", run_id)
        db_run = db.query(SimulationRun).filter(SimulationRun.run_id == run_id).first()
        if db_run:
            db_run.status = "failed"
            db_run.error = str(exc)
        db.commit()
    finally:
        db.close()
        # 清理进度缓存（保留一小段时间后自动清理）
        _progress_cache.pop(run_id, None)


@router.get("/run/{run_id}")
async def get_run_status(
    run_id: str,
    db: Session = Depends(get_db),
    farm: Farm = Depends(get_current_farm),
):
    """查询测试运行状态。"""
    # 优先从内存缓存获取 running 状态
    if run_id in _progress_cache:
        db_run = (
            db.query(SimulationRun)
            .filter(
                SimulationRun.run_id == run_id,
                SimulationRun.farm_id == farm.id,
            )
            .first()
        )
        if db_run:
            results = (
                db.query(SimulationResultRecord)
                .filter(
                    SimulationResultRecord.run_id == run_id,
                    SimulationResultRecord.farm_id == farm.id,
                )
                .all()
            )
            return _run_with_results_to_dict(db_run, results)

    # 从 DB 查询
    db_run = (
        db.query(SimulationRun)
        .filter(
            SimulationRun.run_id == run_id,
            SimulationRun.farm_id == farm.id,
        )
        .first()
    )
    if db_run is None:
        raise HTTPException(
            status_code=404,
            detail={"error": "RUN_NOT_FOUND", "message": "运行记录不存在"},
        )

    results = (
        db.query(SimulationResultRecord)
        .filter(
            SimulationResultRecord.run_id == run_id,
            SimulationResultRecord.farm_id == farm.id,
        )
        .all()
    )
    return _run_with_results_to_dict(db_run, results)


@router.get("/runs")
async def list_runs(
    limit: int = 20,
    db: Session = Depends(get_db),
    farm: Farm = Depends(get_current_farm),
):
    """列出历史运行记录。"""
    runs = (
        db.query(SimulationRun)
        .filter(
            SimulationRun.farm_id == farm.id,
        )
        .order_by(SimulationRun.created_at.desc())
        .limit(limit)
        .all()
    )
    return {"runs": [_run_to_dict(r) for r in runs]}


@router.get("/reports/{run_id}")
async def get_report(
    run_id: str,
    db: Session = Depends(get_db),
    farm: Farm = Depends(get_current_farm),
):
    """获取测试报告。"""
    db_run = (
        db.query(SimulationRun)
        .filter(
            SimulationRun.run_id == run_id,
            SimulationRun.farm_id == farm.id,
        )
        .first()
    )
    if db_run is None:
        raise HTTPException(
            status_code=404,
            detail={"error": "REPORT_NOT_FOUND", "message": "测试报告不存在"},
        )

    results = (
        db.query(SimulationResultRecord)
        .filter(
            SimulationResultRecord.run_id == run_id,
            SimulationResultRecord.farm_id == farm.id,
        )
        .all()
    )

    return _report_from_run(db_run, results)
