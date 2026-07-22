"""Task Context 持久化模型。"""

from datetime import datetime

from sqlalchemy import JSON, Column, DateTime, ForeignKey, Integer, String, Text

from app.shared.database import Base


class AgentTaskState(Base):
    """每个会话最近一个可恢复任务状态。"""

    __tablename__ = "agent_task_states"

    id = Column(Integer, primary_key=True, autoincrement=True)
    task_id = Column(String(64), nullable=False, unique=True, index=True)
    farm_id = Column(Integer, ForeignKey("farms.id"), nullable=False, index=True)
    user_id = Column(String(64), nullable=False, index=True)
    session_id = Column(String(64), nullable=False, index=True)
    task_type = Column(String(64), nullable=False, index=True)
    goal = Column(Text, nullable=False)
    entities_json = Column(JSON, nullable=False, default=dict)
    observations_json = Column(JSON, nullable=False, default=list)
    missing_information_json = Column(JSON, nullable=False, default=list)
    next_action = Column(Text, nullable=True)
    status = Column(String(20), nullable=False, default="active", index=True)
    expires_at = Column(DateTime, nullable=True, index=True)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)


__all__ = ["AgentTaskState"]
