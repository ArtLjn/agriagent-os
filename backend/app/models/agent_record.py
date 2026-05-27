"""Agent 输出记录模型 — 合并 advice_records + report_records。"""

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, func

from app.core.database import Base


class AgentRecord(Base):
    """Agent 输出统一记录。"""

    __tablename__ = "agent_records"

    id = Column(Integer, primary_key=True, index=True)
    farm_id = Column(Integer, ForeignKey("farms.id"), nullable=False)
    user_id = Column(String(36), nullable=True)
    conversation_id = Column(Integer, ForeignKey("conversations.id"), nullable=True)
    cycle_id = Column(Integer, ForeignKey("crop_cycles.id"), nullable=True)
    record_type = Column(String(20), nullable=False)  # chat / daily / report
    content = Column(Text, nullable=False)
    meta = Column(Text, nullable=True)  # JSON: token_usage, latency_ms 等
    created_at = Column(DateTime(timezone=True), server_default=func.now())
