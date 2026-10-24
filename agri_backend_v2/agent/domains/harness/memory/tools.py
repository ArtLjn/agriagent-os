"""主 Agent 的受控记忆工具；身份和持久化版本由运行时提供。"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from agent.domains.harness.memory.personalization import (
    MemoryError,
    SettingsPatch,
    public_settings,
    visible_memories,
)
from agent.platforms.llm.structured import structured_completion
from agent.platforms.persistence.mongo import personalization_store as store
from agent.prompts import render_prompt

TOOL_NAME = "manage_personal_memory"
logger = logging.getLogger(__name__)
PREFERENCE_ACKNOWLEDGEMENT = "了解，我会在当前对话中参考你刚才说的偏好。"
# 语义审查偶尔把简短完成式当作礼貌回应；只兜底普通偏好答复开头的明确完成声明。
# 不用于判断用户授权，也不匹配“记住了什么”等查询或引用。
_UNVERIFIED_MEMORY_ACK = re.compile(
    r"^(?:好的[，,。]\s*)?(?:我)?(?:已经|已)?记住了[，,。！!：:]"
)
_AUTHORIZATION_HISTORY_MESSAGES = 6
MAX_COMMAND_EVIDENCE_CHARS = 500
MAX_REPAIR_ATTEMPTS = 1
RECOVERABLE_ERROR_CODES = frozenset(
    {
        "memory_not_found",
        "memory_version_conflict",
        "memory_evidence_required",
        "memory_invalid_arguments",
        "memory_authorization_unavailable",
        "memory_storage_unavailable",
    }
)
OBSERVATION_ONLY_CODE = "memory_observation_only"
OBSERVATION_ONLY_RESULT = {
    "ok": True,
    "persisted": False,
    "retryable": False,
    "status": "not_requested",
    "code": OBSERVATION_ONLY_CODE,
    "message": "本轮偏好交给后台自动学习。停止调用记忆写工具，自然回应；没有实际保存结果时不要声称已保存。",
}


class MemoryAssessment(BaseModel):
    """模型只判断语义与证据，实际权限仍由代码控制。"""

    model_config = ConfigDict(extra="forbid", strict=True)
    authorized: bool = False
    requests_persistence: bool = False
    claims_persistence: bool = False
    preference_statement: bool = False
    claims_memory_failure: bool = False
    content_evidence: str = ""
    confirmation_unambiguous: bool = False


@dataclass(frozen=True)
class MemoryCompletionIssue:
    """区分必须完成的持久化请求与只需纠正措辞的普通偏好，禁止反向制造写授权。"""

    message: str
    can_acknowledge: bool = False


class GroundingCheck(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    supported: bool


def authorization_dialogue(turn) -> list[dict[str, str]]:
    """只从身份隔离且遵守会话重置的原始快照取证，不使用摘要、工具结果或同轮模型补写。"""
    from agent.config import memory_runtime

    snapshot = getattr(turn, "memory_snapshot", {})
    if turn.temporary or snapshot.get("source_status") in {"unavailable", "divergent"}:
        return []
    history = [
        {"role": item["role"], "content": item["content"]}
        for item in (snapshot.get("messages") or [])[-_AUTHORIZATION_HISTORY_MESSAGES:]
        if isinstance(item, dict)
        and item.get("role") in {"user", "assistant"}
        and isinstance(item.get("content"), str)
    ]
    # 不截断否定或限定条件，也不跳过过长的中间消息后拼出虚假的相邻确认关系。
    if sum(len(item["content"]) for item in history) > memory_runtime.context_chars:
        return []
    return history


async def assess(
    user_input: str,
    *,
    command: dict | None = None,
    reply: str = "",
    known_memories: list[dict] | None = None,
    business_operations: list[dict] | None = None,
    recent_dialogue: list[dict] | None = None,
) -> MemoryAssessment:
    """不依赖触发词，区分长期操作意图、临时要求、引用和真实成功声明。"""
    from agent.config import memory_runtime

    return await structured_completion(
        MemoryAssessment,
        temperature=0,
        max_tokens=300,
        timeout=memory_runtime.assessment_timeout,
        messages=[
            {
                "role": "system",
                "content": render_prompt("memory_assess"),
            },
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "user_input": user_input,
                        "command": command,
                        "reply": reply,
                        "known_memories": known_memories or [],
                        "business_operations": business_operations or [],
                        "recent_dialogue": recent_dialogue or [],
                    },
                    ensure_ascii=False,
                ),
            },
        ],
    )


class MemoryCommand(BaseModel):
    model_config = ConfigDict(extra="forbid")
    action: Literal["list", "remember", "update", "forget", "clear", "configure"]
    text: str | None = Field(default=None, min_length=1, max_length=500)
    memory_id: str | None = None
    scope: Literal["user", "user_farm"] = "user"
    preferences: dict | None = None
    query: str | None = Field(
        default=None,
        min_length=1,
        max_length=200,
        description="list 时的主题检索词；省略时使用本轮问题。重复相同查询不会翻页。",
    )
    evidence: str | None = Field(
        default=None,
        min_length=1,
        max_length=MAX_COMMAND_EVIDENCE_CHARS,
        description="逐字引用用户原文；省略时服务端仅使用长度允许的本轮用户原文，仍核验操作意图和范围。",
    )


async def content_is_grounded(
    command: MemoryCommand,
    user_statements: list[str],
    *,
    known_memories: list[dict] | None = None,
) -> bool:
    """独立核对写入差量与删除范围，只信用户原文和当前身份的权威旧事实。"""
    from agent.config import memory_runtime

    checked = await structured_completion(
        GroundingCheck,
        temperature=0,
        max_tokens=100,
        timeout=memory_runtime.assessment_timeout,
        messages=[
            {
                "role": "system",
                "content": render_prompt("memory_grounding"),
            },
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "action": command.action,
                        "memory_id": command.memory_id,
                        "text": command.text,
                        "preferences": command.preferences,
                        "user_statements": user_statements,
                        "known_memories": known_memories or [],
                    },
                    ensure_ascii=False,
                ),
            },
        ],
    )
    return checked.supported


TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": TOOL_NAME,
        "description": "查询或按明确要求管理长期记忆。list 用 query 检索当前主题，返回有界候选而非全库；重复查询不会翻页。普通新增、补充和纠正偏好都由后台自动学习，无需调用本工具或询问确认。用户明确要求立即保存才 remember/update；删除和配置按明确对象执行。memory_id 来自上下文或 list。evidence 引用用户原文；跨轮确认可承接前文。只有 persisted=true 才表示保存成功。",
        "parameters": MemoryCommand.model_json_schema(),
    },
}


async def completion_guard_issue(
    turn, content: str, *, claims_write: bool = False
) -> MemoryCompletionIssue | None:
    """在同一收尾边界核对意图与成功声明，防止分支复用助手草稿作为写授权。"""
    attempted = False
    for message in turn.messages:
        if message.get("role") != "tool" or message.get("name") != TOOL_NAME:
            continue
        try:
            result = json.loads(message.get("content", "{}"))
        except (ValueError, TypeError):
            continue
        if result.get("ok") is True and result.get("persisted") is True:
            return None
        if (
            result.get("code") == OBSERVATION_ONLY_CODE
            and content == PREFERENCE_ACKNOWLEDGEMENT
        ):
            # 已判断为普通观察且使用固定的非持久化答复，不让第二次语义判断重新打开写循环。
            return None
        attempted = attempted or "persisted" in result
    try:
        snapshot = getattr(turn, "memory_snapshot", {})
        known = (
            [{"context": snapshot["personalization"]}]
            if snapshot.get("personalization") and not turn.temporary
            else []
        )
        # 只提供运行时确认的操作类型与编号，不把任意工具返回或备忘录正文当作授权。
        operations = [
            {
                "tool_name": item["tool_name"],
                "description": item["description"],
                "record_id": item["result"].get("id"),
            }
            for item in getattr(turn, "committed_operations", [])
        ]
        assessment = await assess(
            turn.user_input,
            reply=content,
            known_memories=known,
            business_operations=operations,
            recent_dialogue=authorization_dialogue(turn),
        )
        if assessment.requests_persistence:
            # 助手草稿可能声称“已更新”；不能让这句话反向制造用户的长期写入请求。
            # 只有需要促使 Agent 补执行时才独立核对原始意图，普通读取无需额外调用。
            intent = await assess(
                turn.user_input, recent_dialogue=authorization_dialogue(turn)
            )
            assessment.requests_persistence = intent.requests_persistence
            assessment.preference_statement = intent.preference_statement
    except Exception as exc:  # noqa: BLE001 -- 外部语义审查故障必须阻止无证据声明，不能中断业务结果回传。
        logger.warning(
            "memory assessment unavailable code=%s turn_id=%s",
            type(exc).__name__,
            turn.turn_id,
        )
        return MemoryCompletionIssue(
            "记忆语义核验暂不可用，不能确认持久化成功；请如实说明未确认保存结果"
        )
    if (
        assessment.preference_statement
        and not assessment.requests_persistence
        and (
            assessment.claims_persistence
            or assessment.claims_memory_failure
            or _UNVERIFIED_MEMORY_ACK.search(content.strip())
            or claims_write
        )
    ):
        return MemoryCompletionIssue(
            "本轮只是普通偏好陈述，没有授权显式保存。只回应当前偏好，不得调用记忆工具补救、承诺长期保存或沿用历史报错。",
            can_acknowledge=True,
        )
    if assessment.requests_persistence and not attempted and not turn.temporary:
        return MemoryCompletionIssue(
            "用户明确要求长期记忆操作，但没有成功的 manage_personal_memory 持久化结果；请执行已授权的记忆请求，失败则如实说明。"
        )
    if assessment.claims_persistence:
        return MemoryCompletionIssue(
            "没有成功的个人记忆持久化证据，请撤回保存声明。不能因助手声称记住就反向制造用户授权；不要为纠正措辞重复调用写工具。"
        )
    if assessment.claims_memory_failure and not attempted:
        return MemoryCompletionIssue(
            "本轮没有调用记忆写工具，不能声称本轮保存失败或系统异常；历史报错不是本轮工具结果，请按当前请求重新回答。"
        )
    return None


async def execute(turn, arguments: dict | str, call_id: str) -> dict:
    """集中呈现身份、原文、意图、范围、落库的先后约束，便于审计授权先于副作用。"""
    from agent.config import memory_runtime

    try:
        if turn.temporary:
            raise MemoryError(
                "memory_disabled_for_temporary_session", "临时对话不使用或保存记忆", 403
            )
        command = MemoryCommand.model_validate(
            json.loads(arguments) if isinstance(arguments, str) else arguments
        )
        dialogue = authorization_dialogue(turn)
        evidence_sources = [
            *(item["content"] for item in dialogue if item["role"] == "user"),
            turn.user_input,
        ]
        # 工具漏填引用不能使明确删除陷入重试；只补可信输入，不补助手生成内容。
        # 仍经过下方独立意图、对象范围和内容核对；不截断长输入中的否定条件。
        if (
            command.action != "list"
            and command.evidence is None
            and 0 < len(turn.user_input) <= MAX_COMMAND_EVIDENCE_CHARS
        ):
            command.evidence = turn.user_input
        if command.action != "list" and not (
            command.evidence
            and any(command.evidence in text for text in evidence_sources)
        ):
            raise MemoryError(
                "memory_evidence_required", "请引用本轮或近期用户原文", 422
            )
        doc, record = None, None
        known = []
        if command.action in {"update", "forget"}:
            # 旧事实只能由当前身份的权威存储补齐，不信任模型自报的编号或旧正文。
            doc = await store.load(turn.user_id, memory_ids=[command.memory_id])
            record = next(
                (
                    m
                    for m in visible_memories(doc, turn.farm_uid)
                    if m["memory_id"] == command.memory_id
                ),
                None,
            )
            if record is None:
                raise MemoryError(
                    "memory_not_found", "请先查询记忆，使用返回的真实编号", 404
                )
            known = (
                [
                    {
                        k: record[k]
                        for k in ("memory_id", "text", "conditions", "revision")
                    }
                ]
                if record
                else []
            )
        if command.action != "list":
            try:
                assessment = await assess(
                    turn.user_input,
                    command=command.model_dump(),
                    recent_dialogue=dialogue,
                    known_memories=known,
                )
                if (
                    command.action in {"remember", "update"}
                    and assessment.preference_statement
                    and not assessment.requests_persistence
                ):
                    return dict(OBSERVATION_ONLY_RESULT)
                if (
                    assessment.authorized
                    and command.action in {"remember", "update", "forget", "configure"}
                    and not await content_is_grounded(
                        command, evidence_sources, known_memories=known
                    )
                ):
                    assessment.authorized = False
            except Exception as exc:
                logger.warning(
                    "memory authorization unavailable code=%s turn_id=%s",
                    type(exc).__name__,
                    turn.turn_id,
                )
                raise MemoryError(
                    "memory_authorization_unavailable",
                    "暂时无法确认长期记忆操作意图，请稍后重试",
                    503,
                ) from exc
            if assessment.preference_statement and not assessment.requests_persistence:
                # 模型误选显式记忆工具不应把普通交流变成系统故障，也不能借机持久化。
                # 后台学习由用户消息事件及设置控制，与本轮工具是否成功无关。
                return dict(OBSERVATION_ONLY_RESULT)
            if (
                not assessment.authorized
                or (
                    command.evidence not in turn.user_input
                    and not assessment.requests_persistence
                )
                or (
                    command.evidence not in turn.user_input
                    and not (
                        assessment.confirmation_unambiguous
                        and assessment.content_evidence
                        and any(
                            assessment.content_evidence in text
                            for text in evidence_sources
                        )
                    )
                )
            ):
                raise MemoryError(
                    "memory_explicit_intent_required",
                    "该操作未获得本轮用户的明确长期授权；普通偏好由自动学习处理",
                    422,
                )
        if command.action == "list":
            from agent.domains.harness.memory.long_term import load_context_candidates

            try:
                # 补查与主动注入必须使用相同候选源，不能因词项窗口遗漏而否定语义命中。
                doc = await load_context_candidates(
                    turn.user_id, turn.farm_uid, command.query or turn.user_input
                )
            except TimeoutError as exc:
                raise MemoryError(
                    "memory_retrieve_timeout",
                    "记忆检索超时，不能据此认定没有相关记忆",
                    503,
                ) from exc
            return {
                "ok": True,
                "memory_revision": doc["revision"],
                "settings": public_settings(doc),
                "query": command.query or turn.user_input,
                "coverage": "仅本次匹配候选，不是全库。相同 query 重复调用不会取得下一页；无相关依据就说明本次未找到，不猜测。",
                "memories": [
                    {
                        k: m[k]
                        for k in (
                            "memory_id",
                            "revision",
                            "text",
                            "conditions",
                            "source_type",
                            "category",
                        )
                        if k in m
                    }
                    for m in visible_memories(doc, turn.farm_uid)[
                        : memory_runtime.context_selection_limit
                    ]
                ]
                if doc["settings"]["use_saved_memories"]
                else [],
            }
        doc = doc if doc is not None else await store.load(turn.user_id, memory_ids=[])
        if command.action == "configure":
            patch = SettingsPatch.model_validate(
                {**(command.preferences or {}), "expected_revision": doc["revision"]}
            )
            result = public_settings(await store.update_settings(turn.user_id, patch))
        elif command.action == "clear":
            result = await store.clear_memories(turn.user_id, turn.farm_uid)
        elif command.action in {"remember", "update"}:
            from agent.domains.harness.memory.learning import remember_explicit

            result = await remember_explicit(
                turn,
                command.text or "",
                record["scope"] if record else command.scope,
                target=record,
            )
        else:
            result = await store.modify_memory(
                turn.user_id,
                turn.farm_uid,
                record["memory_id"],
                None,
                expected_revision=record["revision"],
            )
        return {
            "ok": True,
            "persisted": True,
            "result": result,
            "memory_revision": (await store.load(turn.user_id, memory_ids=[]))[
                "revision"
            ],
        }
    except (MemoryError, ValidationError, ValueError) as exc:
        code = getattr(exc, "code", "memory_invalid_arguments")
        return {
            "ok": False,
            "persisted": False,
            "code": code,
            "retryable": code in RECOVERABLE_ERROR_CODES,
            "message": str(exc)
            if isinstance(exc, MemoryError)
            else "记忆参数不符合约束",
        }


def discard_stale_results(messages: list[dict], revision: int | None) -> None:
    """控制状态变化后抹除旧工具快照，避免删除后又从同轮上下文取回。"""
    for message in messages:
        if message.get("role") != "tool" or message.get("name") != TOOL_NAME:
            continue
        try:
            result = json.loads(message.get("content", "{}"))
        except (ValueError, TypeError):
            continue
        # 拒绝/参数错误不含记忆快照；保留真实错误，不能伪装成版本失效。
        if "memory_revision" in result and result.get("memory_revision") != revision:
            message["content"] = json.dumps(
                {
                    "ok": result.get("ok", False),
                    "persisted": result.get("persisted", False),
                    "message": "此记忆快照已失效，不得继续引用其中的偏好；需要时重新查询。",
                },
                ensure_ascii=False,
            )
