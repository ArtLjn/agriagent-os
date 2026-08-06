"""Task Graph Phase 1 任务类型路由。"""

from __future__ import annotations

import re
from typing import Any

from pydantic import BaseModel, Field

from app.agent.task_graph.models import TaskType

TASK_WORDS = ("规划", "计划", "方案", "茬口", "安排")
CROP_WORDS = ("草莓", "番茄", "西红柿", "水稻", "玉米", "小麦", "黄瓜", "蓝莓")
SEASON_OR_TIME_WORDS = (
    "春季",
    "夏季",
    "秋季",
    "冬季",
    "春天",
    "夏天",
    "秋天",
    "冬天",
    "本月",
    "下月",
    "今年",
    "明年",
)
AREA_OR_PLOT_PATTERN = re.compile(
    r"(\d+(?:\.\d+)?|[零〇一二两三四五六七八九十百]+)\s*亩|地块|每块|块地"
)
RETRY_OR_RESUME_WORDS = ("重试", "再试", "继续", "恢复", "上次", "失败")


class RouteDecision(BaseModel):
    task_type: TaskType
    intent: str
    matched_signals: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


def route_task_type(user_input: str) -> RouteDecision:
    """把用户请求路由到 Phase 1 支持的 Task Graph 类型。"""

    normalized = user_input.strip()
    matched_signals = _matched_planting_plan_signals(normalized)
    if _has_retry_or_resume_intent(normalized):
        return RouteDecision(
            task_type="retry_or_resume",
            intent="retry_or_resume",
            matched_signals=matched_signals,
            metadata={"retry_or_resume": True},
        )
    if _is_planting_plan_entry(normalized, matched_signals):
        return RouteDecision(
            task_type="planting_plan",
            intent="plan_crop_cycle",
            matched_signals=matched_signals,
        )
    return RouteDecision(
        task_type="legacy_skill_fallback",
        intent="unknown",
        matched_signals=matched_signals,
    )


def _matched_planting_plan_signals(user_input: str) -> list[str]:
    signals: list[str] = []
    if any(word in user_input for word in TASK_WORDS):
        signals.append("task_word")
    if any(word in user_input for word in CROP_WORDS):
        signals.append("crop")
    if any(word in user_input for word in SEASON_OR_TIME_WORDS):
        signals.append("season_or_time")
    if AREA_OR_PLOT_PATTERN.search(user_input):
        signals.append("area_or_plot")
    return signals


def _is_planting_plan_entry(user_input: str, matched_signals: list[str]) -> bool:
    signals = set(matched_signals)
    if {"task_word", "crop", "season_or_time", "area_or_plot"}.issubset(signals):
        return True
    return "task_word" in signals and "茬口" in user_input


def _has_retry_or_resume_intent(user_input: str) -> bool:
    return any(word in user_input for word in RETRY_OR_RESUME_WORDS)
