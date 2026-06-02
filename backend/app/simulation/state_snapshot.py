import logging

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.simulation.models import DbDiff

logger = logging.getLogger(__name__)

_TABLE_PRIMARY_KEYS = {
    "cost_records": "id",
    "crop_templates": "id",
    "growth_stages": "id",
    "crop_cycles": "id",
    "cycle_stages": "id",
    "farm_logs": "id",
    "users": "id",
    "farms": "id",
    "agent_records": "id",
    "conversations": "id",
    "conversation_messages": "id",
}

# 各表 farm_id 字段名（部分表可能用其他字段或需要关联查询）
_TABLE_FARM_ID_COLUMN = {
    "cost_records": "farm_id",
    "crop_templates": "farm_id",
    "growth_stages": None,  # 通过 crop_template_id 关联
    "crop_cycles": "farm_id",
    "cycle_stages": None,  # 通过 crop_cycles 关联
    "farm_logs": "farm_id",
    "users": None,
    "farms": "id",
    "agent_records": "farm_id",
    "conversations": "farm_id",
    "conversation_messages": None,  # 通过 conversations 关联
}

# 需要 JOIN 关联 farm_id 的表
_TABLE_JOIN_SQL = {
    "growth_stages": (
        "SELECT gs.* FROM growth_stages gs "
        "JOIN crop_templates ct ON gs.crop_template_id = ct.id "
        "WHERE ct.farm_id = :farm_id"
    ),
    "cycle_stages": (
        "SELECT cs.* FROM cycle_stages cs "
        "JOIN crop_cycles cc ON cs.cycle_id = cc.id "
        "WHERE cc.farm_id = :farm_id"
    ),
    "conversation_messages": (
        "SELECT cm.* FROM conversation_messages cm "
        "JOIN conversations c ON cm.conversation_id = c.id "
        "WHERE c.farm_id = :farm_id"
    ),
}


class DbStateSnapshot:
    """数据库状态快照 — 操作前后对比，检测 write skill 是否真正执行。"""

    def __init__(self, db: Session, farm_id: int = 1):
        self._db = db
        self._farm_id = farm_id

    async def take(self, tables: list[str]) -> dict[str, list[dict]]:
        """
        对指定表做快照。
        只查询与当前 farm_id 相关的记录。
        返回：{表名: [记录字典列表]}，按主键排序。
        """
        snapshot: dict[str, list[dict]] = {}
        for table in tables:
            records = await self._fetch_table(table)
            snapshot[table] = records
        return snapshot

    async def _fetch_table(self, table: str) -> list[dict]:
        """查询单表数据，按主键排序。"""
        pk = _TABLE_PRIMARY_KEYS.get(table, "id")
        join_sql = _TABLE_JOIN_SQL.get(table)

        if join_sql:
            sql = text(join_sql + f" ORDER BY {pk}")
        else:
            farm_col = _TABLE_FARM_ID_COLUMN.get(table)
            if farm_col:
                sql = text(
                    f"SELECT * FROM {table} WHERE {farm_col} = :farm_id ORDER BY {pk}"
                )
            else:
                sql = text(f"SELECT * FROM {table} ORDER BY {pk}")

        try:
            result = self._db.execute(sql, {"farm_id": self._farm_id})
            rows = result.mappings().all()
            records = []
            for row in rows:
                record = dict(row)
                record["__table__"] = table
                records.append(record)
            return records
        except Exception:
            logger.exception("查询表 %s 失败", table)
            return []

    def compute_diff(
        self,
        before: dict[str, list[dict]],
        after: dict[str, list[dict]],
    ) -> DbDiff:
        """
        对比两次快照，返回差异。
        added: 在 after 中但不在 before 中的记录
        removed: 在 before 中但不在 after 中的记录
        modified: 同一主键记录但字段值变化（忽略 created_at/updated_at）
        """
        diff = DbDiff()

        all_tables = set(before.keys()) | set(after.keys())
        for table in all_tables:
            before_records = {self._record_key(table, r): r for r in before.get(table, [])}
            after_records = {self._record_key(table, r): r for r in after.get(table, [])}

            before_keys = set(before_records.keys())
            after_keys = set(after_records.keys())

            for key in after_keys - before_keys:
                record = dict(after_records[key])
                record["__table__"] = table
                diff.added.append(record)

            for key in before_keys - after_keys:
                record = dict(before_records[key])
                record["__table__"] = table
                diff.removed.append(record)

            for key in before_keys & after_keys:
                b_norm = self._normalize_record(before_records[key])
                a_norm = self._normalize_record(after_records[key])
                if b_norm != a_norm:
                    record = dict(after_records[key])
                    record["__table__"] = table
                    record["__before__"] = b_norm
                    record["__after__"] = a_norm
                    diff.modified.append(record)

        return diff

    def _record_key(self, table: str, record: dict) -> str:
        """生成记录的唯一键（用于对比）。"""
        pk = _TABLE_PRIMARY_KEYS.get(table, "id")
        return f"{table}:{record.get(pk, '')}"

    def _normalize_record(self, record: dict) -> dict:
        """规范化记录，排除不稳定字段。"""
        exclude = {"created_at", "updated_at", "__table__", "__before__", "__after__"}
        return {k: v for k, v in record.items() if k not in exclude}
