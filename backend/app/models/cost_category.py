"""成本分类模型，定义成本与收入的分类类别。"""

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, func

from app.shared.database import Base


class CostCategory(Base):
    """成本分类模型，支持按农场隔离的类别管理。"""

    __tablename__ = "cost_categories"

    id = Column(Integer, primary_key=True, index=True)
    farm_id = Column(
        Integer, ForeignKey("farms.id"), nullable=False, default=1, index=True
    )
    name = Column(String(50), nullable=False)
    type = Column(String(10), nullable=False)  # cost 或 income
    icon = Column(String(50), nullable=False, default="tag")
    sort_order = Column(Integer, nullable=False, default=0)
    is_default = Column(Boolean, nullable=False, default=False)
    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
