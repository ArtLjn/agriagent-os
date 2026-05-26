"""Agent API 路由，提供农事建议、对话和报告接口。"""

import json
import logging
import time
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from starlette.responses import Response
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_current_farm
from app.core.limiter import limiter
from app.core.llm import LlmNotConfiguredError
from app.core.logger import request_id_var
from app.models.agent import AdviceRecord
from app.models.farm import Farm
from app.schemas.agent import (
    ChatRequest,
    ChatResponse,
    DailyAdviceResponse,
    ReportRequest,
    ReportResponse,
    AdviceHistoryItem,
    ReportHistoryItem,
    ReportListResponse,
)
from app.services.agent_service import (
    chat_with_agent,
    stream_chat_with_agent,
    get_daily_advice,
    refresh_daily_advice,
    generate_report,
    get_advice_history,
    get_report_history,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/agent", tags=["agent"])


def _new_request_id() -> str:
    rid = uuid.uuid4().hex[:8]
    request_id_var.set(rid)
    return rid


@router.post("/chat", response_model=ChatResponse)
@limiter.limit("10/minute")
async def agent_chat(
    request: Request,
    response: Response,
    chat_request: ChatRequest,
    db: Session = Depends(get_db),
    farm: Farm = Depends(get_current_farm),
) -> ChatResponse:
    """与农事顾问 Agent 对话。"""
    rid = _new_request_id()
    logger.info(
        "[%s] POST /agent/chat | message=%s cycle_id=%s",
        rid,
        chat_request.message[:80],
        chat_request.cycle_id,
    )
    start = time.perf_counter()
    try:
        result = await chat_with_agent(
            db, chat_request.message, chat_request.cycle_id, farm_id=farm.id
        )
        logger.info(
            "[%s] /agent/chat 完成 | 耗时 %.2fs | reply %d 字符",
            rid,
            time.perf_counter() - start,
            len(result.reply),
        )
        return result
    except LlmNotConfiguredError as e:
        raise HTTPException(status_code=503, detail=str(e))


@router.post("/chat/stream")
@limiter.limit("10/minute")
async def agent_chat_stream(
    request: Request,
    response: Response,
    chat_request: ChatRequest,
    db: Session = Depends(get_db),
    farm: Farm = Depends(get_current_farm),
) -> StreamingResponse:
    """流式与农事顾问 Agent 对话（SSE）。"""
    rid = _new_request_id()
    logger.info(
        "[%s] POST /agent/chat/stream | message=%s", rid, chat_request.message[:80]
    )

    async def event_generator():
        full_reply = ""
        start = time.perf_counter()
        try:
            async for chunk in stream_chat_with_agent(
                chat_request.message, chat_request.cycle_id
            ):
                full_reply += chunk
                data = json.dumps({"content": chunk}, ensure_ascii=False)
                yield f"data: {data}\n\n"
            record = AdviceRecord(
                cycle_id=chat_request.cycle_id,
                advice_type="chat",
                content=full_reply,
                farm_id=farm.id,
            )
            db.add(record)
            db.commit()
            logger.info(
                "[%s] /chat/stream 完成 | 耗时 %.2fs | reply %d 字符",
                rid,
                time.perf_counter() - start,
                len(full_reply),
            )
        except LlmNotConfiguredError as exc:
            logger.error("[%s] /chat/stream 失败: %s", rid, exc)
            yield f"data: {json.dumps({'error': str(exc)}, ensure_ascii=False)}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/daily", response_model=DailyAdviceResponse)
@limiter.limit("10/minute")
async def daily_advice(
    request: Request,
    response: Response,
    cycle_id: int | None = Query(None, description="关联种植周期 ID"),
    db: Session = Depends(get_db),
    farm: Farm = Depends(get_current_farm),
) -> DailyAdviceResponse:
    """获取每日农事建议。"""
    rid = _new_request_id()
    logger.info("[%s] GET /agent/daily | cycle_id=%s", rid, cycle_id)
    start = time.perf_counter()
    try:
        result = await get_daily_advice(db, cycle_id, farm_id=farm.id)
        logger.info(
            "[%s] /agent/daily 完成 | 耗时 %.2fs", rid, time.perf_counter() - start
        )
        return result
    except LlmNotConfiguredError as e:
        raise HTTPException(status_code=503, detail=str(e))


@router.post("/daily/refresh", response_model=DailyAdviceResponse)
async def refresh_daily_advice_endpoint(
    cycle_id: int | None = Query(None, description="关联种植周期 ID"),
    db: Session = Depends(get_db),
    farm: Farm = Depends(get_current_farm),
) -> DailyAdviceResponse:
    """强制刷新每日农事建议。"""
    rid = _new_request_id()
    logger.info("[%s] POST /agent/daily/refresh | cycle_id=%s", rid, cycle_id)
    start = time.perf_counter()
    try:
        result = await refresh_daily_advice(db, cycle_id, farm_id=farm.id)
        logger.info(
            "[%s] /agent/daily/refresh 完成 | 耗时 %.2fs",
            rid,
            time.perf_counter() - start,
        )
        return result
    except LlmNotConfiguredError as e:
        raise HTTPException(status_code=503, detail=str(e))


@router.post("/report", response_model=ReportResponse)
@limiter.limit("10/minute")
async def agent_report(
    request: Request,
    response: Response,
    report_request: ReportRequest,
    db: Session = Depends(get_db),
    farm: Farm = Depends(get_current_farm),
) -> ReportResponse:
    """生成种植周期报告。"""
    rid = _new_request_id()
    logger.info(
        "[%s] POST /agent/report | type=%s cycle_id=%s",
        rid,
        report_request.report_type,
        report_request.cycle_id,
    )
    start = time.perf_counter()
    try:
        result = await generate_report(
            db, report_request.cycle_id, report_request.report_type, farm_id=farm.id
        )
        logger.info(
            "[%s] /agent/report 完成 | 耗时 %.2fs", rid, time.perf_counter() - start
        )
        return result
    except LlmNotConfiguredError as e:
        raise HTTPException(status_code=503, detail=str(e))


@router.get("/advice-history", response_model=list[AdviceHistoryItem])
@limiter.limit("10/minute")
def advice_history(
    request: Request,
    response: Response,
    cycle_id: int | None = Query(None, description="按周期筛选"),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    farm: Farm = Depends(get_current_farm),
) -> list[AdviceHistoryItem]:
    """查询建议历史记录。"""
    return get_advice_history(db, cycle_id, limit, farm_id=farm.id)


@router.get("/report-history", response_model=list[ReportHistoryItem])
@limiter.limit("10/minute")
def report_history(
    request: Request,
    response: Response,
    cycle_id: int | None = Query(None, description="按周期筛选"),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    farm: Farm = Depends(get_current_farm),
) -> list[ReportHistoryItem]:
    """查询报告历史记录。"""
    return get_report_history(db, cycle_id, limit, farm_id=farm.id)


@router.get("/reports", response_model=ReportListResponse)
async def list_reports(
    page: int = Query(1, ge=1),
    size: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db),
    farm: Farm = Depends(get_current_farm),
) -> ReportListResponse:
    """获取报告历史列表（支持分页）。"""
    from sqlalchemy import func as sqlfunc
    from app.models.agent import ReportRecord

    offset = (page - 1) * size
    query = db.query(ReportRecord).filter(ReportRecord.farm_id == farm.id)
    total = query.with_entities(sqlfunc.count(ReportRecord.id)).scalar() or 0
    records = (
        query.order_by(ReportRecord.created_at.desc()).offset(offset).limit(size).all()
    )
    items = [
        ReportHistoryItem(
            id=r.id,
            cycle_id=r.cycle_id,
            report_type=r.report_type,
            content=r.content,
            created_at=r.created_at,
        )
        for r in records
    ]
    return ReportListResponse(items=items, total=total)


__all__ = ["router"]
