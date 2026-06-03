"""Agent 历史记录 use case。"""

import json

from sqlalchemy import func as sqlfunc
from sqlalchemy.orm import Session

from app.models.agent_record import AgentRecord
from app.models.farm import Farm
from app.schemas.agent import (
    ConversationListItem,
    ConversationMessageItem,
    ReportHistoryItem,
    ReportListResponse,
)
from app.services.agent_service import get_report_history
from app.services.conversation_service import (
    get_conversation_messages,
    list_conversations,
)


def list_conversation_items(
    db: Session, farm: Farm, limit: int
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


def list_message_items(db: Session, session_id: str) -> list[ConversationMessageItem]:
    """获取指定会话的消息列表。"""
    messages = get_conversation_messages(db, session_id)
    result = []
    for message in messages:
        skills = None
        if message.meta:
            try:
                meta_obj = json.loads(message.meta)
                skills = meta_obj.get("skills")
            except (json.JSONDecodeError, AttributeError):
                pass
        result.append(
            ConversationMessageItem(
                id=message.id,
                role=message.role,
                content=message.content,
                skills=skills,
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
        if isinstance(parsed, dict) and "overview" in parsed:
            return parsed
    except (json.JSONDecodeError, TypeError):
        pass
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
    offset = (page - 1) * size
    query = db.query(AgentRecord).filter(AgentRecord.farm_id == farm.id)
    query = query.filter(AgentRecord.record_type.in_(["report", "weekly", "monthly"]))
    total = query.with_entities(sqlfunc.count(AgentRecord.id)).scalar() or 0
    records = (
        query.order_by(AgentRecord.created_at.desc()).offset(offset).limit(size).all()
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
        for record in records
    ]
    return ReportListResponse(items=items, total=total)
