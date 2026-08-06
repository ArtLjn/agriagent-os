"""Mongo-only 写入时生成兼容旧 mysqlId 的标识。"""

from __future__ import annotations

import itertools
import time
from typing import Any

_SYNTHETIC_ID_COUNTER = itertools.count()


def next_synthetic_mysql_id() -> int:
    """生成 int64/JS-safe 范围内的近似递增兼容 ID。"""
    base = (time.time_ns() // 1000) * 1000
    return base + (next(_SYNTHETIC_ID_COUNTER) % 1000)


def ensure_row_mysql_id(row: Any) -> int:
    """为未落 MySQL 的 ORM 行对象补齐 id，供 Mongo 唯一索引使用。"""
    row_id = getattr(row, "id", None)
    if row_id is None:
        row_id = next_synthetic_mysql_id()
        setattr(row, "id", row_id)
    return int(row_id)


def ensure_doc_mysql_id(doc: dict[str, Any]) -> int:
    """为 Mongo 文档补齐 mysqlId。"""
    mysql_id = doc.get("mysqlId")
    if mysql_id is None:
        mysql_id = next_synthetic_mysql_id()
        doc["mysqlId"] = mysql_id
    return int(mysql_id)


__all__ = ["ensure_doc_mysql_id", "ensure_row_mysql_id", "next_synthetic_mysql_id"]
