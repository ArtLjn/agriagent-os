"""Agent 数据飞轮存储模型。"""

from datetime import datetime

from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, JSON, String, Text

from app.core.database import Base


class AgentDataFlywheelLabel(Base):
    """管理员对 Agent 样本的标注记录。"""

    __tablename__ = "agent_data_flywheel_labels"

    id = Column(Integer, primary_key=True, autoincrement=True)
    farm_id = Column(Integer, ForeignKey("farms.id"), nullable=False, index=True)
    sample_id = Column(String(160), nullable=False, index=True)
    sample_type = Column(String(40), nullable=False, index=True)
    session_id = Column(String(64), nullable=True, index=True)
    turn_id = Column(Integer, nullable=True, index=True)
    request_id = Column(String(32), nullable=True, index=True)
    label = Column(String(64), nullable=False, index=True)
    status = Column(String(20), nullable=False, default="open", index=True)
    comment = Column(Text, nullable=True)
    annotator_id = Column(String(64), nullable=True, index=True)
    created_at = Column(DateTime, default=datetime.now, nullable=False, index=True)
    updated_at = Column(
        DateTime,
        default=datetime.now,
        onupdate=datetime.now,
        nullable=False,
    )


class AgentDataFlywheelPrelabel(Base):
    """LLM judge 对 Agent 样本的自动预标注记录。"""

    __tablename__ = "agent_data_flywheel_prelabels"

    id = Column(Integer, primary_key=True, autoincrement=True)
    farm_id = Column(Integer, ForeignKey("farms.id"), nullable=False, index=True)
    sample_id = Column(String(160), nullable=False, index=True)
    sample_type = Column(String(40), nullable=False, index=True)
    session_id = Column(String(64), nullable=True, index=True)
    turn_id = Column(Integer, nullable=True, index=True)
    request_id = Column(String(32), nullable=True, index=True)
    source = Column(String(32), nullable=False, default="llm_judge", index=True)
    status = Column(String(20), nullable=False, default="pending", index=True)
    labels = Column(JSON, nullable=False)
    root_cause = Column(Text, nullable=True)
    severity = Column(String(20), nullable=False, index=True)
    confidence = Column(Float, nullable=False, default=0.0)
    reason = Column(Text, nullable=False)
    recommended_fix = Column(Text, nullable=True)
    judge_model = Column(String(80), nullable=False, index=True)
    prompt_version = Column(String(80), nullable=False, index=True)
    raw_response = Column(JSON, nullable=True)
    accepted_label_ids = Column(JSON, nullable=True)
    reviewed_by = Column(String(64), nullable=True, index=True)
    reviewed_at = Column(DateTime, nullable=True, index=True)
    created_at = Column(DateTime, default=datetime.now, nullable=False, index=True)
    updated_at = Column(
        DateTime, default=datetime.now, onupdate=datetime.now, nullable=False
    )


class AgentCaseDraft(Base):
    """从标注样本生成的评测用例草稿。"""

    __tablename__ = "agent_case_drafts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    farm_id = Column(Integer, ForeignKey("farms.id"), nullable=False, index=True)
    draft_id = Column(String(64), unique=True, nullable=False, index=True)
    source_sample_id = Column(String(160), nullable=False, index=True)
    target_type = Column(String(32), nullable=False, index=True)
    status = Column(String(20), nullable=False, default="draft", index=True)
    case_json = Column(JSON, nullable=False)
    created_by = Column(String(64), nullable=True, index=True)
    created_at = Column(DateTime, default=datetime.now, nullable=False, index=True)
    updated_at = Column(
        DateTime,
        default=datetime.now,
        onupdate=datetime.now,
        nullable=False,
    )
