"""工人档案管理 Skill。"""

from decimal import Decimal, InvalidOperation

from skillify.models.schemas import ResultStatus, SkillResult
from skillify.skills.base import Skill

from app.skills.context import require_farm_context
from app.skills.metadata import SkillPermissionLevel, SkillRiskLevel
from app.shared.database import SessionLocal
from app.models.planting import Worker
from app.schemas.planting import WorkerCreate, WorkerUpdate
from app.services import planting_service

_ACTIVE_STATUS = "active"
_INACTIVE_STATUS = "inactive"
_QUERY_ACTIONS = {"query", "list", "read", "query_workers"}
_WRITE_ACTIONS = {"create", "update", "deactivate", "restore"}
_WRITE_FIELDS = (
    "name",
    "phone",
    "default_pay_type",
    "default_unit_price",
    "note",
    "status",
)


class ManageWorkersSkill(Skill):
    """维护工人档案。"""

    def name(self) -> str:
        return "manage_workers"

    def description(self) -> str:
        return (
            "查询、创建、更新、停用或恢复工人档案。创建或更新时可记录姓名、电话、"
            "默认计薪方式、默认单价和备注；删除语义统一为停用/离职，保留历史用工。"
        )

    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "description": "操作：query/create/update/deactivate/restore",
                },
                "operation": {
                    "type": "string",
                    "description": "能力操作：query_workers 或 manage_worker",
                },
                "active_only": {
                    "type": "boolean",
                    "description": "查询时是否只返回活跃工人，默认 true",
                },
                "worker_id": {"type": "integer", "description": "工人 ID"},
                "name": {"type": "string", "description": "工人姓名"},
                "phone": {"type": "string", "description": "手机号"},
                "default_pay_type": {
                    "type": "string",
                    "description": "默认计薪方式，如 daily、hourly、piece",
                },
                "default_unit_price": {
                    "type": "number",
                    "description": "默认单价，如日薪 150",
                },
                "note": {"type": "string", "description": "备注"},
                "status": {
                    "type": "string",
                    "description": "状态：active 或 inactive",
                },
            },
            "required": [],
        }

    def metadata(self) -> dict:
        return {
            "permission_level": SkillPermissionLevel.WRITE_CONFIRM,
            "risk_level": SkillRiskLevel.MEDIUM,
            "context_dependencies": ["workers", "unpaid_labor"],
            "cache_invalidation": ["get_farm_status"],
            "confirmation_schema": {
                "target_fields": ["worker_id", "name", "action"],
                "changed_fields": [
                    "phone",
                    "default_pay_type",
                    "default_unit_price",
                    "note",
                    "status",
                ],
                "inferred_fields": [],
                "editable_fields": [
                    "action",
                    "worker_id",
                    "name",
                    "phone",
                    "default_pay_type",
                    "default_unit_price",
                    "note",
                    "status",
                ],
                "risk_notes": ["停用工人会隐藏当前列表，但保留历史用工和账务记录。"],
            },
            "evaluation_tags": ["read", "write", "worker", "labor"],
        }

    async def execute(self, params: dict, context) -> SkillResult:
        farm_id, context_error = require_farm_context(context, "管理工人档案")
        if context_error:
            return context_error

        action = _resolve_action(params)
        db = SessionLocal()
        try:
            if action == "query":
                return _query_workers(db, farm_id, params)
            if action == "create":
                return _create_worker(db, farm_id, params)
            if action == "update":
                return _update_worker(db, farm_id, params)
            if action == "deactivate":
                return _deactivate_worker(db, farm_id, params)
            if action == "restore":
                return _restore_worker(db, farm_id, params)
            return SkillResult(
                status=ResultStatus.FAILED,
                reply=(
                    "管理工人失败：action 必须是 query、create、update、"
                    "deactivate 或 restore。"
                ),
            )
        except Exception as exc:
            return SkillResult(status=ResultStatus.FAILED, reply=f"管理工人失败：{exc}")
        finally:
            db.close()


def _resolve_action(params: dict) -> str:
    operation = _clean(params.get("operation"))
    action = _clean(params.get("action"))
    if operation == "query_workers" or action in _QUERY_ACTIONS:
        return "query"
    if action in _WRITE_ACTIONS:
        return action
    if action:
        return action
    if operation == "manage_worker":
        return "create"
    if _has_write_fields(params):
        return "create"
    return "query"


def _has_write_fields(params: dict) -> bool:
    return any(params.get(key) not in (None, "") for key in _WRITE_FIELDS)


def _query_workers(db, farm_id: int, params: dict) -> SkillResult:
    active_only = _to_bool(params.get("active_only"), default=True)
    workers = planting_service.list_workers(
        db,
        farm_id,
        active_only=active_only,
    )
    if not workers:
        return SkillResult(status=ResultStatus.SUCCESS, reply="当前没有活跃工人。")
    lines = ["当前工人："]
    for worker in workers:
        lines.append(_format_worker(worker))
    return SkillResult(status=ResultStatus.SUCCESS, reply="\n".join(lines))


def _create_worker(db, farm_id: int, params: dict) -> SkillResult:
    name = _clean(params.get("name"))
    if not name:
        return SkillResult(status=ResultStatus.NEED_CLARIFY, reply="创建工人需要姓名。")
    existing = _find_worker_by_name(db, farm_id, name)
    if existing and existing.status == _INACTIVE_STATUS:
        return SkillResult(
            status=ResultStatus.NEED_CLARIFY,
            reply=f"工人「{name}」已停用。要恢复该工人，还是新建同名工人？",
        )
    worker = planting_service.create_worker(db, _worker_create(params, name), farm_id)
    return SkillResult(
        status=ResultStatus.SUCCESS, reply=f"已创建工人：{_format_worker(worker)}"
    )


def _update_worker(db, farm_id: int, params: dict) -> SkillResult:
    worker = _resolve_worker(db, farm_id, params)
    update_data = WorkerUpdate(**_worker_update_values(params))
    worker = planting_service.update_worker(db, worker.id, update_data, farm_id)
    return SkillResult(
        status=ResultStatus.SUCCESS, reply=f"已更新工人：{_format_worker(worker)}"
    )


def _deactivate_worker(db, farm_id: int, params: dict) -> SkillResult:
    worker = _resolve_worker(db, farm_id, params)
    planting_service.delete_worker(db, worker.id, farm_id)
    return SkillResult(
        status=ResultStatus.SUCCESS,
        reply=f"已停用工人：{worker.name}。历史用工和账务记录已保留。",
    )


def _restore_worker(db, farm_id: int, params: dict) -> SkillResult:
    worker = _resolve_worker(db, farm_id, params)
    update_data = WorkerUpdate(status=_ACTIVE_STATUS)
    worker = planting_service.update_worker(db, worker.id, update_data, farm_id)
    return SkillResult(
        status=ResultStatus.SUCCESS, reply=f"已恢复工人：{_format_worker(worker)}"
    )


def _worker_create(params: dict, name: str) -> WorkerCreate:
    return WorkerCreate(
        name=name,
        phone=_clean(params.get("phone")),
        default_pay_type=_clean(params.get("default_pay_type")) or "daily",
        default_unit_price=_to_decimal(params.get("default_unit_price")),
        note=_clean(params.get("note")),
        status=_clean(params.get("status")) or _ACTIVE_STATUS,
    )


def _worker_update_values(params: dict) -> dict:
    values = {}
    for key in ("name", "phone", "default_pay_type", "note", "status"):
        if key in params and params.get(key) is not None:
            values[key] = _clean(params.get(key))
    if "default_unit_price" in params and params.get("default_unit_price") is not None:
        values["default_unit_price"] = _to_decimal(params.get("default_unit_price"))
    return values


def _resolve_worker(db, farm_id: int, params: dict) -> Worker:
    worker_id = params.get("worker_id")
    if worker_id:
        worker = (
            db.query(Worker)
            .filter(Worker.id == worker_id, Worker.farm_id == farm_id)
            .first()
        )
    else:
        name = _clean(params.get("name"))
        worker = _find_worker_by_name(db, farm_id, name) if name else None
    if worker is None:
        raise ValueError("工人不存在，请提供工人姓名或 worker_id。")
    return worker


def _find_worker_by_name(db, farm_id: int, name: str | None) -> Worker | None:
    if not name:
        return None
    return (
        db.query(Worker)
        .filter(Worker.farm_id == farm_id, Worker.name == name)
        .order_by(Worker.id)
        .first()
    )


def _format_worker(worker: Worker) -> str:
    price = worker.default_unit_price
    price_text = f"{price}元" if price is not None else "未设置"
    status_text = "活跃" if worker.status == _ACTIVE_STATUS else "已停用"
    return f"- {worker.name}（{status_text}，{worker.default_pay_type}，默认单价 {price_text}）"


def _clean(value) -> str | None:
    if value in (None, ""):
        return None
    text = str(value).strip()
    return text or None


def _to_decimal(value) -> Decimal | None:
    if value in (None, ""):
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None


def _to_bool(value, *, default: bool) -> bool:
    if value in (None, ""):
        return default
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text in {"false", "0", "no", "n", "否", "不", "停用", "离职", "历史"}:
        return False
    if text in {"true", "1", "yes", "y", "是", "活跃", "在职"}:
        return True
    return bool(value)
