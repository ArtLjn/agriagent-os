"""作业类型 Service（从 archive planting/service.py 复用 + 新增数据库查询）。

提供：
  - get_operation_types：返回内置作业类型（西瓜专用 / 通用两类）
  - list_distinct_operation_types：从 operation_work_orders 表查已用过的作业类型

内置常量：
  - WATERMELON_OPERATION_TYPES：西瓜种植的标准化作业类型清单
  - GENERAL_OPERATION_TYPES：通用作业类型清单

改造点（相比 archive）：
  - 导入改为 business.models（OperationWorkOrder）
  - 新增 list_distinct_operation_types：从数据库读已用过的作业类型，
    供前端作业类型选择器展示"内置 + 历史用过"的合并候选
  - 保留 db: Session 第一参数（list_distinct_operation_types）
"""
from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import distinct
from sqlalchemy.orm import Session

from business.models import OperationWorkOrder

logger = logging.getLogger(__name__)

# 西瓜种植的标准化作业类型清单（按生长阶段顺序）。
WATERMELON_OPERATION_TYPES = [
    "定植",
    "补苗",
    "整枝打杈",
    "理蔓",
    "压蔓",
    "人工授粉",
    "留瓜/疏瓜",
    "垫瓜/翻瓜",
    "浇水",
    "冲肥",
    "打药",
    "采收",
    "装车",
]

# 通用作业类型清单（适用于非特定作物的常见农事）。
GENERAL_OPERATION_TYPES = ["浇水", "施肥", "打药", "除草", "巡棚", "采收", "其他"]


def get_operation_types(crop_name: str | None = None) -> list[dict[str, Any]]:
    """返回内置作业类型清单。

    crop_name 含"西瓜"/"watermelon"时返回西瓜专用清单，否则返回通用清单。
    返回结构：[{name, crop, is_builtin, sort_order}, ...]。
    """
    normalized = (crop_name or "").lower()
    is_watermelon = "西瓜" in normalized or "watermelon" in normalized
    names = WATERMELON_OPERATION_TYPES if is_watermelon else GENERAL_OPERATION_TYPES
    return [
        {
            "name": name,
            "crop": "西瓜" if is_watermelon else None,
            "is_builtin": True,
            "sort_order": index,
        }
        for index, name in enumerate(names)
    ]


def list_distinct_operation_types(
    db: Session, farm_id: int
) -> list[dict[str, Any]]:
    """查询农场下已用过的作业类型（从 operation_work_orders 表 distinct）。

    用于前端作业类型选择器：把"内置清单"与"历史用过"合并展示，
    避免遗漏已用过但未在内置清单中的自定义作业类型。
    """
    rows = (
        db.query(distinct(OperationWorkOrder.operation_type))
        .filter(
            OperationWorkOrder.farm_id == farm_id,
            OperationWorkOrder.operation_type.isnot(None),
        )
        .all()
    )
    types = [row[0] for row in rows if row[0]]
    return [
        {
            "name": name,
            "crop": None,
            "is_builtin": False,
            "sort_order": index,
        }
        for index, name in enumerate(sorted(types))
    ]


__all__ = [
    "WATERMELON_OPERATION_TYPES",
    "GENERAL_OPERATION_TYPES",
    "get_operation_types",
    "list_distinct_operation_types",
]
