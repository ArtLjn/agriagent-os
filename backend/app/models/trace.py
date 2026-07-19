"""执行链路追踪记录模型。"""

from datetime import datetime
from sqlalchemy import Column, DateTime, ForeignKey, Integer, JSON, String, Text
from app.shared.database import Base


class TraceRecord(Base):
    """一次 LLM/Skill 调用的详细记录。"""

    __tablename__ = "trace_records"

    id = Column(Integer, primary_key=True, autoincrement=True)
    request_id = Column(String(16), nullable=False, index=True)
    session_id = Column(String(64), nullable=True)
    farm_id = Column(Integer, ForeignKey("farms.id"), nullable=False)
    round_index = Column(Integer, default=0)
    node_type = Column(
        String(20), nullable=False
    )  # llm_call / skill_call / prompt_render
    node_name = Column(String(100), nullable=False)
    input_data = Column(JSON, nullable=True)
    output_data = Column(JSON, nullable=True)
    start_time = Column(DateTime, nullable=True)
    end_time = Column(DateTime, nullable=True)
    duration_ms = Column(Integer, nullable=True)
    token_usage = Column(JSON, nullable=True)
    status = Column(String(10), default="success")
    error_message = Column(Text, nullable=True)
    conversation_message_id = Column(
        Integer,
        ForeignKey("conversation_messages.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at = Column(DateTime, default=datetime.now)
