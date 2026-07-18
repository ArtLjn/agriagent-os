"""可恢复 pending plan 模型。"""

from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import relationship

from app.shared.database import Base


class AgentPendingPlan(Base):
    """一次或多次写操作组成的待确认计划。"""

    __tablename__ = "agent_pending_plans"

    id = Column(Integer, primary_key=True, autoincrement=True)
    plan_id = Column(String(64), nullable=False, unique=True, index=True)
    farm_id = Column(Integer, ForeignKey("farms.id"), nullable=False, index=True)
    session_id = Column(String(64), nullable=True, index=True)
    status = Column(String(20), nullable=False, default="pending", index=True)
    current_step_index = Column(Integer, nullable=False, default=0)
    raw_user_input = Column(Text, nullable=True)
    router_decision = Column(JSON, nullable=True)
    router_decision_json = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.now)
    expires_at = Column(DateTime, nullable=True, index=True)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    steps = relationship(
        "AgentPendingPlanStep",
        back_populates="plan",
        cascade="all, delete-orphan",
        primaryjoin="AgentPendingPlan.plan_id == foreign(AgentPendingPlanStep.plan_id)",
        order_by="AgentPendingPlanStep.step_index",
    )


class AgentPendingPlanStep(Base):
    """pending plan 中的单个执行步骤。"""

    __tablename__ = "agent_pending_plan_steps"

    id = Column(Integer, primary_key=True, autoincrement=True)
    plan_id = Column(String(64), nullable=False, index=True)
    step_id = Column(String(64), nullable=True)
    step_index = Column(Integer, nullable=False)
    tool_name = Column(String(100), nullable=True)
    skill_name = Column(String(100), nullable=False, index=True)
    params = Column(JSON, nullable=True)
    params_json = Column(JSON, nullable=False)
    depends_on = Column(JSON, nullable=True, default=list)
    confirmation_state = Column(String(32), nullable=True)
    execution_status = Column(String(32), nullable=True)
    status = Column(String(20), nullable=False, default="pending", index=True)
    requires_confirmation = Column(Boolean, nullable=False, default=True)
    confirmation_text = Column(Text, nullable=True)
    result_payload = Column(JSON, nullable=True)
    error_payload = Column(JSON, nullable=True)
    result_json = Column(JSON, nullable=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    plan = relationship(
        "AgentPendingPlan",
        back_populates="steps",
        primaryjoin="foreign(AgentPendingPlanStep.plan_id) == AgentPendingPlan.plan_id",
    )
