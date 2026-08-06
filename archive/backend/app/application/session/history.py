"""Agent 历史记录 use case。"""

import json

from sqlalchemy.orm import Session

from app.infra.repository_runtime import (
    get_agent_record_repository,
    run_maybe_awaitable,
)
from app.domains.conversation.models import Conversation
from app.domains.farm.models import Farm
from app.domains.conversation.agent_schemas import (
    ConversationListItem,
    ConversationMessageItem,
    PendingActionResponse,
    PendingPlanResponse,
    ReportHistoryItem,
    ReportListResponse,
)
from app.domains.conversation.agent_service import get_report_history
from app.domains.conversation.service import (
    get_conversation_by_session,
    get_conversation_messages,
    list_conversations,
)

_DEFAULT_CONVERSATION_TITLE = "历史对话"
_DEFAULT_CONVERSATION_PREVIEW = "点击查看这轮农事对话"


def _truncate_text(text: str, limit: int) -> str:
    """按字符长度截断展示文本。"""
    clean_text = " ".join(text.split()).strip()
    if len(clean_text) <= limit:
        return clean_text
    return f"{clean_text[:limit]}..."


def _build_conversation_summary(
    conversation: Conversation,
) -> tuple[str, str, str]:
    """从会话元数据生成列表标题、预览和分类。"""
    meta = conversation.meta_json if conversation else None
    if isinstance(meta, dict):
        title = meta.get("title")
        preview = meta.get("preview")
        category = meta.get("category")
        if title and preview and category:
            return str(title), str(preview), str(category)
    if conversation and conversation.summary:
        return (
            _truncate_text(conversation.summary, 18),
            _truncate_text(conversation.summary, 24),
            "对话",
        )
    return (
        _DEFAULT_CONVERSATION_TITLE,
        _DEFAULT_CONVERSATION_PREVIEW,
        "对话",
    )


def list_conversation_items(
    db: Session, farm: Farm, limit: int
) -> list[ConversationListItem]:
    """获取当前 farm 的会话列表。"""
    conversations = list_conversations(db, farm_id=farm.id, limit=limit)
    items: list[ConversationListItem] = []
    for c in conversations:
        summary = _build_conversation_summary(c)
        title, preview, category = summary
        items.append(
            ConversationListItem(
                id=c.id,
                session_id=c.session_id,
                status=c.status,
                title=title,
                preview=preview,
                category=category,
                created_at=c.created_at,
                last_active_at=c.last_active_at,
            )
        )
    return items


def list_message_items(
    db: Session, farm: Farm, session_id: str
) -> list[ConversationMessageItem]:
    """获取指定会话的消息列表。"""
    conversation = get_conversation_by_session(db, session_id, farm_id=farm.id)
    if conversation is None:
        raise ValueError("会话不存在")
    messages = get_conversation_messages(db, session_id, farm_id=farm.id)
    result = []
    for message in messages:
        skills = None
        pending_action = None
        pending_plan = None
        meta_obj = message.meta_json if isinstance(message.meta_json, dict) else None
        if meta_obj is None and message.meta:
            try:
                parsed = json.loads(message.meta)
                if isinstance(parsed, dict):
                    meta_obj = parsed
            except (json.JSONDecodeError, AttributeError):
                meta_obj = None
        if meta_obj:
            skills = meta_obj.get("skills")
            pending_raw = meta_obj.get("pending_action")
            if pending_raw:
                pending_action = PendingActionResponse.model_validate(pending_raw)
            pending_plan_raw = meta_obj.get("pending_plan")
            if pending_plan_raw:
                pending_plan = PendingPlanResponse.model_validate(pending_plan_raw)
        result.append(
            ConversationMessageItem(
                id=message.id,
                role=message.role,
                content=message.content,
                skills=skills,
                pending_action=pending_action,
                pending_plan=pending_plan,
                created_at=message.created_at,
            )
        )
    return result


def parse_structured_data(meta: str | None) -> dict | None:
    """从 meta 字段解析结构化数据。"""
    if not meta:
        return None
    try:
        parsed = json.loads(meta)
    except (json.JSONDecodeError, TypeError):
        return None
    if not isinstance(parsed, dict):
        return None

    structured_data = parsed.get("structured_data")
    if isinstance(structured_data, dict):
        parsed = structured_data

    if "overview" in parsed:
        return parsed
    if all(key in parsed for key in ("period", "sections", "source_refs")):
        return parsed
    return None


def list_report_history_items(
    db: Session, farm: Farm, cycle_id: int | None, limit: int
) -> list[ReportHistoryItem]:
    """查询报告历史记录。"""
    records = get_report_history(db, farm_id=farm.id, cycle_id=cycle_id, limit=limit)
    return [
        ReportHistoryItem(
            id=record.id,
            cycle_id=record.cycle_id,
            report_type=record.record_type,
            content=record.content,
            structured_data=parse_structured_data(record.meta),
            created_at=record.created_at,
        )
        for record in records
    ]


def list_report_page(
    db: Session, farm: Farm, page: int, size: int
) -> ReportListResponse:
    """获取报告历史分页列表。"""
    page_data = run_maybe_awaitable(
        get_agent_record_repository(db).list_report_page(
            farm_id=farm.id,
            page=page,
            size=size,
        )
    )
    items = [
        ReportHistoryItem(
            id=record.id,
            cycle_id=record.cycle_id,
            report_type=record.record_type,
            content=record.content,
            structured_data=parse_structured_data(record.meta),
            created_at=record.created_at,
        )
        for record in page_data.items
    ]
    return ReportListResponse(items=items, total=page_data.total)


def delete_report_item(db: Session, farm: Farm, report_id: int) -> None:
    """删除当前 farm 下的一条报告历史。"""
    record = run_maybe_awaitable(
        get_agent_record_repository(db).get_report_by_id(
            farm_id=farm.id,
            report_id=report_id,
        )
    )
    if record is None:
        raise ValueError("报告不存在")
    deleted = run_maybe_awaitable(
        get_agent_record_repository(db).delete_report(
            farm_id=farm.id,
            report_id=report_id,
        )
    )
    if not deleted:
        raise ValueError("报告不存在")
