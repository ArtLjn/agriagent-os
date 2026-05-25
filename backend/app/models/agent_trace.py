"""Agent 调用埋点模型 — 记录 LLM/Tool 调用耗时和 token。"""

from datetime import datetime

from sqlalchemy import Column, DateTime, Integer, String, Text

from app.core.database import Base


class AgentTrace(Base):
    """Agent 调用链路追踪。"""

    __tablename__ = "agent_traces"

    id = Column(Integer, primary_key=True, autoincrement=True)
    farm_id = Column(Integer, nullable=False)
    session_id = Column(String(64), nullable=True)
    node_type = Column(String(20), nullable=False)  # llm_call, tool_call
    node_name = Column(String(100), nullable=True)
    input_summary = Column(Text, nullable=True)
    output_summary = Column(Text, nullable=True)
    duration_ms = Column(Integer, nullable=True)
    tokens_used = Column(Integer, nullable=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.now)
