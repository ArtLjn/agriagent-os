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


def _infer_category(text: str) -> str:
    """根据首条用户消息推断会话分类。"""
    if any(
        keyword in text
        for keyword in ("天气", "降雨", "下雨", "温度", "打药", "施药", "风", "雨")
    ):
        return "天气"
    if any(
        keyword in text for keyword in ("病虫害", "虫", "病", "叶片", "发黄", "防治")
    ):
        return "病虫害"
    if any(keyword in text for keyword in ("报告", "周报", "月报", "总结")):
        return "报告"
    if any(
        keyword in text
        for keyword in ("记一笔", "记账", "成本", "收入", "支出", "人工", "费用")
    ):
        return "记账"
    if any(
        keyword in text for keyword in ("种植", "浇水", "施肥", "采摘", "播种", "定植")
    ):
        return "种植"
    return "对话"


def _build_conversation_summary(db: Session, session_id: str) -> tuple[str, str, str]:
    """从会话消息生成列表标题、预览和分类。"""
    messages = get_conversation_messages(db, session_id)
    if not messages:
        return (
            _DEFAULT_CONVERSATION_TITLE,
            _DEFAULT_CONVERSATION_PREVIEW,
            "对话",
        )
    first_user = next((message for message in messages if message.role == "user"), None)
    title_source = first_user.content if first_user else messages[0].content
    preview_source = messages[-1].content
    return (
        _truncate_text(title_source, 18),
        _truncate_text(preview_source, 24),
        _infer_category(title_source),
    )


def list_conversation_items(
    db: Session, farm: Farm, limit: int
) -> list[ConversationListItem]:
    """获取当前 farm 的会话列表。"""
    conversations = list_conversations(db, farm_id=farm.id, limit=limit)
    items: list[ConversationListItem] = []
    for c in conversations:
        title, preview, category = _build_conversation_summary(db, c.session_id)
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


def delete_report_item(db: Session, farm: Farm, report_id: int) -> None:
    """删除当前 farm 下的一条报告历史。"""
    record = (
        db.query(AgentRecord)
        .filter(AgentRecord.id == report_id, AgentRecord.farm_id == farm.id)
        .filter(AgentRecord.record_type.in_(["report", "weekly", "monthly"]))
        .first()
    )
    if record is None:
        raise ValueError("报告不存在")
    db.delete(record)
    db.commit()
