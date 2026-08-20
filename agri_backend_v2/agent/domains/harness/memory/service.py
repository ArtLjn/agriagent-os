"""Conversation memory.

Two layers, both persisted as JSON (no SQL):
  - short_term: per-conversation message log (last N messages)
  - long_term:  per-conversation facts (extracted user preferences,
                key entities, last-mentioned farm)

Each conversation has its own short-term file under data/conversations/.
Long-term is shared in data/memory.json keyed by conversation_id.

Mirrors archive/backend/app/memory/ but stripped to MVP essentials:
no summarizer, no vector store, just JSON.
"""

from __future__ import annotations

import json
import logging
import threading
from pathlib import Path
from typing import Any

# 迁移期间继续读取原有 JSON 数据，但通过本模块唯一适配；生产 Runtime
# 不应再直接依赖该路径，完成 Mongo parity 后由 legacy_json adapter 接管。
_DATA_DIR = Path(__file__).resolve().parents[3] / "platforms" / "legacy_json" / "data"
_CONV_DIR = _DATA_DIR / "conversations"
_STATE_DIR = _DATA_DIR / "states"
_MEMORY_FILE = _DATA_DIR / "memory.json"
_LOCK = threading.Lock()
logger = logging.getLogger(__name__)

# Keep last N messages per conversation to bound context size.
MAX_SHORT_TERM_MESSAGES = 20


def _empty_session_view(
    conversation_id: str,
    *,
    user_id: str = "",
    farm_id: int = 1,
    source_status: str = "empty",
) -> dict[str, Any]:
    """构造可安全注入 Context 的空 Session View。"""
    return {
        "conversation_id": conversation_id,
        "user_id": user_id,
        "farm_id": farm_id,
        "messages": [],
        "summary": None,
        "summary_revision": 0,
        "conversation_revision": 0,
        "reset_generation": 0,
        "pending_action": None,
        "task_state": None,
        "source_status": source_status,
        # 长期记忆本阶段只保留空结果，不把旧 JSON 事实默认注入。
        "long_term": {},
    }


async def get_session_view(
    conversation_id: str,
    *,
    user_id: str = "",
    farm_id: int = 1,
    legacy_key: str | None = None,
) -> dict[str, Any]:
    """读取短时记忆 Session View。

    Mongo 优先读取只在 `memory_mongo_read` 开关打开时生效；否则保留
    legacy JSON fallback，便于迁移期间回滚。Runtime 只调用本入口，不接触
    具体存储路径。长期记忆在本阶段固定返回空结果。
    """
    from agent.config import settings

    flags = settings.context.feature_flags
    if settings.mongodb.enabled and flags.get("memory_mongo_read", False):
        try:
            from agent.platforms.persistence.mongo import chat_store

            state_reader = getattr(chat_store, "get_conversation_state", None)
            state = (
                await state_reader(
                    conversation_id,
                    user_id=user_id,
                    farm_id=farm_id,
                )
                if state_reader is not None
                else None
            )
            recent = await chat_store.load_recent(
                conversation_id,
                limit=max(settings.context.recent_turn_limit * 2, 2),
                user_id=user_id,
                farm_id=farm_id,
            )
            if state is None:
                state = {}
            if state.get("status") == "unavailable":
                return _empty_session_view(
                    conversation_id,
                    user_id=user_id,
                    farm_id=farm_id,
                    source_status="unavailable",
                )
            return {
                **_empty_session_view(
                    conversation_id,
                    user_id=user_id,
                    farm_id=farm_id,
                    source_status="mongo",
                ),
                "messages": project_recent_turns(
                    _dialogue_messages(recent), settings.context.recent_turn_limit
                ),
                "summary": state.get("summary"),
                "summary_revision": int(state.get("summary_revision", 0) or 0),
                "conversation_revision": int(
                    state.get("conversation_revision", 0) or 0
                ),
                "reset_generation": int(state.get("reset_generation", 0) or 0),
                "pending_action": state.get("pending_action"),
                "task_state": state.get("task_state"),
                "summary_status": state.get("summary_status", "ready"),
            }
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "memory session view mongo read failed; fallback to legacy: %s", exc
            )

    fallback_id = legacy_key or conversation_id
    legacy_state = load_legacy_state(fallback_id)
    messages = project_recent_turns(
        load_messages(fallback_id), settings.context.recent_turn_limit
    )
    source = "legacy_json_fallback" if messages or legacy_state else "empty"
    return {
        **_empty_session_view(
            conversation_id,
            user_id=user_id,
            farm_id=farm_id,
            source_status=source,
        ),
        "messages": messages,
        "summary": legacy_state.get("summary"),
        "summary_revision": int(legacy_state.get("summary_revision", 0) or 0),
        "reset_generation": int(legacy_state.get("reset_generation", 0) or 0),
        "summary_status": legacy_state.get("summary_status", "ready"),
        "pending_action": legacy_state.get("pending_action"),
        "task_state": legacy_state.get("task_state"),
    }


async def search(
    *,
    user_id: str,
    farm_id: int,
    query: str = "",
    scope: str = "farm",
    dependencies: list[str] | None = None,
) -> list[dict[str, Any]]:
    """长期记忆检索端口；当前阶段明确返回空结果。"""
    del user_id, farm_id, query, scope, dependencies
    return []


async def observe(
    *,
    user_id: str,
    farm_id: int,
    conversation_id: str,
    turn_id: str,
    user_input: str,
    assistant_answer: str,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """记录长期记忆 observation 的接口占位，不直接沉淀事实。"""
    del user_id, farm_id, conversation_id, turn_id, user_input, assistant_answer, metadata
    return {"accepted": False, "persisted": False, "status": "deferred"}


async def persist_session_turn(
    *,
    conversation_id: str,
    user_id: str,
    farm_id: int,
    farm_uid: str,
    expected_revision: int,
    turn_id: str,
    pending_action: dict[str, Any] | None = None,
    task_state: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """在可见消息终态后推进 Conversation state revision。"""
    from agent.config import settings

    if not settings.context.feature_flags.get("conversation_state_v2", False):
        return {"ok": True, "status": "disabled", "source_status": "legacy_json_fallback"}
    from agent.platforms.persistence.mongo import chat_store

    return await chat_store.save_conversation_state(
        conversation_id,
        user_id=user_id,
        farm_id=farm_id,
        farm_uid=farm_uid,
        expected_revision=expected_revision,
        pending_action=pending_action,
        task_state=task_state,
        idempotency_key=f"turn:{turn_id}:session-state",
    )


async def reset_session(
    conversation_id: str,
    *,
    user_id: str = "",
    farm_id: int = 1,
    legacy_key: str | None = None,
) -> dict[str, Any]:
    """清除 active Session View；用户可见 Mongo 消息不在此删除。"""
    reset_conversation(legacy_key or conversation_id)
    from agent.config import settings

    if settings.mongodb.enabled:
        try:
            from agent.platforms.persistence.mongo import chat_store

            resetter = getattr(chat_store, "reset_conversation_state", None)
            if resetter is not None:
                return await resetter(
                    conversation_id,
                    user_id=user_id,
                    farm_id=farm_id,
                )
        except Exception as exc:  # noqa: BLE001
            return {
                "ok": False,
                "status": "unavailable",
                "code": "conversation_state_reset_failed",
                "message": str(exc),
            }
    return {"ok": True, "status": "legacy_json_fallback", "reset_generation": 1}


def _ensure_dirs() -> None:
    _CONV_DIR.mkdir(parents=True, exist_ok=True)
    _STATE_DIR.mkdir(parents=True, exist_ok=True)


def _conv_file(conversation_id: str) -> Path:
    safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in conversation_id)
    return _CONV_DIR / f"{safe}.json"


def _state_file(conversation_id: str) -> Path:
    safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in conversation_id)
    return _STATE_DIR / f"{safe}.json"


def load_legacy_state(conversation_id: str) -> dict[str, Any]:
    """读取迁移期间的本地 Session state fallback。"""
    _ensure_dirs()
    path = _state_file(conversation_id)
    if not path.exists():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    return value if isinstance(value, dict) else {}


def save_legacy_summary(conversation_id: str, summary: str) -> None:
    """将摘要独立于消息窗口保存，避免伪 assistant 消息被过滤。"""
    _ensure_dirs()
    state = load_legacy_state(conversation_id)
    state["summary"] = summary
    state["summary_revision"] = int(state.get("summary_revision", 0) or 0) + 1
    state["summary_status"] = "ready"
    _state_file(conversation_id).write_text(
        json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def load_messages(conversation_id: str) -> list[dict[str, Any]]:
    """加载可注入 Prompt 的对话历史，不返回工具调用中间态。"""
    _ensure_dirs()
    f = _conv_file(conversation_id)
    if not f.exists():
        return []
    try:
        return _dialogue_messages(json.loads(f.read_text(encoding="utf-8")))
    except (json.JSONDecodeError, OSError):
        return []


def project_recent_turns(
    messages: list[dict[str, Any]], recent_turn_limit: int
) -> list[dict[str, Any]]:
    """按完整 user/assistant Turn 投影最近窗口，而非按单条消息截断。"""
    pairs: list[list[dict[str, Any]]] = []
    pending: list[dict[str, Any]] = []
    for message in messages:
        if message.get("role") == "user":
            pending = [message]
        elif message.get("role") == "assistant" and pending:
            pending.append(message)
            pairs.append(pending)
            pending = []
    selected = pairs[-max(1, recent_turn_limit) :]
    return [message for pair in selected for message in pair]


def save_messages(conversation_id: str, messages: list[dict[str, Any]]) -> None:
    """持久化用户与最终答复；工具轨迹只属于当前 turn。"""
    _ensure_dirs()
    trimmed = _dialogue_messages(messages)[-MAX_SHORT_TERM_MESSAGES:]
    _conv_file(conversation_id).write_text(
        json.dumps(trimmed, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def persist_turn(conversation_id: str, messages: list[dict[str, Any]]) -> None:
    """Memory Service 的同步兼容写入口；具体 fallback 由本模块封装。"""
    save_messages(conversation_id, messages)


def load_long_term(conversation_id: str) -> dict[str, Any]:
    """Load long-term facts for a conversation. Empty dict if missing."""
    _ensure_dirs()
    if not _MEMORY_FILE.exists():
        return {}
    try:
        all_mem = json.loads(_MEMORY_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    return all_mem.get(conversation_id, {})


def snapshot(conversation_id: str) -> dict[str, Any]:
    """Combined short-term + long-term snapshot for prompt building."""
    return {
        "conversation_id": conversation_id,
        "messages": load_messages(conversation_id),
        "long_term": load_long_term(conversation_id),
    }


def _dialogue_messages(messages: Any) -> list[dict[str, str]]:
    """保留已完成对话 + 工具结果摘要（不保留原始工具数据）。

    工具结果摘要拼接到随后 assistant 回复的前面，让下一 turn 的 LLM
    能看到上一 turn 查过什么、结果是什么，避免重复查询。
    """
    if not isinstance(messages, list):
        return []

    dialogue: list[dict[str, str]] = []
    pending_user: dict[str, str] | None = None
    pending_tool_summaries: list[str] = []

    for message in messages:
        if not isinstance(message, dict):
            continue
        role = message.get("role")

        # 收集工具结果摘要
        if role == "tool":
            summary = _summarize_tool_result(
                message.get("name", ""),
                message.get("content", ""),
            )
            if summary:
                pending_tool_summaries.append(summary)
            continue

        # assistant with tool_calls = 工具调用触发，跳过（摘要由 tool result 提供）
        if role == "assistant" and message.get("tool_calls"):
            continue

        content = message.get("content")
        if role not in {"user", "assistant"} or not isinstance(content, str):
            continue
        if not content.strip():
            continue

        # 如果有待处理的工具摘要，拼接到 assistant 回复前
        if pending_tool_summaries and role == "assistant":
            tool_block = "; ".join(pending_tool_summaries)
            content = f"[上轮工具调用: {tool_block}]\n\n{content}"
            pending_tool_summaries = []

        normalized = {"role": role, "content": content}
        if role == "user":
            # 没有最终答复的旧用户消息不能成为下一轮待办。
            pending_user = normalized
        elif pending_user is not None:
            dialogue.extend([pending_user, normalized])
            pending_user = None
    return dialogue


def _summarize_tool_result(tool_name: str, content: Any) -> str:
    """从工具结果中提取关键信息摘要（≤200 字符）。

    使用数据驱动的规则注册表，按 result 中的 key 匹配提取规则。
    新增工具类型只需在 _LIST_RULES 中加一行，不需要改代码逻辑。
    """
    result = _parse_tool_content(content)
    if not isinstance(result, dict):
        return ""

    # 按规则注册表匹配列表型结果
    for rule in _LIST_RULES:
        items = result.get(rule["key"])
        if isinstance(items, list) and items:
            return _format_list_summary(tool_name, rule, items)

    # wages 查询结果（嵌套 summary.workers 结构）
    workers = result.get("workers")
    if isinstance(workers, list) and workers and "summary" in result:
        parts = [
            f"{w.get('worker_name', '?')}({w.get('total_unpaid', 0)})" for w in workers
        ]
        return f"{tool_name}→{len(workers)}工人工资:{','.join(parts)}"

    # 通用 fallback：输出 key=value（保留写操作返回的关键 ID 和状态）
    return _format_generic_summary(tool_name, result)


def _parse_tool_content(content: Any) -> dict | None:
    """解析工具结果内容为 dict。"""
    if isinstance(content, str):
        try:
            parsed = json.loads(content)
        except (json.JSONDecodeError, TypeError):
            return None
    elif isinstance(content, dict):
        parsed = content
    else:
        return None
    return parsed if isinstance(parsed, dict) else None


# 列表型结果的摘要规则注册表
# 新增工具类型只需加一行：key=result中的键, label=摘要标签,
# name=实体名称字段, id=实体ID字段, extra=额外提取字段, max=最大条目数
_LIST_RULES: list[dict[str, Any]] = [
    {
        "key": "workers",
        "label": "工人",
        "name": "name",
        "id": "id",
        "extra": ["default_pay_type", "default_unit_price"],
        "max": 10,
    },
    {
        "key": "work_orders",
        "label": "作业单",
        "name": "operation_type",
        "id": "id",
        "extra": [],
        "max": 10,
    },
    {
        "key": "cycles",
        "label": "茬口",
        "name": "name",
        "id": "id",
        "extra": [],
        "max": 10,
    },
    {
        "key": "categories",
        "label": "分类",
        "name": "name",
        "id": None,
        "extra": [],
        "max": 10,
    },
    {
        "key": "records",
        "label": "记录",
        "name": None,
        "id": "id",
        "extra": [],
        "max": 5,
    },
    {
        "key": "entries",
        "label": "明细",
        "name": "operation_type",
        "id": "work_order_id",
        "extra": ["payable_amount", "settlement_status"],
        "max": 5,
    },
    {
        "key": "templates",
        "label": "模板",
        "name": "name",
        "id": "id",
        "extra": [],
        "max": 10,
    },
    {
        "key": "fields",
        "label": "地块",
        "name": "name",
        "id": "id",
        "extra": [],
        "max": 10,
    },
]


def _format_list_summary(tool_name: str, rule: dict[str, Any], items: list[Any]) -> str:
    """按规则格式化列表型结果摘要。"""
    max_items = rule.get("max", 10)
    name_field = rule.get("name")
    id_field = rule.get("id")
    extra_fields = rule.get("extra", [])
    label = rule["label"]

    parts: list[str] = []
    for item in items[:max_items]:
        if not isinstance(item, dict):
            continue
        part = ""
        if name_field and name_field in item:
            part = str(item[name_field])
        if id_field and id_field in item:
            part = f"{part}({item[id_field]})" if part else f"#{item[id_field]}"
        for ef in extra_fields:
            if ef in item and item[ef] is not None:
                part += f",{item[ef]}"
        if part:
            parts.append(part)

    return f"{tool_name}→{len(items)}{label}:{','.join(parts)}"


def _format_generic_summary(tool_name: str, result: dict[str, Any]) -> str:
    """通用 fallback：输出 key=value，保留写操作返回的关键 ID 和状态。"""
    parts: list[str] = []
    for k, v in result.items():
        if isinstance(v, (str, int, float, bool)):
            parts.append(f"{k}={v}")
        elif isinstance(v, list):
            parts.append(f"{k}={len(v)}项")
        elif isinstance(v, dict):
            parts.append(f"{k}=...")
        elif v is None:
            continue
        if len(parts) >= 8:
            break
    return f"{tool_name}→{','.join(parts)}" if parts else ""


def reset_conversation(conversation_id: str) -> None:
    """Wipe a conversation's short-term + long-term memory (for /reset)."""
    f = _conv_file(conversation_id)
    if f.exists():
        f.unlink()
    state_file = _state_file(conversation_id)
    state = load_legacy_state(conversation_id)
    if state_file.exists():
        state["summary"] = None
        state["pending_action"] = None
        state["task_state"] = None
        state["reset_generation"] = int(state.get("reset_generation", 0) or 0) + 1
        state["summary_revision"] = int(state.get("summary_revision", 0) or 0) + 1
        state["summary_status"] = "stale"
        state_file.write_text(
            json.dumps(state, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    with _LOCK:
        if not _MEMORY_FILE.exists():
            return
        try:
            all_mem = json.loads(_MEMORY_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return
        if conversation_id in all_mem:
            del all_mem[conversation_id]
            _MEMORY_FILE.write_text(
                json.dumps(all_mem, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
