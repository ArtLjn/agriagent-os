"""Agent API 路由，提供农事建议、对话和报告接口。"""

import json
import logging
import time
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from starlette.responses import Response
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_current_farm, get_current_user
from app.models.user import User
from app.infra.limiter import limiter
from app.agent.llm import LlmNotConfiguredError
from app.core.logger import request_id_var
from app.models.agent_record import AgentRecord
from app.models.conversation import Conversation
from app.models.farm import Farm
from app.models.trace import TraceRecord
from app.schemas.agent import (
    ChatRequest,
    ChatResponse,
    DailyAdviceResponse,
    PendingActionContext,
    PendingActionResponse,
    ReportRequest,
    ReportResponse,
    AdviceHistoryItem,
    ReportHistoryItem,
    ReportListResponse,
    ConversationListItem,
    ConversationMessageItem,
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
from app.services.conversation_service import (
    list_conversations,
    get_conversation_messages,
    save_message,
)
from app.infra.pending_actions import get_pending

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
            db,
            chat_request.message,
            farm_id=farm.id,
            cycle_id=chat_request.cycle_id,
            session_id=chat_request.session_id,
            request_id=rid,
        )
        # 非流式端点也需要返回 pending_action（供仿真测试等调用方使用）
        pending = get_pending(farm.id)
        if pending:
            notes = []
            if pending.original_input:
                notes.append(f"理解：您说的是「{pending.original_input}」")
            result.pending_action = PendingActionResponse(
                action_id=pending.action_id,
                skill_name=pending.skill_name,
                params=pending.params,
                context=PendingActionContext(
                    original_input=pending.original_input,
                    extracted_params=pending.params,
                    notes=notes,
                ),
            )
        logger.info(
            "[%s] /agent/chat 完成 | 耗时 %.2fs | reply %d 字符 | pending=%s",
            rid,
            time.perf_counter() - start,
            len(result.reply),
            bool(pending),
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
    current_user: User = Depends(get_current_user),
) -> StreamingResponse:
    """流式与农事顾问 Agent 对话（SSE）。支持管理员模拟其他用户身份。"""
    # 确定实际用户和农场
    user = current_user
    if chat_request.simulate_user_id:
        if current_user.role != "admin":
            raise HTTPException(status_code=403, detail="需要管理员权限才能模拟用户")
        simulated = (
            db.query(User).filter(User.id == chat_request.simulate_user_id).first()
        )
        if not simulated:
            raise HTTPException(status_code=404, detail="模拟用户不存在")
        user = simulated

    farm = db.query(Farm).filter(Farm.user_id == user.id).first()
    if farm is None:
        raise HTTPException(status_code=404, detail="未找到关联农场")

    rid = _new_request_id()
    logger.info(
        "[%s] POST /agent/chat/stream | message=%s simulate_user=%s",
        rid,
        chat_request.message[:80],
        chat_request.simulate_user_id,
    )

    async def event_generator():
        full_reply = ""
        start = time.perf_counter()
        try:
            async for chunk in stream_chat_with_agent(
                chat_request.message,
                farm_id=farm.id,
                cycle_id=chat_request.cycle_id,
                db=db,
                session_id=chat_request.session_id,
                user_id=user.id,
                request_id=rid,
            ):
                full_reply += chunk
                data = json.dumps({"content": chunk}, ensure_ascii=False)
                yield f"data: {data}\n\n"

            # flush trace 队列确保 skill_call 记录已落盘
            from app.infra.trace_collector import get_trace_dao

            dao = get_trace_dao()
            if dao and dao.queue_size > 0:
                await dao.flush_now()

            # 查询本次对话调用的 skill 列表
            skills = (
                db.query(TraceRecord.node_name)
                .filter(TraceRecord.request_id == rid)
                .filter(TraceRecord.node_type == "skill_call")
                .distinct()
                .all()
            )
            skill_names = [s[0] for s in skills if s[0]]

            # 保存 AI 回复到 conversation_messages + AgentRecord
            conversation = None
            if chat_request.session_id:
                conversation = (
                    db.query(Conversation)
                    .filter(Conversation.session_id == chat_request.session_id)
                    .first()
                )
                if conversation:
                    meta = (
                        json.dumps({"skills": skill_names}, ensure_ascii=False)
                        if skill_names
                        else None
                    )
                    save_message(
                        db, conversation.id, "assistant", full_reply, meta=meta
                    )

            record = AgentRecord(
                cycle_id=chat_request.cycle_id,
                record_type="chat",
                content=full_reply,
                farm_id=farm.id,
                user_id=user.id,
                conversation_id=conversation.id if conversation else None,
            )
            db.add(record)
            db.commit()

            if skill_names:
                yield f"data: {json.dumps({'skills': skill_names}, ensure_ascii=False)}\n\n"

            pending = get_pending(farm.id)
            if pending:
                notes = []
                if pending.original_input:
                    notes.append(f"理解：您说的是「{pending.original_input}」")
                pa_event = json.dumps(
                    {
                        "pending_action": {
                            "action_id": pending.action_id,
                            "skill_name": pending.skill_name,
                            "params": pending.params,
                            "context": {
                                "original_input": pending.original_input,
                                "extracted_params": pending.params,
                                "notes": notes,
                            },
                        }
                    },
                    ensure_ascii=False,
                )
                logger.info(
                    "[%s] 发送 pending_action SSE 事件 | skill=%s",
                    rid,
                    pending.skill_name,
                )
                yield f"data: {pa_event}\n\n"

            logger.info(
                "[%s] /chat/stream 完成 | 耗时 %.2fs | reply %d 字符 | skills=%s",
                rid,
                time.perf_counter() - start,
                len(full_reply),
                skill_names,
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


@router.get("/conversations", response_model=list[ConversationListItem])
@limiter.limit("30/minute")
def get_conversations(
    request: Request,
    response: Response,
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    farm: Farm = Depends(get_current_farm),
) -> list[ConversationListItem]:
    """获取当前 farm 的会话列表。"""
    conversations = list_conversations(db, farm_id=farm.id, limit=limit)
    return [
        ConversationListItem(
            id=c.id,
            session_id=c.session_id,
            status=c.status,
            created_at=c.created_at,
            last_active_at=c.last_active_at,
        )
        for c in conversations
    ]


@router.get(
    "/conversations/{session_id}/messages",
    response_model=list[ConversationMessageItem],
)
@limiter.limit("30/minute")
def get_messages_by_session(
    request: Request,
    response: Response,
    session_id: str,
    db: Session = Depends(get_db),
    farm: Farm = Depends(get_current_farm),
) -> list[ConversationMessageItem]:
    """获取指定会话的消息列表。"""
    messages = get_conversation_messages(db, session_id)
    result = []
    for m in messages:
        skills = None
        if m.meta:
            try:
                meta_obj = json.loads(m.meta)
                skills = meta_obj.get("skills")
            except (json.JSONDecodeError, AttributeError):
                pass
        result.append(
            ConversationMessageItem(
                id=m.id,
                role=m.role,
                content=m.content,
                skills=skills,
                created_at=m.created_at,
            )
        )
    return result


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
        result = await get_daily_advice(db, farm_id=farm.id, cycle_id=cycle_id)
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
        result = await refresh_daily_advice(db, farm_id=farm.id, cycle_id=cycle_id)
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
            db,
            farm_id=farm.id,
            cycle_id=report_request.cycle_id,
            report_type=report_request.report_type,
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
    return get_advice_history(db, farm_id=farm.id, cycle_id=cycle_id, limit=limit)


def _parse_structured_data(meta: str | None) -> dict | None:
    """从 meta 字段解析结构化数据。"""
    if not meta:
        return None
    try:
        import json
        parsed = json.loads(meta)
        if isinstance(parsed, dict) and "overview" in parsed:
            return parsed
    except (json.JSONDecodeError, TypeError):
        pass
    return None


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
    records = get_report_history(
        db, farm_id=farm.id, cycle_id=cycle_id, limit=limit
    )
    return [
        ReportHistoryItem(
            id=r.id,
            cycle_id=r.cycle_id,
            report_type=r.record_type,
            content=r.content,
            structured_data=_parse_structured_data(r.meta),
            created_at=r.created_at,
        )
        for r in records
    ]


@router.get("/reports", response_model=ReportListResponse)
async def list_reports(
    page: int = Query(1, ge=1),
    size: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db),
    farm: Farm = Depends(get_current_farm),
) -> ReportListResponse:
    """获取报告历史列表（支持分页）。"""
    from sqlalchemy import func as sqlfunc

    offset = (page - 1) * size
    query = db.query(AgentRecord).filter(AgentRecord.farm_id == farm.id)
    query = query.filter(AgentRecord.record_type.in_(["report", "weekly", "monthly"]))
    total = query.with_entities(sqlfunc.count(AgentRecord.id)).scalar() or 0
    records = (
        query.order_by(AgentRecord.created_at.desc()).offset(offset).limit(size).all()
    )
    items = [
        ReportHistoryItem(
            id=r.id,
            cycle_id=r.cycle_id,
            report_type=r.record_type,
            content=r.content,
            structured_data=_parse_structured_data(r.meta),
            created_at=r.created_at,
        )
        for r in records
    ]
    return ReportListResponse(items=items, total=total)


__all__ = ["router"]
