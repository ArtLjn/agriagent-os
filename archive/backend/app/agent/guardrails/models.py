"""Guardrails 拦截日志模型。"""

from datetime import datetime

from sqlalchemy import Column, DateTime, Integer, String, Text

from app.shared.database import Base


class GuardrailsLog(Base):
    """Guardrails 拦截日志。"""

    __tablename__ = "guardrails_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    farm_id = Column(Integer, nullable=False)
    trigger_type = Column(String(50), nullable=False)
    trigger_detail = Column(Text, nullable=True)
    source_text = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.now)
