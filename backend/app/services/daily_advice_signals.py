"""今日建议候选信号管线。"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import date
from datetime import timedelta
from decimal import Decimal
from typing import Any, Literal

from sqlalchemy.orm import Session

from app.models.cost import CostRecord
from app.models.planting import OperationWorkOrder

DailyAdviceCategory = Literal[
    "weather",
    "operation",
    "crop_stage",
    "finance",
    "setup",
    "record",
]

_CATEGORY_ORDER: dict[DailyAdviceCategory, int] = {
    "weather": 0,
    "operation": 1,
    "crop_stage": 2,
    "finance": 3,
    "setup": 4,
    "record": 5,
}

_CATEGORY_LIMITS: dict[DailyAdviceCategory, int] = {
    "weather": 1,
    "finance": 1,
    "operation": 2,
    "crop_stage": 2,
    "setup": 1,
    "record": 1,
}


@dataclass(slots=True)
class DailyAdviceCandidate:
    """今日建议生成前的结构化候选。"""

    id: str
    category: DailyAdviceCategory
    title_hint: str
    detail_hint: str
    priority: int
    due_date: date | None
    source_type: str
    source_id: int | None
    dedupe_key: str
    reason: str

    def to_meta(self) -> dict[str, Any]:
        """输出可稳定序列化的候选元数据。"""
        return {
            "id": self.id,
            "category": self.category,
            "title_hint": self.title_hint,
            "detail_hint": self.detail_hint,
            "priority": self.priority,
            "due_date": self.due_date.isoformat() if self.due_date else None,
            "source_type": self.source_type,
            "source_id": self.source_id,
            "dedupe_key": self.dedupe_key,
            "reason": self.reason,
        }


def rank_daily_advice_candidates(
    candidates: list[DailyAdviceCandidate],
    *,
    today: date | None = None,
    limit: int = 3,
) -> list[DailyAdviceCandidate]:
    """排序、去重并按类别抑制今日建议候选。"""
    if limit <= 0:
        return []

    reference_day = today or date.today()
    ranked = sorted(candidates, key=lambda item: _candidate_sort_key(item, reference_day))
    selected: list[DailyAdviceCandidate] = []
    seen_dedupe_keys: set[str] = set()
    category_counts: dict[DailyAdviceCategory, int] = {
        category: 0 for category in _CATEGORY_LIMITS
    }

    for candidate in ranked:
        if candidate.dedupe_key in seen_dedupe_keys:
            continue

        category_limit = _CATEGORY_LIMITS[candidate.category]
        if category_counts[candidate.category] >= category_limit:
            continue

        selected.append(candidate)
        seen_dedupe_keys.add(candidate.dedupe_key)
        category_counts[candidate.category] += 1

        if len(selected) >= limit:
            break

    return selected


def render_candidate_context(candidates: list[DailyAdviceCandidate]) -> str:
    """渲染给大模型使用的今日行动候选上下文。"""
    if not candidates:
        return "今日无明确高优先级行动候选。"

    lines = ["【今日行动候选】"]
    for index, candidate in enumerate(candidates, start=1):
        due = candidate.due_date.isoformat() if candidate.due_date else "none"
        lines.append(
            f"{index}. priority={candidate.priority} "
            f"category={candidate.category} "
            f"source={candidate.source_type} "
            f"due={due} "
            f"title={candidate.title_hint} "
            f"detail={candidate.detail_hint} "
            f"reason={candidate.reason}"
        )

    return "\n".join(lines)


def fingerprint_candidates(candidates: list[DailyAdviceCandidate]) -> str:
    """为候选集合生成稳定短指纹。"""
    payload = [candidate.to_meta() for candidate in candidates]
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()[:16]


def collect_daily_advice_candidates(
    db: Session,
    *,
    farm_id: int,
    today: date | None = None,
) -> list[DailyAdviceCandidate]:
    """收集今日建议候选信号。"""
    reference_day = today or date.today()
    return [
        *_collect_operation_candidates(db, farm_id=farm_id, today=reference_day),
        *_collect_finance_candidates(db, farm_id=farm_id, today=reference_day),
    ]


def _collect_operation_candidates(
    db: Session,
    *,
    farm_id: int,
    today: date,
) -> list[DailyAdviceCandidate]:
    horizon = today + timedelta(days=3)
    work_orders = (
        db.query(OperationWorkOrder)
        .filter(
            OperationWorkOrder.farm_id == farm_id,
            OperationWorkOrder.operation_date <= horizon,
        )
        .order_by(OperationWorkOrder.operation_date.asc(), OperationWorkOrder.id.asc())
        .all()
    )

    candidates: list[DailyAdviceCandidate] = []
    for work_order in work_orders:
        day_offset = (work_order.operation_date - today).days
        priority = 1 if day_offset <= 1 else 2
        title = _operation_title(work_order.operation_type, day_offset)
        candidates.append(
            DailyAdviceCandidate(
                id=f"operation:work_order:{work_order.id}",
                category="operation",
                title_hint=title,
                detail_hint=_operation_detail(work_order, day_offset),
                priority=priority,
                due_date=work_order.operation_date,
                source_type="operation_work_order",
                source_id=work_order.id,
                dedupe_key=f"operation_work_order:{work_order.id}",
                reason="作业单日期进入今日建议窗口",
            )
        )

    return candidates


def _collect_finance_candidates(
    db: Session,
    *,
    farm_id: int,
    today: date,
) -> list[DailyAdviceCandidate]:
    horizon = today + timedelta(days=3)
    debts = (
        db.query(CostRecord)
        .filter(
            CostRecord.farm_id == farm_id,
            CostRecord.record_subtype == "赊账",
            CostRecord.due_date.isnot(None),
            CostRecord.due_date <= horizon,
            CostRecord.settled_amount < CostRecord.amount,
            CostRecord.deleted_at.is_(None),
        )
        .order_by(CostRecord.due_date.asc(), CostRecord.id.asc())
        .all()
    )

    candidates: list[DailyAdviceCandidate] = []
    for debt in debts:
        day_offset = (debt.due_date - today).days
        overdue = day_offset < 0
        candidates.append(
            DailyAdviceCandidate(
                id=f"finance:cost_record:{debt.id}",
                category="finance",
                title_hint="赊账已逾期" if overdue else "赊账即将到期",
                detail_hint=_finance_detail(debt, day_offset),
                priority=1 if overdue else 2,
                due_date=debt.due_date,
                source_type="cost_record",
                source_id=debt.id,
                dedupe_key=f"finance:cost_record:{debt.id}",
                reason="赊账到期日进入今日建议窗口且尚未结清",
            )
        )

    return candidates


def _candidate_sort_key(
    candidate: DailyAdviceCandidate,
    today: date,
) -> tuple[int, int, int, str]:
    due_offset = (candidate.due_date - today).days if candidate.due_date else 99
    return (
        candidate.priority,
        due_offset,
        _CATEGORY_ORDER[candidate.category],
        candidate.id,
    )


def _operation_title(operation_type: str, day_offset: int) -> str:
    if day_offset < 0:
        return f"{operation_type}作业已逾期"
    if day_offset == 0:
        return f"今日安排{operation_type}"
    if day_offset == 1:
        return f"明日安排{operation_type}"
    return f"近期安排{operation_type}"


def _operation_detail(work_order: OperationWorkOrder, day_offset: int) -> str:
    if day_offset < 0:
        time_text = f"已逾期 {abs(day_offset)} 天"
    elif day_offset == 0:
        time_text = "今天到期"
    else:
        time_text = f"{day_offset} 天后到期"

    note = f"，备注：{work_order.note}" if work_order.note else ""
    return f"{work_order.operation_date.isoformat()} {work_order.operation_type}，{time_text}{note}"


def _finance_detail(debt: CostRecord, day_offset: int) -> str:
    counterparty = debt.counterparty or "未标注对象"
    if day_offset < 0:
        time_text = f"已逾期 {abs(day_offset)} 天"
    elif day_offset == 0:
        time_text = "今天到期"
    else:
        time_text = f"{day_offset} 天后到期"

    return (
        f"{counterparty} 赊账未结 {_money(debt.unsettled_amount)} 元，"
        f"到期日 {debt.due_date.isoformat()}，{time_text}"
    )


def _money(value: Decimal | int | float | str | None) -> str:
    amount = Decimal(str(value or "0")).quantize(Decimal("0.01"))
    return f"{amount:.2f}"
