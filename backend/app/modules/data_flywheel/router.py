"""Admin 数据飞轮 API。"""

import uuid
from pathlib import Path
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.dependencies import get_db
from app.modules.auth.dependencies import get_current_user, require_admin
from app.modules.farm.dependencies import get_current_farm
from app.core.config import settings
from app.core.database import SessionLocal
from app.models.farm import Farm
from app.models.user import User
from app.modules.data_flywheel.service import (
    SAMPLE_TYPE_SESSION_TURN,
    build_case_draft,
    create_sample_prelabel,
    get_session_annotation_detail,
    get_sample_detail,
    list_samples,
)
from app.modules.data_flywheel.judge_service import (
    DataFlywheelJudgeClient,
    OpenAIDataFlywheelJudgeClient,
)
from app.modules.data_flywheel.session_review_service import get_session_review
from app.modules.data_flywheel.session_sync_service import sync_session_events

router = APIRouter(
    prefix="/admin/data-flywheel",
    tags=["admin-data-flywheel"],
    dependencies=[Depends(require_admin)],
)

AGENT_EVENT_BASE_DIR = Path("data/agent-events")
_SYNC_JOBS: dict[str, dict[str, Any]] = {}
_PRELABEL_BATCH_JOBS: dict[str, dict[str, Any]] = {}


class CaseDraftRequest(BaseModel):
    target_type: str = "evaluation_replay"


class SyncSessionsRequest(BaseModel):
    session_id: str | None = None
    only_missing: bool = True
    limit: int = 100
    run_inline: bool = False


class BatchPrelabelRequest(BaseModel):
    sample_type: str = SAMPLE_TYPE_SESSION_TURN
    label: str | None = None
    session_id: str | None = None
    request_id: str | None = None
    q: str | None = None
    unannotated_only: bool = True
    limit: int = 50
    skip_existing: bool = True
    run_inline: bool = False


@router.get("/samples")
def list_admin_data_flywheel_samples(
    sample_type: str = Query(SAMPLE_TYPE_SESSION_TURN),
    label: str | None = Query(None),
    session_id: str | None = Query(None),
    request_id: str | None = Query(None),
    q: str | None = Query(None),
    unannotated_only: bool = Query(False),
    sort_by: str = Query("risk", pattern="^(risk|time)$"),
    sort: str | None = Query(None, pattern="^(risk|time)$"),
    min_risk: float = Query(0.0, ge=0.0, le=1.0),
    severity: str = Query("all", pattern="^(P0|P1|all)$"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    farm: Farm = Depends(get_current_farm),
) -> dict[str, Any]:
    """列出当前农场的 Agent 数据飞轮样本。"""
    try:
        return list_samples(
            db,
            farm_id=farm.id,
            sample_type=sample_type or SAMPLE_TYPE_SESSION_TURN,
            label=label,
            session_id=session_id,
            request_id=request_id,
            q=q,
            unannotated_only=unannotated_only,
            sort_by=sort or sort_by,
            min_risk=min_risk,
            severity=severity,
            limit=limit,
            offset=offset,
        )
    except ValueError as exc:
        raise _http_error(exc) from exc


@router.get("/samples/{sample_id}")
def get_admin_data_flywheel_sample(
    sample_id: str,
    db: Session = Depends(get_db),
    farm: Farm = Depends(get_current_farm),
) -> dict[str, Any]:
    """获取单个数据飞轮样本详情。"""
    try:
        return get_sample_detail(db, farm_id=farm.id, sample_id=sample_id)
    except ValueError as exc:
        raise _http_error(exc) from exc


@router.get("/sessions/{session_id}/review")
def get_admin_data_flywheel_session_review(
    session_id: str,
    db: Session = Depends(get_db),
    farm: Farm = Depends(get_current_farm),
) -> dict[str, Any]:
    """获取单个会话的完整 turn 审阅时间线。"""
    return get_session_review(db, farm_id=farm.id, session_id=session_id)


@router.get("/sessions/{session_id}/annotations")
def get_admin_data_flywheel_session_annotations(
    session_id: str,
    db: Session = Depends(get_db),
    farm: Farm = Depends(get_current_farm),
) -> dict[str, Any]:
    """获取单个会话的会话级标注。"""
    try:
        return get_session_annotation_detail(db, farm_id=farm.id, session_id=session_id)
    except ValueError as exc:
        raise _http_error(exc) from exc


@router.post("/sync-sessions")
def sync_admin_data_flywheel_sessions(
    background_tasks: BackgroundTasks,
    body: SyncSessionsRequest | None = None,
    db: Session = Depends(get_db),
    farm: Farm = Depends(get_current_farm),
) -> dict[str, Any]:
    """将数据库已有会话补齐同步到 Agent JSONL 事件日志。"""
    payload = body or SyncSessionsRequest()
    if payload.run_inline:
        return {
            "mode": "inline",
            **sync_session_events(
                db,
                farm_id=farm.id,
                session_id=payload.session_id,
                only_missing=payload.only_missing,
                event_base_dir=AGENT_EVENT_BASE_DIR,
                limit=payload.limit,
            ),
        }

    job_id = f"session-sync-{uuid.uuid4().hex[:12]}"
    _SYNC_JOBS[job_id] = {
        "job_id": job_id,
        "status": "queued",
        "mode": "background",
        "farm_id": farm.id,
        "session_id": payload.session_id,
        "result": None,
        "error": None,
    }
    background_tasks.add_task(
        run_session_events_sync_job,
        job_id=job_id,
        farm_id=farm.id,
        session_id=payload.session_id,
        only_missing=payload.only_missing,
        event_base_dir=AGENT_EVENT_BASE_DIR,
        limit=payload.limit,
    )
    return _SYNC_JOBS[job_id]


@router.get("/sync-sessions/{job_id}")
def get_admin_data_flywheel_sync_job(job_id: str) -> dict[str, Any]:
    """查询会话事件补齐同步任务状态。"""
    job = _SYNC_JOBS.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail={"code": "SYNC_JOB_NOT_FOUND"})
    return job


@router.post("/prelabels/batch")
def create_admin_data_flywheel_prelabel_batch(
    background_tasks: BackgroundTasks,
    body: BatchPrelabelRequest | None = None,
    db: Session = Depends(get_db),
    farm: Farm = Depends(get_current_farm),
) -> dict[str, Any]:
    """按当前筛选批量触发 LLM 预判，不写入人工质量标签。"""
    payload = body or BatchPrelabelRequest()
    if not settings.data_flywheel.llm_prelabel_enabled:
        raise _http_error(ValueError("LLM_PRELABEL_DISABLED"))
    if payload.run_inline:
        return {
            "job_id": "inline",
            "status": "completed",
            "mode": "inline",
            "farm_id": farm.id,
            "result": run_prelabel_batch(
                db,
                farm_id=farm.id,
                sample_type=payload.sample_type,
                label=payload.label,
                session_id=payload.session_id,
                request_id=payload.request_id,
                q=payload.q,
                unannotated_only=payload.unannotated_only,
                limit=payload.limit,
                skip_existing=payload.skip_existing,
            ),
            "error": None,
        }

    job_id = f"prelabel-batch-{uuid.uuid4().hex[:12]}"
    _PRELABEL_BATCH_JOBS[job_id] = {
        "job_id": job_id,
        "status": "queued",
        "mode": "background",
        "farm_id": farm.id,
        "result": None,
        "error": None,
    }
    background_tasks.add_task(
        run_prelabel_batch_job,
        job_id=job_id,
        farm_id=farm.id,
        sample_type=payload.sample_type,
        label=payload.label,
        session_id=payload.session_id,
        request_id=payload.request_id,
        q=payload.q,
        unannotated_only=payload.unannotated_only,
        limit=payload.limit,
        skip_existing=payload.skip_existing,
    )
    return _PRELABEL_BATCH_JOBS[job_id]


@router.get("/prelabels/batch/{job_id}")
def get_admin_data_flywheel_prelabel_batch_job(job_id: str) -> dict[str, Any]:
    """查询批量 AI 预判任务状态。"""
    job = _PRELABEL_BATCH_JOBS.get(job_id)
    if job is None:
        raise HTTPException(
            status_code=404, detail={"code": "PRELABEL_BATCH_JOB_NOT_FOUND"}
        )
    return job


def run_session_events_sync_job(
    *,
    job_id: str,
    farm_id: int,
    session_id: str | None,
    only_missing: bool,
    event_base_dir: str | Path,
    limit: int,
) -> None:
    """后台执行会话事件补齐任务。"""
    job = _SYNC_JOBS.get(job_id)
    if job is not None:
        job["status"] = "running"
    db = SessionLocal()
    try:
        result = sync_session_events(
            db,
            farm_id=farm_id,
            session_id=session_id,
            only_missing=only_missing,
            event_base_dir=event_base_dir,
            limit=limit,
        )
    except Exception as exc:
        if job is not None:
            job["status"] = "failed"
            job["error"] = str(exc)
        raise
    finally:
        db.close()
    if job is not None:
        job["status"] = "completed"
        job["result"] = result


def run_prelabel_batch_job(
    *,
    job_id: str,
    farm_id: int,
    sample_type: str,
    label: str | None,
    session_id: str | None,
    request_id: str | None,
    q: str | None,
    unannotated_only: bool,
    limit: int,
    skip_existing: bool,
) -> None:
    """后台执行批量 LLM 预判任务。"""
    job = _PRELABEL_BATCH_JOBS.get(job_id)
    if job is not None:
        job["status"] = "running"
    db = SessionLocal()
    try:
        result = run_prelabel_batch(
            db,
            farm_id=farm_id,
            sample_type=sample_type,
            label=label,
            session_id=session_id,
            request_id=request_id,
            q=q,
            unannotated_only=unannotated_only,
            limit=limit,
            skip_existing=skip_existing,
        )
    except Exception as exc:
        if job is not None:
            job["status"] = "failed"
            job["error"] = str(exc)
        raise
    finally:
        db.close()
    if job is not None:
        job["status"] = "completed"
        job["result"] = result


def run_prelabel_batch(
    db: Session,
    *,
    farm_id: int,
    sample_type: str,
    label: str | None,
    session_id: str | None,
    request_id: str | None,
    q: str | None,
    unannotated_only: bool,
    limit: int,
    skip_existing: bool,
) -> dict[str, Any]:
    """同步执行一批样本的 LLM 预判，只创建 prelabel，不写人工标签。"""
    judge_client = build_data_flywheel_judge_client()
    listed = list_samples(
        db,
        farm_id=farm_id,
        sample_type=sample_type or SAMPLE_TYPE_SESSION_TURN,
        label=label,
        session_id=session_id,
        request_id=request_id,
        q=q,
        unannotated_only=unannotated_only,
        limit=limit,
        offset=0,
    )
    items: list[dict[str, Any]] = []
    created = 0
    skipped_existing = 0
    failed = 0

    for sample in listed["items"]:
        sample_id = str(sample["sample_id"])
        if skip_existing and sample.get("latest_prelabel"):
            skipped_existing += 1
            items.append({"sample_id": sample_id, "status": "skipped_existing"})
            continue
        try:
            prelabel = create_sample_prelabel(
                db,
                farm_id=farm_id,
                sample_id=sample_id,
                judge_client=judge_client,
            )
        except Exception as exc:
            failed += 1
            items.append(
                {"sample_id": sample_id, "status": "failed", "error": str(exc)}
            )
            continue
        created += 1
        items.append(
            {
                "sample_id": sample_id,
                "status": "created",
                "prelabel_id": prelabel["id"],
                "labels": prelabel["labels"],
                "confidence": prelabel["confidence"],
            }
        )

    return {
        "total": len(listed["items"]),
        "created": created,
        "skipped_existing": skipped_existing,
        "failed": failed,
        "items": items,
    }


@router.post("/samples/{sample_id}/prelabel")
def create_admin_data_flywheel_prelabel(
    sample_id: str,
    db: Session = Depends(get_db),
    farm: Farm = Depends(get_current_farm),
) -> dict[str, Any]:
    """管理员手动触发 LLM 预标注。"""
    try:
        if not settings.data_flywheel.llm_prelabel_enabled:
            raise ValueError("LLM_PRELABEL_DISABLED")
        judge_client = build_data_flywheel_judge_client()
        return create_sample_prelabel(
            db,
            farm_id=farm.id,
            sample_id=sample_id,
            judge_client=judge_client,
        )
    except ValueError as exc:
        raise _http_error(exc) from exc


@router.post("/samples/{sample_id}/case-draft")
def build_admin_data_flywheel_case_draft(
    sample_id: str,
    body: CaseDraftRequest,
    db: Session = Depends(get_db),
    farm: Farm = Depends(get_current_farm),
    user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """从样本生成评测用例草稿。"""
    try:
        return build_case_draft(
            db,
            farm_id=farm.id,
            sample_id=sample_id,
            target_type=body.target_type,
            created_by=user.id,
        )
    except ValueError as exc:
        raise _http_error(exc) from exc


def _http_error(exc: ValueError) -> HTTPException:
    if exc.args and isinstance(exc.args[0], dict):
        payload = exc.args[0]
        return HTTPException(status_code=400, detail=payload)
    code = str(exc)
    status_code = (
        404
        if code
        in {
            "SAMPLE_NOT_FOUND",
            "LABEL_NOT_FOUND",
            "PRELABEL_NOT_FOUND",
            "REPAIR_PACK_NOT_FOUND",
            "CHAIN_NOT_FOUND",
        }
        else 400
    )
    return HTTPException(status_code=status_code, detail={"code": code})


def build_data_flywheel_judge_client() -> DataFlywheelJudgeClient:
    try:
        from app.core.llm_client_manager import get_llm_manager

        manager = get_llm_manager()
        if not manager.fallback_mode:
            client, info = manager.get_sync_client_with_info(role="generation")
            return OpenAIDataFlywheelJudgeClient(
                client=client,
                judge_model=str(info["model"]),
            )
    except Exception:
        pass

    if not settings.ai_api_key:
        raise ValueError("JUDGE_CLIENT_NOT_CONFIGURED")

    try:
        from openai import OpenAI
    except ImportError as exc:
        raise ValueError("JUDGE_CLIENT_NOT_CONFIGURED") from exc

    return OpenAIDataFlywheelJudgeClient(
        client=OpenAI(api_key=settings.ai_api_key, base_url=settings.ai_base_url),
        judge_model=settings.ai_model,
    )


__all__ = ["router"]
