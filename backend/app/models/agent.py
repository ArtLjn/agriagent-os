"""Agent 相关数据库模型，存储建议与报告历史。"""

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, func

from app.core.database import Base


class AdviceRecord(Base):
    """农事建议记录，保存 Agent 生成的每日建议或问答回复。"""

    __tablename__ = "advice_records"

    id = Column(Integer, primary_key=True, index=True)
    farm_id = Column(Integer, ForeignKey("farms.id"), nullable=False, default=1)
    cycle_id = Column(Integer, ForeignKey("crop_cycles.id"), nullable=True)
    advice_type = Column(String, nullable=False)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class ReportRecord(Base):
    """周期报告记录，保存 Agent 生成的周报/月报。"""

    __tablename__ = "report_records"

    id = Column(Integer, primary_key=True, index=True)
    farm_id = Column(Integer, ForeignKey("farms.id"), nullable=False, default=1)
    cycle_id = Column(Integer, ForeignKey("crop_cycles.id"), nullable=True)
    report_type = Column(String, nullable=False)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
