"""持久化 Task Context selector。"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from app.context.core.models import ContextBlock
from app.context.task_state.models import AgentTaskState
from app.context.task_state.store import AgentTaskStateStore


class TaskStateSelector:
    """读取当前会话最近一个可恢复任务状态。"""

    def select(
        self,
        db: Session,
        farm_id: int,
        user_id: str | None = None,
        session_id: str | None = None,
        **_kwargs,
    ) -> list[ContextBlock]:
        task = AgentTaskStateStore(db).get_active_task(
            farm_id=farm_id,
            user_id=user_id,
            session_id=session_id,
        )
        if task is None:
            return []
        return [
            ContextBlock(
                key="active_task_state",
                source="task_state",
                purpose="当前可恢复任务状态",
                content=self._format_content(task),
                priority=85,
                compressible=True,
                min_tokens=48,
                ttl_seconds=300,
                metadata=self._metadata(task),
            )
        ]

    @staticmethod
    def _format_content(task: AgentTaskState) -> str:
        lines = [
            f"目标：{task.goal}",
            f"状态：{task.status}",
        ]
        entities = _format_entities(task.entities_json)
        if entities:
            lines.append(f"已知实体：{entities}")
        observations = _format_list(task.observations_json)
        if observations:
            lines.append(f"已观察信息：{observations}")
        missing = _format_list(task.missing_information_json)
        if missing:
            lines.append(f"缺失信息：{missing}")
        if task.next_action:
            lines.append(f"下一步动作：{task.next_action}")
        instruction = _task_instruction(task)
        if instruction:
            lines.append(f"处理要求：{instruction}")
        return "\n".join(lines)

    @staticmethod
    def _metadata(task: AgentTaskState) -> dict[str, Any]:
        expires_at = task.expires_at
        return {
            "task_id": task.task_id,
            "task_type": task.task_type,
            "status": task.status,
            "entities": _metadata_entities(task.entities_json),
            "missing_information": _metadata_list(task.missing_information_json),
            "expires_at": expires_at.isoformat()
            if isinstance(expires_at, datetime)
            else "",
            "layer": "working",
            "cache_scope": "session",
        }


def _format_entities(value: Any) -> str:
    if not isinstance(value, dict) or not value:
        return ""
    parts = []
    for key, item in value.items():
        if isinstance(item, dict | list):
            continue
        parts.append(f"{key}={item}")
    return "；".join(parts)


def _format_list(value: Any) -> str:
    if not isinstance(value, list):
        return ""
    return "；".join(str(item) for item in value[:6] if item not in (None, ""))


def _task_instruction(task: AgentTaskState) -> str:
    missing = _metadata_list(task.missing_information_json)
    if missing:
        return f"优先追问缺失信息：{missing}；不要展开长篇方案或跳到无关建议。"
    if task.task_type == "planting_plan":
        return (
            "如果用户表达“可以、可以了、按这个来、确认”，"
            "优先询问是否把方案落地为作物模板、茬口和种植单元；"
            "缺少地块或种植单元名称时先追问名称；"
            "不要只用“随时叫我”结束。"
        )
    if task.task_type == "crop_cycle_setup":
        return (
            "如果信息已补齐，优先生成待确认写入计划；"
            "缺少种植单元名称时只追问名称，不要重新讲完整种植方案。"
        )
    return ""


def _metadata_entities(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    allowed = {
        "crop",
        "crop_name",
        "variety",
        "cycle_name",
        "season",
        "start_date",
        "area_mu",
        "area_target",
        "greenhouse",
        "planting_unit",
    }
    return {
        key: _metadata_value(item)
        for key, item in value.items()
        if key in allowed and _metadata_value(item) not in (None, "", {}, [])
    }


def _metadata_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: _metadata_value(item)
            for key, item in value.items()
            if key in {"name", "area_mu", "should_create"}
            and _metadata_value(item) not in (None, "", {}, [])
        }
    if isinstance(value, list):
        return [str(item) for item in value[:6] if item not in (None, "")]
    if isinstance(value, str | int | float | bool):
        return value
    return None


def _metadata_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value[:6] if item not in (None, "")]


__all__ = ["TaskStateSelector"]
