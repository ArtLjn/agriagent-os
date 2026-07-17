"""成本记录写入和删除操作。"""

from datetime import date

from skillify.models.schemas import ResultStatus, SkillResult

from app.skills.context import require_farm_context
from app.core.database import SessionLocal
from app.core.date_context import get_request_date
from app.models.cost_category import CostCategory
from app.schemas.cost import CostRecordCreate
from app.services import cost_service
from app.services.cost_service import create_record as create_cost_record


async def create_record(params: dict, context) -> SkillResult:
    amount = _normalize_amount(params.get("amount"))
    category = params.get("category")
    error = _validate_record_required(amount, category)
    if error:
        return error
    route_error = _guard_wrong_record_route(category, params.get("note"))
    if route_error:
        return route_error
    farm_id, context_error = require_farm_context(context, "记账")
    if context_error:
        return context_error
    record_create = CostRecordCreate(
        record_type=params.get("record_type", "cost"),
        category=category,
        amount=amount,
        record_date=_parse_date(params.get("record_date")),
        note=params.get("note"),
        record_subtype=_normalize_record_subtype(params.get("record_subtype")),
        counterparty=_clean_optional_text(params.get("counterparty")),
        due_date=_parse_optional_date(params.get("due_date")),
    )
    db = SessionLocal()
    try:
        category_error = _validate_category_choice(
            db, farm_id, category, record_create.record_type
        )
        if category_error:
            return category_error
        created = create_cost_record(db, record_create, farm_id=farm_id)
        return SkillResult(
            status=ResultStatus.SUCCESS,
            reply=_format_record_reply(created),
        )
    except Exception as exc:
        return SkillResult(status=ResultStatus.FAILED, reply=f"记账失败：{exc}")
    finally:
        db.close()


async def delete_record(params: dict, context) -> SkillResult:
    farm_id, context_error = require_farm_context(context, "删除账务记录")
    if context_error:
        return context_error
    record_id = params.get("record_id")
    if not record_id:
        return SkillResult(
            status=ResultStatus.NEED_CLARIFY,
            reply="删除账务记录需要 record_id。",
        )
    db = SessionLocal()
    try:
        record = cost_service.delete_record(db, int(record_id), farm_id)
        if record is None:
            return SkillResult(
                status=ResultStatus.FAILED,
                reply="删除账务记录失败：记录不存在。",
            )
        return SkillResult(
            status=ResultStatus.SUCCESS,
            reply=f"已删除账务记录 #{record.id}。",
        )
    except Exception as exc:
        return SkillResult(
            status=ResultStatus.FAILED,
            reply=f"删除账务记录失败：{exc}",
        )
    finally:
        db.close()


def _normalize_amount(amount):
    if isinstance(amount, str):
        try:
            return float(amount)
        except (ValueError, TypeError):
            return amount
    return amount


def _validate_record_required(amount, category) -> SkillResult | None:
    if not amount or not isinstance(amount, (int, float)) or amount <= 0:
        return SkillResult(
            status=ResultStatus.FAILED,
            reply="记账失败：金额无效，请提供大于0的金额。",
        )
    if not category or not isinstance(category, str):
        return SkillResult(status=ResultStatus.FAILED, reply="记账失败：分类不能为空。")
    return None


def _guard_wrong_record_route(category, note) -> SkillResult | None:
    category_text = str(category or "").strip()
    note_text = str(note or "").strip()
    if category_text == "还款":
        return SkillResult(
            status=ResultStatus.NEED_CLARIFY,
            reply="这像是在还赊账，请使用 operation=settle_debt 处理。",
        )
    if note_text.startswith(("还", "结清", "清账")) and category_text in {
        "还款",
        "其他",
    }:
        return SkillResult(
            status=ResultStatus.NEED_CLARIFY,
            reply="这像是在还账，请使用 operation=settle_debt 处理原赊账记录。",
        )
    return None


def _validate_category_choice(
    db, farm_id: int, category: str, record_type: str
) -> SkillResult | None:
    category_count = db.query(CostCategory).filter_by(farm_id=farm_id).count()
    if category_count == 0:
        return None
    category_exists = (
        db.query(CostCategory)
        .filter(
            CostCategory.farm_id == farm_id,
            CostCategory.name == category,
            CostCategory.type == record_type,
        )
        .first()
    )
    if category == "其他" or category_exists is None:
        return SkillResult(
            status=ResultStatus.NEED_CLARIFY,
            reply="记账分类不明确，请从已有分类中选择。",
        )
    return None


def _parse_date(date_str: str | None) -> date:
    if not date_str:
        return get_request_date()
    try:
        return date.fromisoformat(date_str)
    except (ValueError, TypeError):
        return get_request_date()


def _parse_optional_date(date_str: str | None) -> date | None:
    if not date_str:
        return None
    try:
        return date.fromisoformat(date_str)
    except (ValueError, TypeError):
        return None


def _normalize_record_subtype(value) -> str | None:
    if not value or not isinstance(value, str):
        return None
    text = value.strip()
    if text in {"赊账", "欠款", "未结", "未收款", "应付", "应收"}:
        return "赊账"
    return text[:50] or None


def _clean_optional_text(value) -> str | None:
    if not value or not isinstance(value, str):
        return None
    return value.strip()[:100] or None


def _format_record_reply(record) -> str:
    type_label = "收入" if record.record_type == "income" else "支出"
    lines = [f"💰 已记账：**{record.category}** {record.amount}元（{type_label}）"]
    if getattr(record, "record_subtype", None) == "赊账":
        counterparty = getattr(record, "counterparty", None)
        lines.append(f"🧾 赊账：{counterparty}" if counterparty else "🧾 赊账")
    if record.note:
        if "赊账" in record.note:
            lines.append(f"📝 {record.note}")
        else:
            lines.append(f"📝 备注：{record.note}")
    recorded_at = getattr(record, "recorded_at", None)
    if recorded_at:
        lines.append(f"📅 {recorded_at.strftime('%Y-%m-%d %H:%M')}")
    else:
        lines.append(f"📅 {record.record_date}")
    return "\n".join(lines)
