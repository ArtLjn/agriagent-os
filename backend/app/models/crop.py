from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer, String, func
from sqlalchemy.orm import relationship

from app.shared.database import Base


class CropTemplate(Base):
    """作物模板模型，定义一种作物的基本信息及其生长阶段。"""

    __tablename__ = "crop_templates"
    __table_args__ = (
        Index("ix_crop_templates_farm_name_variety", "farm_id", "name", "variety"),
    )

    id = Column(Integer, primary_key=True, index=True)
    farm_id = Column(
        Integer().evaluates_none(), ForeignKey("farms.id"), nullable=True, default=1
    )
    name = Column(String(100), nullable=False)
    variety = Column(String(100), nullable=True)
    category = Column(String(50), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    stages = relationship(
        "GrowthStage",
        back_populates="crop_template",
        cascade="all, delete-orphan",
    )


class GrowthStage(Base):
    """生长阶段模型，定义作物在某一生长阶段的具体信息。"""

    __tablename__ = "growth_stages"

    id = Column(Integer, primary_key=True, index=True)
    crop_template_id = Column(
        Integer,
        ForeignKey("crop_templates.id"),
        nullable=False,
    )
    name = Column(String(100), nullable=False)
    duration_days = Column(Integer, nullable=False)
    order_index = Column(Integer, nullable=False)
    key_tasks = Column(String(500), nullable=True)

    crop_template = relationship("CropTemplate", back_populates="stages")
