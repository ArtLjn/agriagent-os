"""查询能力菜单的轻量多轮状态。"""

import re
from dataclasses import dataclass

from app.memory.models import TemporaryTaskState
from app.memory.service import InMemoryMemoryService

QUERY_MENU_TASK_ID = "query_capability_menu"
QUERY_MENU_STATUS = "awaiting_selection"

_NUMBER_RE = re.compile(r"^\s*(\d{1,2})\s*[.。]?\s*$")
_SELECTION_PROMPT = (
    "用户选择了上一轮你给出的第 {number} 个选项。"
    "请结合本会话上文理解这个编号对应的查询方向；"
    "如果需要查询业务数据，请自行选择合适工具执行，不要让用户重复选择。"
)
_MENU_HINTS = (
    "查数据",
    "查询数据",
    "可以查什么",
    "可以查啥",
    "能查什么",
    "能查啥",
    "查啥",
    "查什么",
    "几个选项",
    "给我选项",
    "我选择查啥",
    "选择查什么",
    "选啥",
)


@dataclass(frozen=True)
class QueryMenuResolution:
    """查询菜单解析结果。"""

    reply: str | None = None
    rewritten_message: str | None = None


async def resolve_query_capability_menu(
    *,
    memory_service: InMemoryMemoryService,
    user_id: str,
    farm_id: int,
    session_id: str | None,
    message: str,
) -> QueryMenuResolution:
    """处理查询能力菜单和后续编号选择。"""
    selected_number = _extract_selected_number(message)
    if selected_number is not None:
        state = await memory_service.short_term.get_temporary_task_state(
            user_id=user_id,
            farm_id=farm_id,
            session_id=session_id,
        )
        if _is_query_menu_state(state):
            await memory_service.short_term.set_temporary_task_state(
                user_id=user_id,
                farm_id=farm_id,
                session_id=session_id,
                task_state=None,
            )
            return QueryMenuResolution(
                rewritten_message=_SELECTION_PROMPT.format(number=selected_number)
            )

    if _looks_like_query_menu_request(message):
        await memory_service.short_term.set_temporary_task_state(
            user_id=user_id,
            farm_id=farm_id,
            session_id=session_id,
            task_state=TemporaryTaskState(
                task_id=QUERY_MENU_TASK_ID,
                status=QUERY_MENU_STATUS,
                data={"source": "model_generated_query_options"},
            ),
        )

    return QueryMenuResolution()


async def resolve_query_menu_or_message(
    *,
    memory_service: InMemoryMemoryService,
    user_id: str,
    farm_id: int,
    session_id: str | None,
    message: str,
) -> tuple[str, str | None]:
    """返回实际交给 Agent 的消息，以及可直接回复的菜单文案。"""
    resolution = await resolve_query_capability_menu(
        memory_service=memory_service,
        user_id=user_id,
        farm_id=farm_id,
        session_id=session_id,
        message=message,
    )
    return resolution.rewritten_message or message, resolution.reply


def _looks_like_query_menu_request(message: str) -> bool:
    normalized = message.strip().lower()
    if not normalized:
        return False
    return any(hint in normalized for hint in _MENU_HINTS)


def _extract_selected_number(message: str) -> str | None:
    match = _NUMBER_RE.match(message)
    if match is None:
        return None
    return match.group(1)


def _is_query_menu_state(state: TemporaryTaskState | None) -> bool:
    if state is None:
        return False
    return state.task_id == QUERY_MENU_TASK_ID and state.status == QUERY_MENU_STATUS
