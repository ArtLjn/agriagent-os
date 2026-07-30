"""Agent 任务类型共享定义。"""

from __future__ import annotations

from typing import Literal

TASK_TYPE_VALUES = (
    "planting_plan",
    "crop_cycle_setup",
    "field_work_assignment",
    "inventory_management",
    "cost_analysis",
    "pest_diagnosis",
    "retry_or_resume",
    "legacy_skill_fallback",
)

TaskType = Literal[
    "planting_plan",
    "crop_cycle_setup",
    "field_work_assignment",
    "inventory_management",
    "cost_analysis",
    "pest_diagnosis",
    "retry_or_resume",
    "legacy_skill_fallback",
]

__all__ = ["TASK_TYPE_VALUES", "TaskType"]
