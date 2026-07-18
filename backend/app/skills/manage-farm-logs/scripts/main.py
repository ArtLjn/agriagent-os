"""农事日志聚合 Skill。"""

from datetime import date, datetime, timedelta

from skillify.models.schemas import ResultStatus, SkillResult
from skillify.skills.base import Skill

from app.skills.context import require_farm_context
from app.skills.metadata import SkillPermissionLevel, SkillRiskLevel
from app.shared.database import SessionLocal
from app.models.cycle import CropCycle
from app.models.log import FarmLog
from app.schemas.log import FarmLogCreate
from app.services import log_service


class ManageFarmLogsSkill(Skill):
    """统一农事日志业务能力 Skill。"""

    def name(self) -> str:
        return "manage_farm_logs"

    def description(self) -> str:
        return (
            "管理农事日志。通过 operation 选择 create_log、query_logs 或 manage_log，"
            "支持记录浇水、施肥、打药、除草、翻地等农事操作，查询最近农事记录，"
            "以及更新或删除已有农事日志。"
        )

    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "operation": {
                    "type": "string",
                    "description": "操作类型：create_log、query_logs、manage_log。",
                    "enum": ["create_log", "query_logs", "manage_log"],
                },
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
                "days": {
                    "type": "integer",
                    "description": "查询最近天数，默认 7。",
                    "default": 7,
                },
            },
            "required": ["operation"],
        }

    def metadata(self) -> dict:
        return {
            "permission_level": SkillPermissionLevel.READ,
            "risk_level": SkillRiskLevel.LOW,
            "domain": "log",
            "capability": "manage_farm_logs",
            "operation": None,
            "operation_risk": None,
            "legacy_alias": None,
            "context_dependencies": [
                "farm",
                "farm_logs",
                "crop_cycles",
                "active_cycles",
            ],
            "cache_invalidation": ["farm_logs", "get_farm_status"],
            "confirmation_schema": {
                "target_fields": ["operation", "action", "log_id", "cycle_id"],
                "changed_fields": [
                    "operation_type",
                    "operation_date",
                    "operation_time",
                    "note",
                    "photo_urls",
                ],
                "editable_fields": [
                    "operation",
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
            "evaluation_tags": ["farm_logs", "log"],
        }

    async def execute(self, params: dict, context) -> SkillResult:
        farm_id, context_error = require_farm_context(context, "管理农事日志")
        if context_error:
            return context_error
        operation = _resolve_operation(params)
        db = SessionLocal()
        try:
            if operation == "create_log":
                return _create_log(db, farm_id, params)
            if operation == "query_logs":
                return _query_logs(db, farm_id, params)
            if operation == "manage_log":
                action = _clean(params.get("action")) or "update"
                if action == "update":
                    return _update_log(db, farm_id, params)
                if action == "delete":
                    return _delete_log(db, farm_id, params)
                return SkillResult(
                    status=ResultStatus.FAILED,
                    reply="管理农事日志失败：action 必须是 update 或 delete。",
                )
            if operation == "update":
                return _update_log(db, farm_id, params)
            if operation == "delete":
                return _delete_log(db, farm_id, params)
            return SkillResult(
                status=ResultStatus.NEED_CLARIFY,
                reply="请说明要记录、查询、更新还是删除农事日志。",
            )
        except Exception as exc:
            return SkillResult(
                status=ResultStatus.FAILED, reply=f"管理农事日志失败：{exc}"
            )
        finally:
            db.close()


def _resolve_operation(params: dict) -> str:
    operation = _clean(params.get("operation"))
    if operation:
        return operation
    # 兼容历史 pending 参数：旧 manage_farm_logs 只传 action。
    action = _clean(params.get("action"))
    if action in {"update", "delete"}:
        return "manage_log"
    if _clean(params.get("operation_type")):
        return "create_log"
    return ""


def _create_log(db, farm_id: int, params: dict) -> SkillResult:
    operation_type = _clean(params.get("operation_type"))
    if not operation_type:
        return SkillResult(
            status=ResultStatus.FAILED,
            reply="记农事失败：请提供操作类型（如浇水、施肥、打药）。",
        )

    cycle_id = params.get("cycle_id")
    if not cycle_id:
        cycle_id = _find_first_active_cycle(db, farm_id)
        if not cycle_id:
            return SkillResult(
                status=ResultStatus.NEED_CLARIFY,
                reply="当前没有活跃的茬口，请先建一个茬口再来记录农事。",
            )

    log_create = FarmLogCreate(
        cycle_id=int(cycle_id),
        operation_type=operation_type,
        operation_date=_parse_date(params.get("operation_date")),
        operation_time=_to_datetime(params.get("operation_time")),
        note=_clean(params.get("note")),
        photo_urls=_clean(params.get("photo_urls")),
    )
    created = log_service.create_log(db, log_create, farm_id=farm_id)
    return SkillResult(status=ResultStatus.SUCCESS, reply=_format_create_reply(created))


def _query_logs(db, farm_id: int, params: dict) -> SkillResult:
    days = _to_positive_int(params.get("days"), default=7)
    query = db.query(FarmLog).filter(FarmLog.farm_id == farm_id)
    cycle_id = params.get("cycle_id")
    if cycle_id:
        query = query.filter(FarmLog.cycle_id == int(cycle_id))
    since = date.today() - timedelta(days=days)
    logs = (
        query.filter(FarmLog.operation_date >= since)
        .order_by(FarmLog.operation_date.desc())
        .limit(20)
        .all()
    )
    if not logs:
        scope = f"{cycle_id} 号茬口" if cycle_id else "农场"
        return SkillResult(
            status=ResultStatus.SUCCESS,
            reply=f"{scope}最近 {days} 天内没有农事记录。",
        )

    title = f"最近 {days} 天农事记录（共 {len(logs)} 条）："
    lines = [title]
    for log in logs:
        scope = f"茬口 {log.cycle_id}，" if not cycle_id else ""
        lines.append(
            f"  {log.operation_date}: {scope}{log.operation_type}"
            f" - {log.note or '无备注'}"
        )
    return SkillResult(status=ResultStatus.SUCCESS, reply="\n".join(lines))


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


def _find_first_active_cycle(db, farm_id: int) -> int | None:
    cycle = (
        db.query(CropCycle)
        .filter(CropCycle.farm_id == farm_id, CropCycle.status == "active")
        .order_by(CropCycle.id)
        .first()
    )
    return cycle.id if cycle else None


def _clean(value) -> str | None:
    if value in (None, ""):
        return None
    text = str(value).strip()
    return text or None


def _parse_date(value) -> date:
    if not value:
        return date.today()
    try:
        return _to_date(value) or date.today()
    except (ValueError, TypeError):
        return date.today()


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


def _to_positive_int(value, *, default: int) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return default
    return number if number > 0 else default


def _format_create_reply(log) -> str:
    parts = [f"已记录「{log.operation_type}」"]
    if log.operation_date:
        parts.append(f"日期 {log.operation_date}")
    if log.note:
        parts.append(f"备注: {log.note}")
    return "，".join(parts)
