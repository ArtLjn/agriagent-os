"""欠款查询和还款操作。"""

from collections import defaultdict
from decimal import Decimal

from sqlalchemy import or_
from skillify.models.schemas import ResultStatus, SkillResult

from app.agent.skills.context import require_farm_context
from app.core.database import SessionLocal
from app.models.cost import CostRecord
from app.services import debt_service
from app.services.cost_service import SETTLED
from app.services.debt_service import SUBTYPE_DEBT
from app.services.planting_read_service import get_unsettled_labor_summary

_PAYABLE = "payable"
_RECEIVABLE = "receivable"
_ALL = "all"
_DEBT_ONLY = "debt_only"
_TOTAL_PAYABLE = "total_payable"


async def query_debt(params: dict, context) -> SkillResult:
    farm_id, context_error = require_farm_context(context, "查询赊账欠款")
    if context_error:
        return context_error
    direction = _normalize_direction(params.get("direction"))
    counterparty = _clean(params.get("counterparty"))
    limit = _normalize_limit(params.get("limit"))
    scope = _normalize_scope(params.get("scope"))
    db = SessionLocal()
    try:
        records = _query_debts(
            db,
            farm_id=farm_id,
            direction=direction,
            counterparty=counterparty,
        )
        summary = _summarize_debt_records(records)
        if scope == _TOTAL_PAYABLE and direction == _PAYABLE:
            return _total_payable_result(db, farm_id, summary, limit)
        if not summary:
            return SkillResult(
                status=ResultStatus.SUCCESS,
                reply=_empty_debt_reply(direction, counterparty),
                data={"summary": [], "total_remaining": "0.00"},
            )
        summary = summary[:limit]
        return SkillResult(
            status=ResultStatus.SUCCESS,
            reply=_format_debt_reply(summary, direction),
            data={
                "summary": summary,
                "total_remaining": _money(_sum_remaining(summary)),
            },
        )
    except Exception as exc:
        return SkillResult(
            status=ResultStatus.FAILED,
            reply=f"查询赊账欠款失败：{exc}",
        )
    finally:
        db.close()


async def settle_debt(params: dict, context) -> SkillResult:
    counterparty = params.get("counterparty")
    amount = params.get("amount")
    error = _validate_counterparty(counterparty)
    if error:
        return error
    if amount is not None:
        error = _validate_settlement_amount(amount)
        if error:
            return error
    farm_id, context_error = require_farm_context(context, "还款")
    if context_error:
        return context_error
    db = SessionLocal()
    try:
        settlement_amount = None if amount is None else Decimal(str(amount))
        updated = debt_service.settle_debt(
            db,
            farm_id=farm_id,
            counterparty=counterparty,
            amount=settlement_amount,
            note=params.get("note"),
        )
        return SkillResult(
            status=ResultStatus.SUCCESS,
            reply=_format_settle_reply(updated, counterparty),
        )
    except ValueError as exc:
        return SkillResult(status=ResultStatus.FAILED, reply=f"还款失败：{exc}")
    except Exception as exc:
        return SkillResult(status=ResultStatus.FAILED, reply=f"还款失败：{exc}")
    finally:
        db.close()


def _query_debts(db, *, farm_id: int, direction: str, counterparty: str | None):
    query = (
        db.query(CostRecord)
        .filter(CostRecord.farm_id == farm_id)
        .filter(CostRecord.record_subtype == SUBTYPE_DEBT)
        .filter(CostRecord.deleted_at.is_(None))
        .filter(
            or_(
                CostRecord.settlement_status.is_(None),
                CostRecord.settlement_status != SETTLED,
            )
        )
        .filter(
            or_(
                CostRecord.settled_amount.is_(None),
                CostRecord.settled_amount < CostRecord.amount,
            )
        )
    )
    if direction == _PAYABLE:
        query = query.filter(CostRecord.record_type == "cost")
    elif direction == _RECEIVABLE:
        query = query.filter(CostRecord.record_type == "income")
    if counterparty:
        query = query.filter(CostRecord.counterparty.like(f"%{counterparty}%"))
    return query.order_by(
        CostRecord.record_date.desc(),
        CostRecord.recorded_at.desc(),
        CostRecord.id.desc(),
    ).all()


def _summarize_debt_records(records: list[CostRecord]) -> list[dict]:
    groups: dict[str, dict] = defaultdict(
        lambda: {
            "counterparty": "",
            "total_debt": Decimal("0.00"),
            "total_settled": Decimal("0.00"),
            "remaining": Decimal("0.00"),
            "record_count": 0,
        }
    )
    for record in records:
        row = groups[record.counterparty or "未填写对象"]
        row["counterparty"] = record.counterparty or "未填写对象"
        amount = _to_decimal(record.amount)
        settled = _to_decimal(record.settled_amount)
        row["total_debt"] += amount
        row["total_settled"] += settled
        row["remaining"] += max(amount - settled, Decimal("0.00"))
        row["record_count"] += 1
    summary = sorted(groups.values(), key=lambda row: row["remaining"], reverse=True)
    return [
        {
            "counterparty": row["counterparty"],
            "total_debt": _money(row["total_debt"]),
            "total_settled": _money(row["total_settled"]),
            "remaining": _money(row["remaining"]),
            "record_count": row["record_count"],
        }
        for row in summary
    ]


def _total_payable_result(
    db,
    farm_id: int,
    debt_summary: list[dict],
    limit: int,
) -> SkillResult:
    debt_summary = debt_summary[:limit]
    debt_remaining = _sum_remaining(debt_summary)
    labor_summary = get_unsettled_labor_summary(db, farm_id)
    labor_workers = labor_summary.get("workers", [])[:limit]
    labor_remaining = _to_decimal(labor_summary.get("total_unpaid"))
    total_remaining = debt_remaining + labor_remaining
    if total_remaining <= 0:
        return SkillResult(
            status=ResultStatus.SUCCESS,
            reply="您目前没有未结清的普通赊账欠款，也没有未付人工。",
            data={"summary": [], "labor_summary": [], "total_remaining": "0.00"},
        )
    return SkillResult(
        status=ResultStatus.SUCCESS,
        reply=_format_total_payable_reply(
            debt_summary, labor_workers, debt_remaining, labor_remaining
        ),
        data={
            "summary": debt_summary,
            "labor_summary": [
                {
                    "worker_name": row["worker_name"],
                    "unpaid_amount": _money(_to_decimal(row["unpaid_amount"])),
                    "entry_count": row["entry_count"],
                }
                for row in labor_workers
            ],
            "debt_remaining": _money(debt_remaining),
            "labor_remaining": _money(labor_remaining),
            "total_remaining": _money(total_remaining),
        },
    )


def _format_debt_reply(summary: list[dict], direction: str) -> str:
    title = "应收赊账汇总" if direction == _RECEIVABLE else "赊账欠款汇总"
    lines = [f"{title}：总剩余{_money(_sum_remaining(summary))}元"]
    for row in summary:
        lines.append(
            f"- {row['counterparty']}：原欠{row['total_debt']}元，"
            f"已还{row['total_settled']}元，剩余{row['remaining']}元，"
            f"{row['record_count']}笔"
        )
    return "\n".join(lines)


def _format_total_payable_reply(
    debt_summary, labor_workers, debt_remaining, labor_remaining
) -> str:
    lines = [
        f"您目前总欠款为 {_money(debt_remaining + labor_remaining)} 元，构成如下：",
        f"- 普通赊账：{_money(debt_remaining)} 元",
        f"- 未付人工：{_money(labor_remaining)} 元",
    ]
    if debt_summary:
        lines.extend(["", "普通赊账明细："])
        lines.extend(
            f"- {row['counterparty']}：剩余 {row['remaining']} 元，"
            f"{row['record_count']}笔"
            for row in debt_summary
        )
    if labor_workers:
        lines.extend(["", "未付人工明细："])
        lines.extend(
            f"- {row['worker_name']}：未付 "
            f"{_money(_to_decimal(row['unpaid_amount']))} 元，"
            f"{row['entry_count']}笔"
            for row in labor_workers
        )
    return "\n".join(lines)


def _empty_debt_reply(direction: str, counterparty: str | None) -> str:
    target = f"「{counterparty}」" if counterparty else ""
    if direction == _RECEIVABLE:
        return f"暂无{target}未结应收赊账。"
    return f"暂无{target}未结赊账欠款。"


def _normalize_direction(value) -> str:
    text = _clean(value)
    if text in {_RECEIVABLE, "应收", "别人欠我"}:
        return _RECEIVABLE
    if text in {_ALL, "全部"}:
        return _ALL
    return _PAYABLE


def _normalize_limit(value) -> int:
    if value in (None, ""):
        return 20
    try:
        return max(1, min(int(value), 100))
    except (TypeError, ValueError):
        return 20


def _normalize_scope(value) -> str:
    text = _clean(value)
    if text in {_TOTAL_PAYABLE, "total", "all_payable", "总欠款", "全部欠款"}:
        return _TOTAL_PAYABLE
    return _DEBT_ONLY


def _sum_remaining(summary: list[dict]) -> Decimal:
    return sum((_to_decimal(row["remaining"]) for row in summary), Decimal("0.00"))


def _to_decimal(value) -> Decimal:
    return Decimal(str(value or 0))


def _money(value: Decimal) -> str:
    return str(value.quantize(Decimal("0.01")))


def _clean(value) -> str | None:
    if value in (None, ""):
        return None
    text = str(value).strip()
    return text or None


def _validate_counterparty(counterparty) -> SkillResult | None:
    if (
        not counterparty
        or not isinstance(counterparty, str)
        or not counterparty.strip()
    ):
        return SkillResult(
            status=ResultStatus.FAILED,
            reply="还款失败：请提供债权人名称。",
        )
    return None


def _validate_settlement_amount(amount) -> SkillResult | None:
    try:
        normalized = Decimal(str(amount))
    except Exception:
        normalized = None
    if normalized is None or not normalized.is_finite() or normalized <= 0:
        return SkillResult(
            status=ResultStatus.FAILED,
            reply="还款失败：金额无效，请提供大于0的金额。",
        )
    return None


def _format_settle_reply(record, counterparty: str) -> str:
    settled_amount = getattr(record, "settled_amount", None)
    remaining_amount = getattr(record, "unsettled_amount", None)
    if remaining_amount is None and settled_amount is not None:
        remaining_amount = Decimal(str(record.amount)) - Decimal(str(settled_amount))
    return "，".join(
        [
            f"已更新{counterparty}账单",
            f"账单：{record.category}",
            f"已结：{settled_amount}元",
            f"剩余：{remaining_amount}元",
            f"settlement_status：{record.settlement_status}",
            f"日期 {record.record_date}",
        ]
    )
