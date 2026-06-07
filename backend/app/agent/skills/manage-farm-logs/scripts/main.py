"""农事日志管理 Skill。"""

from datetime import date, datetime

from skillify.models.schemas import ResultStatus, SkillResult
from skillify.skills.base import Skill

from app.agent.skills.context import require_farm_context
from app.agent.skills.metadata import SkillPermissionLevel, SkillRiskLevel
from app.core.database import SessionLocal
from app.models.log import FarmLog
from app.schemas.log import FarmLogCreate
from app.services import log_service


class ManageFarmLogsSkill(Skill):
    """更新或删除农事日志。"""

    def name(self) -> str:
        return "manage_farm_logs"

    def description(self) -> str:
        return "更新或删除已有农事日志。创建农事记录请使用 log_farm_activity。"

    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "action": {"type": "string", "description": "操作：update/delete"},
                "log_id": {"type": "integer", "description": "农事日志 ID"},
                "cycle_id": {"type": "integer", "description": "茬口 ID"},
                "operation_type": {"type": "string", "description": "操作类型"},
                "operation_date": {
                    "type": "string",
                    "description": "操作日期，YYYY-MM-DD",
                },
                "operation_time": {
                    "type": "string",
                    "description": "操作时间，ISO datetime，可选",
                },
                "note": {"type": "string", "description": "备注"},
                "photo_urls": {"type": "string", "description": "图片 URL 列表字符串"},
            },
            "required": ["action"],
        }

    def metadata(self) -> dict:
        return {
            "permission_level": SkillPermissionLevel.WRITE_CONFIRM,
            "risk_level": SkillRiskLevel.MEDIUM,
            "context_dependencies": ["farm_logs", "crop_cycles"],
            "cache_invalidation": ["farm_logs", "get_farm_status"],
            "confirmation_schema": {
                "target_fields": ["action", "log_id", "cycle_id"],
                "changed_fields": [
                    "operation_type",
                    "operation_date",
                    "operation_time",
                    "note",
                    "photo_urls",
                ],
                "editable_fields": [
                    "action",
                    "log_id",
                    "cycle_id",
                    "operation_type",
                    "operation_date",
                    "operation_time",
                    "note",
                    "photo_urls",
                ],
                "risk_notes": ["删除农事日志会影响历史农事记录。"],
            },
            "evaluation_tags": ["write", "farm_logs"],
        }

    async def execute(self, params: dict, context) -> SkillResult:
        farm_id, context_error = require_farm_context(context, "管理农事日志")
        if context_error:
            return context_error
        action = _clean(params.get("action")) or "update"
        db = SessionLocal()
        try:
            if action == "update":
                return _update_log(db, farm_id, params)
            if action == "delete":
                return _delete_log(db, farm_id, params)
            return SkillResult(
                status=ResultStatus.FAILED,
                reply="管理农事日志失败：action 必须是 update 或 delete。",
            )
        except Exception as exc:
            return SkillResult(
                status=ResultStatus.FAILED, reply=f"管理农事日志失败：{exc}"
            )
        finally:
            db.close()


def _update_log(db, farm_id: int, params: dict) -> SkillResult:
    log_id = params.get("log_id")
    if not log_id:
        return SkillResult(
            status=ResultStatus.NEED_CLARIFY, reply="更新农事日志需要 log_id。"
        )
    existing = _get_log(db, farm_id, int(log_id))
    if existing is None:
        return SkillResult(
            status=ResultStatus.FAILED, reply=f"农事日志 {log_id} 不存在。"
        )
    data = FarmLogCreate(
        cycle_id=int(params.get("cycle_id") or existing.cycle_id),
        operation_type=_clean(params.get("operation_type")) or existing.operation_type,
        operation_date=_to_date(params.get("operation_date"))
        or existing.operation_date,
        operation_time=(
            _to_datetime(params.get("operation_time"))
            if params.get("operation_time") is not None
            else existing.operation_time
        ),
        note=_clean(params.get("note")) if "note" in params else existing.note,
        photo_urls=(
            _clean(params.get("photo_urls"))
            if "photo_urls" in params
            else existing.photo_urls
        ),
    )
    log = log_service.update_log(db, int(log_id), data, farm_id)
    return SkillResult(status=ResultStatus.SUCCESS, reply=f"已更新农事日志 #{log.id}。")


def _delete_log(db, farm_id: int, params: dict) -> SkillResult:
    log_id = params.get("log_id")
    if not log_id:
        return SkillResult(
            status=ResultStatus.NEED_CLARIFY, reply="删除农事日志需要 log_id。"
        )
    log_service.delete_log(db, int(log_id), farm_id)
    return SkillResult(status=ResultStatus.SUCCESS, reply=f"已删除农事日志 #{log_id}。")


def _get_log(db, farm_id: int, log_id: int) -> FarmLog | None:
    return (
        db.query(FarmLog)
        .filter(FarmLog.id == log_id, FarmLog.farm_id == farm_id)
        .first()
    )


def _clean(value) -> str | None:
    if value in (None, ""):
        return None
    text = str(value).strip()
    return text or None


def _to_date(value) -> date | None:
    if value in (None, ""):
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    return date.fromisoformat(str(value))


def _to_datetime(value) -> datetime | None:
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        return value
    return datetime.fromisoformat(str(value))
