"""Agent Pending Plan 持久化模型。"""

from sqlalchemy import Column, DateTime, ForeignKey, Integer, JSON, String, Text, func
from sqlalchemy.orm import relationship

from app.core.database import Base


class AgentPendingPlan(Base):
    """等待确认或后续执行的 Agent 计划。"""

    __tablename__ = "agent_pending_plans"

    id = Column(Integer, primary_key=True, index=True)
    plan_id = Column(String(64), nullable=False, unique=True, index=True)
    farm_id = Column(Integer, ForeignKey("farms.id"), nullable=False, index=True)
    session_id = Column(String(64), nullable=True, index=True)
    status = Column(String(32), nullable=False, default="pending")
    current_step_index = Column(Integer, nullable=False, default=0)
    raw_user_input = Column(Text, nullable=False)
    router_decision = Column(JSON, nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    steps = relationship(
        "AgentPendingPlanStep",
        back_populates="plan",
        cascade="all, delete-orphan",
        order_by="AgentPendingPlanStep.step_index",
    )


class AgentPendingPlanStep(Base):
    """Agent Pending Plan 的单个工具调用步骤。"""

    __tablename__ = "agent_pending_plan_steps"

    id = Column(Integer, primary_key=True, index=True)
    plan_id = Column(
        Integer,
        ForeignKey("agent_pending_plans.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    step_id = Column(String(64), nullable=False)
    step_index = Column(Integer, nullable=False)
    tool_name = Column(String(100), nullable=False)
    params = Column(JSON, nullable=False)
    depends_on = Column(JSON, nullable=False, default=list)
    confirmation_state = Column(String(32), nullable=False, default="pending")
    execution_status = Column(String(32), nullable=False, default="pending")
    result_payload = Column(JSON, nullable=True)
    error_payload = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    plan = relationship("AgentPendingPlan", back_populates="steps")
