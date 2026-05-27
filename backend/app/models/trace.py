"""执行链路追踪记录模型。"""

from datetime import datetime
from sqlalchemy import Column, DateTime, Integer, String, Text
from app.core.database import Base


class TraceRecord(Base):
    """一次 LLM/Skill 调用的详细记录。"""

    __tablename__ = "trace_records"

    id = Column(Integer, primary_key=True, autoincrement=True)
    request_id = Column(String(16), nullable=False, index=True)
    session_id = Column(String(64), nullable=True)
    farm_id = Column(Integer, nullable=False)
    round_index = Column(Integer, default=0)
    node_type = Column(
        String(20), nullable=False
    )  # llm_call / skill_call / prompt_render
    node_name = Column(String(100), nullable=False)
    input_data = Column(Text, nullable=True)  # JSON
    output_data = Column(Text, nullable=True)  # JSON，截断到 4000 字符
    start_time = Column(String(32), nullable=True)  # ISO 格式
    end_time = Column(String(32), nullable=True)
    duration_ms = Column(Integer, nullable=True)
    token_usage = Column(Text, nullable=True)  # JSON: {prompt, completion, total}
    status = Column(String(10), default="success")
    error_message = Column(Text, nullable=True)
    conversation_message_id = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.now)
