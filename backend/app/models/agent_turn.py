"""Agent 单轮对话聚合模型。"""

from datetime import datetime

from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, JSON, String, Text

from app.core.database import Base


class AgentTurn(Base):
    """一轮用户输入到助手回复的轻量聚合记录。"""

    __tablename__ = "agent_turns"

    id = Column(Integer, primary_key=True, autoincrement=True)
    farm_id = Column(Integer, ForeignKey("farms.id"), nullable=False, index=True)
    session_id = Column(String(64), nullable=False, index=True)
    conversation_id = Column(
        Integer,
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    request_id = Column(String(16), nullable=False, index=True)
    user_message_id = Column(
        Integer,
        ForeignKey("conversation_messages.id", ondelete="SET NULL"),
        nullable=True,
    )
    assistant_message_id = Column(
        Integer,
        ForeignKey("conversation_messages.id", ondelete="SET NULL"),
        nullable=True,
    )
    input_preview = Column(Text, nullable=True)
    reply_preview = Column(Text, nullable=True)
    intent_count = Column(Integer, nullable=True)
    selected_tools_count = Column(Integer, nullable=True)
    tool_calls_count = Column(Integer, nullable=True)
    token_total = Column(Integer, nullable=True)
    latency_ms = Column(Integer, nullable=True)
    status = Column(String(20), nullable=False, default="success")
    pending_plan_id = Column(String(64), nullable=True, index=True)
    event_file = Column(Text, nullable=True)
    event_seq_start = Column(Integer, nullable=True)
    event_seq_end = Column(Integer, nullable=True)
    event_write_status = Column(String(20), nullable=False, default="not_started")
    rule_score = Column(Float, nullable=False, default=0.0)
    rule_hits = Column(JSON, nullable=False, default=list)
    risk_score = Column(Float, nullable=False, default=0.0, index=True)
    risk_dominant_signal = Column(String(20), nullable=True, index=True)
    risk_severity = Column(String(10), nullable=True, index=True)
    judge_bad_prob = Column(Float, nullable=True)
    judge_issue_type = Column(String(80), nullable=True, index=True)
    judge_suggested_label = Column(String(80), nullable=True)
    created_at = Column(DateTime, default=datetime.now, index=True)
