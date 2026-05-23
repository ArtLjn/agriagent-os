from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import relationship

from app.core.database import Base


class CropTemplate(Base):
    """作物模板模型，定义一种作物的基本信息及其生长阶段。"""

    __tablename__ = "crop_templates"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    variety = Column(String, nullable=True)
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
    name = Column(String, nullable=False)
    duration_days = Column(Integer, nullable=False)
    order_index = Column(Integer, nullable=False)
    key_tasks = Column(String, nullable=True)

    crop_template = relationship("CropTemplate", back_populates="stages")
