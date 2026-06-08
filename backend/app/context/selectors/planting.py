"""种植作业相关 selector。"""

from decimal import Decimal

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.context.models import ContextBlock
from app.models.cost_category import CostCategory
from app.models.planting import (
    LaborEntry,
    OperationWorkOrder,
    PlantingUnit,
    Worker,
)


def _format_amount(value: Decimal | None) -> str:
    amount = value or Decimal("0")
    if amount == amount.to_integral_value():
        return str(int(amount))
    return str(amount.normalize())


class PlantingUnitSelector:
    """选择种植单元摘要。"""

    def select(self, db: Session, farm_id: int, **_kwargs) -> list[ContextBlock]:
        units = (
            db.query(PlantingUnit)
            .filter(PlantingUnit.farm_id == farm_id)
            .order_by(PlantingUnit.status.desc(), PlantingUnit.id)
            .limit(8)
            .all()
        )
        if not units:
            content = "种植单元：暂无"
        else:
            parts = []
            for unit in units:
                area = (
                    f"{_format_amount(unit.area_mu)}亩"
                    if unit.area_mu is not None
                    else "面积未填"
                )
                parts.append(f"{unit.name}(cycle={unit.cycle_id}，{area}，{unit.status})")
            content = "种植单元：" + "；".join(parts)
        return [
            ContextBlock(
                key="planting_units",
                source="planting_unit",
                purpose="种植单元",
                content=content,
                priority=72,
                ttl_seconds=300,
            )
        ]


class OperationWorkOrderSelector:
    """选择近期作业单摘要。"""

    def select(self, db: Session, farm_id: int, **_kwargs) -> list[ContextBlock]:
        work_orders = (
            db.query(OperationWorkOrder)
            .filter(OperationWorkOrder.farm_id == farm_id)
            .order_by(OperationWorkOrder.operation_date.desc(), OperationWorkOrder.id.desc())
            .limit(6)
            .all()
        )
        if not work_orders:
            content = "作业单：暂无"
        else:
            parts = []
            for order in work_orders:
                units = [link.unit.name for link in order.unit_links if link.unit]
                scope = "、".join(units) if units else order.scope_type
                parts.append(
                    f"#{order.id} {order.operation_date} {order.operation_type}"
                    f"(cycle={order.cycle_id or '无'}，范围={scope})"
                )
            content = "近期作业单：" + "；".join(parts)
        return [
            ContextBlock(
                key="operation_work_orders",
                source="operation_work_order",
                purpose="作业单",
                content=content,
                priority=68,
                ttl_seconds=180,
            )
        ]


class WorkerSelector:
    """选择工人摘要。"""

    def select(self, db: Session, farm_id: int, **_kwargs) -> list[ContextBlock]:
        workers = (
            db.query(Worker)
            .filter(Worker.farm_id == farm_id)
            .order_by(Worker.status.desc(), Worker.id)
            .limit(10)
            .all()
        )
        if not workers:
            content = "工人：暂无"
        else:
            parts = [
                f"{worker.name}(id={worker.id}，{worker.status}，{worker.default_pay_type}"
                f"={_format_amount(worker.default_unit_price)}元)"
                for worker in workers
            ]
            content = "工人：" + "；".join(parts)
        return [
            ContextBlock(
                key="workers",
                source="worker",
                purpose="工人档案",
                content=content,
                priority=70,
                ttl_seconds=300,
            )
        ]


class UnpaidLaborSummarySelector:
    """选择未结人工摘要。"""

    def select(self, db: Session, farm_id: int, **_kwargs) -> list[ContextBlock]:
        rows = (
            db.query(
                Worker.name,
                func.sum(LaborEntry.unpaid_amount),
                func.count(LaborEntry.id),
            )
            .join(Worker, Worker.id == LaborEntry.worker_id)
            .filter(
                LaborEntry.farm_id == farm_id,
                LaborEntry.unpaid_amount > 0,
                or_(
                    LaborEntry.settlement_status == "unpaid",
                    LaborEntry.settlement_status == "partial",
                ),
            )
            .group_by(Worker.name)
            .order_by(func.sum(LaborEntry.unpaid_amount).desc())
            .limit(8)
            .all()
        )
        if not rows:
            content = "未结人工：暂无"
        else:
            parts = [
                f"{name} 未付{_format_amount(total)}元({count}笔)"
                for name, total, count in rows
            ]
            content = "未结人工：" + "；".join(parts)
        return [
            ContextBlock(
                key="unpaid_labor",
                source="unpaid_labor",
                purpose="未结人工摘要",
                content=content,
                priority=74,
                ttl_seconds=180,
            )
        ]


class CostCategorySelector:
    """选择成本分类摘要。"""

    def select(self, db: Session, farm_id: int, **_kwargs) -> list[ContextBlock]:
        categories = (
            db.query(CostCategory)
            .filter(CostCategory.farm_id == farm_id)
            .order_by(CostCategory.type, CostCategory.sort_order, CostCategory.id)
            .limit(20)
            .all()
        )
        if not categories:
            content = "成本分类：暂无"
        else:
            parts = [f"{item.name}({item.type})" for item in categories]
            content = "成本分类：" + "、".join(parts)
        return [
            ContextBlock(
                key="cost_categories",
                source="cost_category",
                purpose="成本分类",
                content=content,
                priority=62,
                ttl_seconds=600,
            )
        ]


__all__ = [
    "CostCategorySelector",
    "OperationWorkOrderSelector",
    "PlantingUnitSelector",
    "UnpaidLaborSummarySelector",
    "WorkerSelector",
]
