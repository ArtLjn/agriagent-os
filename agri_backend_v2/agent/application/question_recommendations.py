"""首页问题推荐：仅使用生效画像生成建议，不执行工具或写入用户记忆。"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import time
import unicodedata
from collections import OrderedDict
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from agent.domains.harness.memory.personalization import (
    SENSITIVE_PATTERN,
    MemoryError,
    visible_memories,
)
from agent.domains.harness.tools.registry import SkillRegistry
from agent.platforms.logging import get_logger, log_event
from agent.platforms.persistence.mongo import personalization_store as store
from agent.prompts import render_prompt
from shared.time import beijing_today

# 推荐是独立的轻量读请求，预算与缓存只影响推荐，不影响主对话。
QUESTION_LIMIT = 6
QUESTION_LENGTH = 100
EXCLUDE_LIMIT = 18
MEMORY_LIMIT = 8
CONTEXT_CHAR_LIMIT = 4000
CACHE_SECONDS = 300
CACHE_ENTRIES = 128
REQUEST_TIMEOUT = 20
MODEL_MAX_TOKENS = 1600
MODEL_TEMPERATURE = 0.7
MODEL_CONCURRENCY = 4
logger = get_logger(__name__)
_cache: OrderedDict[str, tuple[float, dict]] = OrderedDict()
_generation_slots = asyncio.Semaphore(MODEL_CONCURRENCY)


class RecommendationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, str_strip_whitespace=True)
    exclude: list[Annotated[str, Field(min_length=1, max_length=QUESTION_LENGTH)]] = (
        Field(default_factory=list, max_length=EXCLUDE_LIMIT)
    )


class SuggestedQuestion(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, str_strip_whitespace=True)
    question: str = Field(min_length=4, max_length=QUESTION_LENGTH)
    skill_name: str = Field(min_length=1, max_length=100)
    memory_ids: list[str] = Field(default_factory=list, max_length=MEMORY_LIMIT)


class GeneratedQuestions(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    items: list[SuggestedQuestion] = Field(min_length=1, max_length=QUESTION_LIMIT)


class RecommendationItem(BaseModel):
    id: str
    question: str
    basis: Literal["memory", "explore"]


class RecommendationResponse(BaseModel):
    items: list[RecommendationItem]
    mode: Literal["personalized", "explore"]


def profile_context(document: dict, farm_uid: str) -> dict:
    """画像沿用记忆开关和可信农场过滤，候选、删除、过期及秘密内容不得推荐。"""
    records = (
        visible_memories(document, farm_uid)
        if document["settings"]["use_saved_memories"]
        else []
    )
    records = sorted(
        (record for record in records if record["status"] == "active"),
        key=lambda record: (
            record.get("source_type") == "explicit",
            record.get("updated_at", ""),
        ),
        reverse=True,
    )
    selected, size = [], 0
    for record in records:
        item = {key: record[key] for key in ("memory_id", "text", "conditions")}
        serialized = json.dumps(item, ensure_ascii=False)
        if SENSITIVE_PATTERN.search(serialized):
            continue
        if size + len(serialized) > CONTEXT_CHAR_LIMIT:
            continue
        selected.append(item)
        size += len(serialized)
        if len(selected) == MEMORY_LIMIT:
            break
    return {
        "date": str(beijing_today()),
        "memories": selected,
        "reply_style": document["settings"]["reply_style"],
    }


@lru_cache(maxsize=1)
def read_capabilities() -> list[dict]:
    """从实际技能目录提取只读能力，推荐不能虚构新增工具或预填业务写操作。"""
    registry = SkillRegistry.from_directory(
        Path(__file__).resolve().parents[1] / "tools"
    )
    return [
        {"name": skill.name, "description": skill.description}
        for skill in registry.exposed()
        if skill.risk_level == "read"
    ]


def normalized_question(value: str) -> str:
    """忽略空白、大小写与标点差异，避免换一批只是改变问号。"""
    return "".join(
        char
        for char in unicodedata.normalize("NFKC", value).casefold()
        if not char.isspace() and not unicodedata.category(char).startswith("P")
    )


def validated_result(
    generated: GeneratedQuestions, context: dict, exclude: list[str]
) -> dict:
    """只接受现有能力与已提供的记忆引用，返回界面标签而不泄露原始画像。"""
    allowed = {item["name"] for item in context["capabilities"]}
    memories = {item["memory_id"] for item in context["profile"]["memories"]}
    seen = {normalized_question(question) for question in exclude}
    items = []
    for item in generated.items:
        normalized = normalized_question(item.question)
        if (
            not normalized
            or normalized in seen
            or item.skill_name not in allowed
            or not set(item.memory_ids) <= memories
            or SENSITIVE_PATTERN.search(item.question)
        ):
            continue
        seen.add(normalized)
        items.append(
            {
                "id": hashlib.sha256(item.question.encode()).hexdigest()[:16],
                "question": item.question,
                "basis": "memory" if item.memory_ids else "explore",
            }
        )
    if not items:
        raise MemoryError("recommendations_empty", "暂未生成新的问题，请稍后重试", 503)
    return {
        "items": items,
        "mode": "personalized"
        if any(item["basis"] == "memory" for item in items)
        else "explore",
    }


async def generate(context: dict, instruction: str) -> GeneratedQuestions:
    """复用已配置的模型提供方；不传 tools，推荐生成不会触发业务动作。"""
    from agent.platforms.llm.client import MODEL, _async_client

    response = await _async_client.chat.completions.create(
        model=MODEL,
        temperature=MODEL_TEMPERATURE,
        max_tokens=MODEL_MAX_TOKENS,
        timeout=REQUEST_TIMEOUT,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": instruction},
            {"role": "user", "content": json.dumps(context, ensure_ascii=False)},
        ],
    )
    return GeneratedQuestions.model_validate_json(
        response.choices[0].message.content or ""
    )


async def recommend(user: dict, request: RecommendationRequest) -> dict:
    """每次读取最新画像；生成期间的删除、禁用和版本变更会阻止旧结果返回。"""
    try:
        async with asyncio.timeout(REQUEST_TIMEOUT):
            document = await store.load(user["user_id"])
            profile = profile_context(document, user["farm_uid"])
            instruction = render_prompt("question_recommendations")
            context = {
                "profile": profile,
                "capabilities": read_capabilities(),
                "exclude": request.exclude,
                "count": QUESTION_LIMIT,
            }
            # 包括签发域、可信用户/农场、画像版本、日期及提示词，不能共享用户推荐缓存。
            key = hashlib.sha256(
                json.dumps(
                    [
                        store.owner_key(user["user_id"]),
                        user["farm_uid"],
                        document["revision"],
                        context,
                        instruction,
                    ],
                    ensure_ascii=False,
                    sort_keys=True,
                ).encode()
            ).hexdigest()
            async with _generation_slots:
                cached = _cache.get(key)
                cache_hit = cached is not None and cached[0] > time.monotonic()
                if cache_hit:
                    _cache.move_to_end(key)
                    result = cached[1]
                else:
                    result = validated_result(
                        await generate(context, instruction), context, request.exclude
                    )
                # 等待生成槽或模型期间可能关闭记忆；缓存命中也必须复核。
                current = await store.load(user["user_id"])
                if (
                    current["revision"] != document["revision"]
                    or profile_context(current, user["farm_uid"]) != profile
                ):
                    raise MemoryError(
                        "recommendations_context_changed",
                        "偏好已更新，请重新获取推荐",
                        409,
                    )
                if not cache_hit:
                    _cache[key] = (time.monotonic() + CACHE_SECONDS, result)
                _cache.move_to_end(key)
                while len(_cache) > CACHE_ENTRIES:
                    _cache.popitem(last=False)
                return result
    except MemoryError:
        raise
    except Exception as exc:
        # 只记录错误类型，避免把模型响应、画像或提供方凭据写入普通日志。
        log_event(
            logger,
            logging.WARNING,
            "question_recommendations_failed",
            code=type(exc).__name__,
        )
        raise MemoryError(
            "recommendations_unavailable", "推荐暂时不可用，你仍可直接输入问题", 503
        ) from exc
