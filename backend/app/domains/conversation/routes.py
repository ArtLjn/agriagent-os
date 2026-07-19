"""Agent API 路由，提供农事建议、对话和报告接口。"""

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from starlette.responses import Response
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.shared.database import get_db
from app.domains.users.dependencies import get_current_user
from app.domains.farm.dependencies import get_current_farm
from app.domains.users.models import User
from app.infra.limiter import limiter
from app.shared.llm import LlmNotConfiguredError
from app.domains.farm.models import Farm
from app.application.chat.use_case import chat, new_request_id
from app.application.advice.use_case import (
    create_report,
    get_daily,
    refresh_daily,
)
from app.application.session.history import (
    delete_report_item,
    list_conversation_items,
    list_message_items,
    list_report_history_items,
    list_report_page,
)
from app.application.skill_catalog import list_app_skills
from app.application.chat.stream_chat import (
    resolve_stream_user_and_farm,
    stream_chat_events,
)
from app.domains.conversation.agent_schemas import (
    ChatRequest,
    ChatResponse,
    DailyAdviceResponse,
    ReportRequest,
    ReportResponse,
    AdviceHistoryItem,
    ReportHistoryItem,
    ReportListResponse,
    ConversationListItem,
    ConversationMessageItem,
    AppSkillListResponse,
)
from app.domains.conversation.agent_service import (
    get_advice_history,
)
from app.domains.conversation.service import ConversationAccessError
from app.domains.conversation.session_debug_export_service import build_session_debug_export


router = APIRouter(prefix="/agent", tags=["agent"])


@router.get("/skills", response_model=AppSkillListResponse)
def list_agent_skills(
    _current_user: User = Depends(get_current_user),
) -> AppSkillListResponse:
    """列出 App 端可展示的技能能力。"""
    items = list_app_skills()
    return AppSkillListResponse(items=items, total=len(items))


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
    rid = new_request_id()
    try:
        return await chat(db, chat_request, farm, request_id=rid)
    except ConversationAccessError as e:
        raise HTTPException(status_code=404, detail=str(e))
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
    user, farm = resolve_stream_user_and_farm(
        db, current_user, chat_request.simulate_user_id
    )
    rid = new_request_id()

    return StreamingResponse(
        stream_chat_events(db, chat_request, user, farm, request_id=rid),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/conversations", response_model=list[ConversationListItem])
@limiter.limit("30/minute")
def get_conversations(
    request: Request,
    response: Response,
    limit: int = Query(20, ge=1, le=100),
    simulate_user_id: str | None = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    farm: Farm = Depends(get_current_farm),
) -> list[ConversationListItem]:
    """获取当前 farm 的会话列表。"""
    if simulate_user_id:
        _, farm = resolve_stream_user_and_farm(db, current_user, simulate_user_id)
    return list_conversation_items(db, farm=farm, limit=limit)


@router.get(
    "/conversations/{session_id}/messages",
    response_model=list[ConversationMessageItem],
)
@limiter.limit("30/minute")
def get_messages_by_session(
    request: Request,
    response: Response,
    session_id: str,
    simulate_user_id: str | None = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    farm: Farm = Depends(get_current_farm),
) -> list[ConversationMessageItem]:
    """获取指定会话的消息列表。"""
    try:
        if simulate_user_id:
            _, farm = resolve_stream_user_and_farm(db, current_user, simulate_user_id)
        return list_message_items(db, farm=farm, session_id=session_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/conversations/{session_id}/debug-export")
@limiter.limit("10/minute")
def get_session_debug_export(
    request: Request,
    response: Response,
    session_id: str,
    simulate_user_id: str | None = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    farm: Farm = Depends(get_current_farm),
) -> dict:
    """导出会话调试 JSON v2。"""
    if simulate_user_id:
        _, farm = resolve_stream_user_and_farm(db, current_user, simulate_user_id)
    return build_session_debug_export(db, farm_id=farm.id, session_id=session_id)


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
    try:
        return await get_daily(db, farm, cycle_id)
    except LlmNotConfiguredError as e:
        raise HTTPException(status_code=503, detail=str(e))


@router.post("/daily/refresh", response_model=DailyAdviceResponse)
async def refresh_daily_advice_endpoint(
    cycle_id: int | None = Query(None, description="关联种植周期 ID"),
    db: Session = Depends(get_db),
    farm: Farm = Depends(get_current_farm),
) -> DailyAdviceResponse:
    """强制刷新每日农事建议。"""
    try:
        return await refresh_daily(db, farm, cycle_id)
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
    try:
        return await create_report(db, farm, report_request)
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
    return list_report_history_items(db, farm=farm, cycle_id=cycle_id, limit=limit)


@router.get("/reports", response_model=ReportListResponse)
def list_reports(
    page: int = Query(1, ge=1),
    size: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db),
    farm: Farm = Depends(get_current_farm),
) -> ReportListResponse:
    """获取报告历史列表（支持分页）。"""
    return list_report_page(db, farm=farm, page=page, size=size)


@router.delete("/reports/{report_id}")
def delete_report(
    report_id: int,
    db: Session = Depends(get_db),
    farm: Farm = Depends(get_current_farm),
):
    """删除报告历史。"""
    try:
        delete_report_item(db, farm=farm, report_id=report_id)
        return {"message": "删除成功"}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


__all__ = ["router"]
