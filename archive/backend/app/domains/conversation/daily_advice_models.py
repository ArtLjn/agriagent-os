"""今日建议候选模型、排序和渲染工具。"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Literal

from app.domains.conversation.agent_schemas import (
    AdviceItem,
    DailyAdviceAction,
    DailyAdviceCompact,
    DailyAdviceDetailView,
    DailyAdviceEvidence,
    DailyAdviceGeneration,
    DailyAdviceHeroBadge,
    DailyAdviceOverview,
    DailyAdviceOverviewMetric,
    DailyAdviceRelatedEntry,
    DailyAdviceResponse,
    DailyAdviceStep,
)

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


@dataclass(frozen=True, slots=True)
class DailyAdviceCategoryDefault:
    """每日建议类别默认展示配置。"""

    icon: str
    icon_color: str
    level: str
    steps: tuple[str, str]
    actions: tuple[str, ...]
    related_title: str


DAILY_ADVICE_CATEGORY_DEFAULTS: dict[
    DailyAdviceCategory, DailyAdviceCategoryDefault
] = {
    "weather": DailyAdviceCategoryDefault(
        icon="CloudSun",
        icon_color="amber",
        level="urgent",
        steps=("查看天气窗口并避开极端时段", "调整今日作业时间和人员安排"),
        actions=("ask_agent", "create_work_order"),
        related_title="天气风险",
    ),
    "operation": DailyAdviceCategoryDefault(
        icon="ClipboardList",
        icon_color="green",
        level="important",
        steps=("确认作业地块、人员和物料", "完成后记录执行结果和异常情况"),
        actions=("create_work_order", "ask_agent"),
        related_title="关联作业",
    ),
    "crop_stage": DailyAdviceCategoryDefault(
        icon="Sprout",
        icon_color="emerald",
        level="important",
        steps=("巡查当前生育期关键长势", "按阶段任务补齐水肥和管护动作"),
        actions=("ask_agent", "create_work_order"),
        related_title="茬口阶段",
    ),
    "finance": DailyAdviceCategoryDefault(
        icon="CircleDollarSign",
        icon_color="blue",
        level="important",
        steps=("核对到期日期和往来对象", "确认后安排收付或补充备注"),
        actions=("ask_agent",),
        related_title="资金事项",
    ),
    "setup": DailyAdviceCategoryDefault(
        icon="Settings",
        icon_color="violet",
        level="normal",
        steps=("补充农场、作物或茬口基础信息", "完善后重新查看今日建议"),
        actions=("ask_agent",),
        related_title="基础配置",
    ),
    "record": DailyAdviceCategoryDefault(
        icon="NotebookPen",
        icon_color="slate",
        level="normal",
        steps=("回顾今天已完成的农事动作", "补录关键照片、用工或投入品记录"),
        actions=("ask_agent",),
        related_title="经营记录",
    ),
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
    ranked = sorted(
        candidates, key=lambda item: _candidate_sort_key(item, reference_day)
    )
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
    encoded = json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()[:16]


def build_daily_advice_item_skeletons(
    candidates: list[DailyAdviceCandidate],
) -> list[AdviceItem]:
    """把候选信号转换为确定性的 v2 建议骨架。"""
    return [_build_daily_advice_item_skeleton(candidate) for candidate in candidates]


def build_daily_advice_overview(
    *,
    weather_summary: str | None = None,
    work_order_count: int = 0,
    pending_count: int = 0,
) -> DailyAdviceOverview:
    """生成首页经营态势概览。"""
    work_order_count = max(0, work_order_count)
    pending_count = max(0, pending_count)
    weather_value = weather_summary or "天气平稳"
    work_order_level = "important" if work_order_count else "normal"
    pending_level = "urgent" if pending_count else "normal"
    score = _overview_score(
        weather_summary=weather_summary,
        work_order_count=work_order_count,
        pending_count=pending_count,
    )
    subtitle = (
        f"{weather_value}，今日有 {work_order_count} 项作业、"
        f"{pending_count} 项待处理"
    )
    return DailyAdviceOverview(
        score=score,
        subtitle=subtitle,
        metrics=[
            DailyAdviceOverviewMetric(
                key="weather",
                label="天气",
                value=weather_value,
                level="important" if weather_summary else "normal",
                icon="CloudSun",
            ),
            DailyAdviceOverviewMetric(
                key="work_order",
                label="作业",
                value=f"{work_order_count}项",
                level=work_order_level,
                icon="ClipboardList",
            ),
            DailyAdviceOverviewMetric(
                key="pending",
                label="待处理",
                value=f"{pending_count}项",
                level=pending_level,
                icon="Bell",
            ),
        ],
    )


def build_daily_advice_empty_response(
    *,
    cycle_id: int | None = None,
    created_at: datetime | date | None = None,
) -> DailyAdviceResponse:
    """生成无高优先级候选时可展示的 empty 模式响应。"""
    timestamp = _coerce_datetime(created_at)
    item = AdviceItem(
        id="empty-today",
        category="record",
        level="normal",
        source_type="system",
        source_id=None,
        priority=3,
        compact=DailyAdviceCompact(
            title="今日暂无高优先级事项",
            subtitle="目前没有紧急风险，建议完成基础巡田并补齐今日记录。",
            icon="NotebookPen",
            icon_color="slate",
        ),
        detail_view=DailyAdviceDetailView(
            title="今日暂无高优先级事项",
            description="当前没有识别到必须立即处理的天气、作业或资金风险，可按常规节奏完成巡田和记录。",
            hero_badges=[
                DailyAdviceHeroBadge(label="状态", value="平稳", level="normal"),
            ],
            evidence=[],
            steps=[
                DailyAdviceStep(
                    order=1,
                    title="完成一次基础巡田",
                    description="重点查看苗情、水分、病虫害和设施状态。",
                ),
                DailyAdviceStep(
                    order=2,
                    title="补齐今日经营记录",
                    description="记录已完成作业、投入品、用工和现场照片。",
                ),
            ],
            related=[],
            actions=[DailyAdviceAction(type="ask_agent", label="问问芽芽")],
        ),
    )
    return DailyAdviceResponse(
        cycle_id=cycle_id,
        preview="暂无紧急建议",
        overview=build_daily_advice_overview(),
        items=[item],
        generation=DailyAdviceGeneration(mode="empty", retry_count=0, cache_hit=False),
        created_at=timestamp,
    )


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


def _build_daily_advice_item_skeleton(candidate: DailyAdviceCandidate) -> AdviceItem:
    default = DAILY_ADVICE_CATEGORY_DEFAULTS[candidate.category]
    compact_subtitle = _fit_text(
        candidate.detail_hint,
        min_length=15,
        max_length=50,
    )
    compact = DailyAdviceCompact(
        title=candidate.title_hint[:12],
        subtitle=compact_subtitle,
        icon=default.icon,
        icon_color=default.icon_color,
    )
    detail_view = DailyAdviceDetailView(
        title=candidate.title_hint,
        description=_fit_text(
            _detail_description(candidate),
            min_length=20,
            max_length=120,
        ),
        hero_badges=_build_hero_badges(candidate, default),
        evidence=[
            DailyAdviceEvidence(
                title="候选依据",
                description=candidate.reason or candidate.detail_hint,
                source_type=candidate.source_type,
                source_id=candidate.source_id,
            )
        ],
        steps=[
            DailyAdviceStep(order=index, title=step, description=candidate.detail_hint)
            for index, step in enumerate(default.steps, start=1)
        ],
        related=[
            DailyAdviceRelatedEntry(
                title=default.related_title,
                description=candidate.detail_hint,
                source_type=candidate.source_type,
                source_id=candidate.source_id,
            )
        ],
        actions=[
            DailyAdviceAction(
                type=action_type,
                label=_action_label(action_type),
                payload=_action_payload(action_type, candidate),
            )
            for action_type in default.actions
        ],
    )
    return AdviceItem(
        id=candidate.id,
        category=candidate.category,
        level=default.level,
        source_type=candidate.source_type,
        source_id=candidate.source_id,
        compact=compact,
        detail_view=detail_view,
        priority=candidate.priority,
    )


def _detail_description(candidate: DailyAdviceCandidate) -> str:
    reason = candidate.reason.strip()
    detail = candidate.detail_hint.strip()
    if reason and reason not in detail:
        description = f"{detail}依据：{reason}"
    else:
        description = detail or reason
    return description[:120]


def _fit_text(value: str, *, min_length: int, max_length: int) -> str:
    text = value.strip() or "暂无详细说明"
    while len(text) < min_length:
        text = f"{text}，请结合现场情况处理"
    return text[:max_length]


def _build_hero_badges(
    candidate: DailyAdviceCandidate,
    default: DailyAdviceCategoryDefault,
) -> list[DailyAdviceHeroBadge]:
    badges = [
        DailyAdviceHeroBadge(
            label="级别",
            value=_priority_label(candidate.priority),
            level=default.level,
            icon=default.icon,
        )
    ]
    if candidate.due_date:
        badges.append(
            DailyAdviceHeroBadge(
                label="日期",
                value=candidate.due_date.isoformat(),
                level=default.level,
                icon="Calendar",
            )
        )
    return badges


def _priority_label(priority: int) -> str:
    if priority == 1:
        return "紧急"
    if priority == 2:
        return "重要"
    return "常规"


def _action_label(action_type: str) -> str:
    labels = {
        "ask_agent": "问问芽芽",
        "create_work_order": "生成作业单",
    }
    return labels.get(action_type, action_type)


def _action_payload(
    action_type: str,
    candidate: DailyAdviceCandidate,
) -> dict[str, Any]:
    payload: dict[str, Any] = {"candidate_id": candidate.id}
    if action_type == "create_work_order":
        payload.update(
            {
                "source_type": candidate.source_type,
                "source_id": candidate.source_id,
                "title": candidate.title_hint,
            }
        )
    return payload


def _overview_score(
    *,
    weather_summary: str | None,
    work_order_count: int,
    pending_count: int,
) -> int:
    score = 88
    if weather_summary:
        score -= 8
    if work_order_count > 10:
        score -= 6
    elif work_order_count:
        score -= 3
    if pending_count:
        score -= min(12, pending_count * 4)
    return max(0, min(100, score))


def _coerce_datetime(value: datetime | date | None) -> datetime:
    if value is None:
        return datetime.now()
    if isinstance(value, datetime):
        return value
    return datetime.combine(value, datetime.min.time())
