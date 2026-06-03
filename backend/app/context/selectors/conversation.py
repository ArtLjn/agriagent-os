"""会话历史 selector。"""

from sqlalchemy.orm import Session

from app.context.models import ContextBlock
from app.models.conversation import Conversation, ConversationMessage


class ConversationSelector:
    """选择最近对话。"""

    def select(
        self,
        db: Session | None = None,
        farm_id: int | None = None,
        session_id: str | None = None,
        messages: list[str] | None = None,
        **_kwargs,
    ) -> list[ContextBlock]:
        lines = messages or []
        if not lines and db is not None and farm_id is not None:
            query = db.query(Conversation).filter(Conversation.farm_id == farm_id)
            if session_id:
                query = query.filter(Conversation.session_id == session_id)
            conversation = query.order_by(Conversation.last_active_at.desc()).first()
            if conversation:
                rows = (
                    db.query(ConversationMessage)
                    .filter(ConversationMessage.conversation_id == conversation.id)
                    .order_by(ConversationMessage.id.desc())
                    .limit(6)
                    .all()
                )
                lines = [
                    f"{row.role}：{row.content}"
                    for row in reversed(rows)
                    if row.content
                ]

        if not lines:
            return []
        return [
            ContextBlock(
                key="conversation",
                source="conversation",
                purpose="最近对话",
                content="\n".join(lines),
                priority=55,
                compressible=True,
                min_tokens=40,
            )
        ]


__all__ = ["ConversationSelector"]
