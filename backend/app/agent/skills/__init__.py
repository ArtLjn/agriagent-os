"""Farm Manager Skill 包 — skillify SDK 驱动。"""

import asyncio
import logging
from typing import Any, Literal

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field, create_model
from skillify.core.context import SkillContext
from skillify.manager import SkillManager

from app.core.database import SessionLocal
from app.services import cost_category_service

logger = logging.getLogger(__name__)

_manager: SkillManager | None = None


def get_skill_manager() -> SkillManager:
    """获取全局 SkillManager 单例。"""
    global _manager
    if _manager is None:
        _manager = SkillManager(python_packages=["app.agent.skills"])
        for skill_def in _manager.list_skills():
            skill = _manager.get_skill(skill_def.name)
            if skill:
                logger.info(
                    "Skill 已加载 | name=%s | desc=%s",
                    skill.name(),
                    skill.description(),
                )
        logger.info(
            "SkillManager 初始化完成，共 %d 个 Skill",
            len(_manager.list_skills()),
        )
    return _manager


def _schema_to_pydantic(
    name: str,
    schema: dict[str, Any],
    *,
    enums: dict[str, list[str]] | None = None,
) -> type[BaseModel]:
    """将 JSON Schema 转为 Pydantic BaseModel。"""
    properties = schema.get("properties", {})
    required = set(schema.get("required", []))
    fields: dict[str, Any] = {}
    type_map = {"string": str, "integer": int, "number": float, "boolean": bool}

    for field_name, field_def in properties.items():
        original_type = type_map.get(field_def.get("type", "string"), str)
        py_type = original_type
        if field_name not in required:
            py_type = py_type | None
        default = field_def.get("default") if field_name not in required else ...
        desc = field_def.get("description", "")

        enum_values = field_def.get("enum")
        if enums and field_name in enums:
            enum_values = enums[field_name]

        if enum_values and original_type is str:
            literal_type = Literal[tuple(enum_values)]
            py_type = literal_type if field_name in required else literal_type | None

        fields[field_name] = (py_type, Field(default=default, description=desc))

    return create_model(f"{name}Schema", **fields)


_DEFAULT_CATEGORY_ENUM = ["化肥", "种子", "农药", "人工", "其他"]
_category_cache: dict[int, list[str]] = {}


def get_category_enum(farm_id: int) -> list[str]:
    """从数据库加载 farm 的分类标签列表，结果缓存。"""
    if farm_id in _category_cache:
        return _category_cache[farm_id]
    try:
        db = SessionLocal()
        try:
            categories = cost_category_service.get_categories(db, farm_id)
            names = [c.name for c in categories]
        finally:
            db.close()
        if not names:
            names = list(_DEFAULT_CATEGORY_ENUM)
        _category_cache[farm_id] = names
        return names
    except Exception:
        logger.warning("分类加载失败，使用默认 enum | farm_id=%d", farm_id)
        default = list(_DEFAULT_CATEGORY_ENUM)
        _category_cache[farm_id] = default
        return default


def clear_category_cache(farm_id: int | None = None) -> None:
    """清除分类缓存。farm_id=None 时清除全部。"""
    if farm_id is None:
        _category_cache.clear()
    else:
        _category_cache.pop(farm_id, None)


def _make_sync_fn(skill):
    """为 StructuredTool 创建同步调用函数。"""

    def fn(**kwargs):
        loop = asyncio.new_event_loop()
        try:
            result = loop.run_until_complete(skill.execute(kwargs, None))
            return result.reply
        finally:
            loop.close()

    return fn


def _make_async_fn(skill):
    """为 StructuredTool 创建异步调用函数。"""

    async def coro(**kwargs):
        result = await skill.execute(kwargs, None)
        return result.reply

    return coro


def skills_to_langchain_tools(
    manager: SkillManager, farm_id: int = 1
) -> list[StructuredTool]:
    """将 skillify Skills 转为 LangChain StructuredTool 列表。"""
    category_enum = get_category_enum(farm_id)
    enums_map = {"category": category_enum} if category_enum else {}

    tools = []
    for skill_def in manager.list_skills():
        skill = manager.get_skill(skill_def.name)
        if not skill:
            continue
        args_schema = _schema_to_pydantic(
            skill.name(), skill.parameters_schema(), enums=enums_map
        )
        tools.append(
            StructuredTool(
                name=skill.name(),
                description=skill.description(),
                args_schema=args_schema,
                func=_make_sync_fn(skill),
                coroutine=_make_async_fn(skill),
            )
        )
    return tools


def get_langchain_tools(farm_id: int = 1) -> list[StructuredTool]:
    """获取 LangChain Tool 列表（供 LangGraph 使用）。"""
    return skills_to_langchain_tools(get_skill_manager(), farm_id=farm_id)


_SKILL_REGISTRY: dict = {}


def get_skill_registry() -> dict:
    """获取全局 Skill 注册表（名称 -> 工具实例）。"""
    global _SKILL_REGISTRY
    if not _SKILL_REGISTRY:
        _SKILL_REGISTRY = _build_registry()
    return _SKILL_REGISTRY


def _build_registry() -> dict:
    """构建 Skill 注册表。"""
    registry = {}
    try:
        manager = get_skill_manager()
        for skill_def in manager.list_skills():
            skill = manager.get_skill(skill_def.name)
            if skill:
                registry[skill.name()] = skill
                logger.debug("Skill 注册 | name=%s", skill.name())
    except Exception as e:
        logger.warning("Skill 加载失败: %s", e)
    return registry


def clear_skill_cache():
    """清除工具缓存（用于热重载）。"""
    global _SKILL_REGISTRY
    _SKILL_REGISTRY = {}


def build_skill_context(farm_id: int) -> SkillContext:
    """构建 skillify SkillContext，优先从 Manager 获取 LLM 配置。"""
    from openai import AsyncOpenAI

    from app.core.config import settings

    api_key = settings.ai_api_key
    base_url = settings.ai_base_url
    model = settings.ai_model

    try:
        from app.core.llm_client_manager import get_llm_manager

        manager = get_llm_manager()
        if not manager.fallback_mode:
            info = manager.get_model_info()
            client = manager.get_async_client()
            api_key = client.api_key
            base_url = client.base_url
            model = info["model"]
    except Exception:
        pass

    client = AsyncOpenAI(api_key=api_key, base_url=base_url)
    return SkillContext(
        user_id=str(farm_id),
        farm_id=farm_id,
        llm_model=model,
        llm_client=client,
    )


__all__ = [
    "get_skill_manager",
    "skills_to_langchain_tools",
    "get_langchain_tools",
    "get_skill_registry",
    "clear_skill_cache",
    "build_skill_context",
    "get_category_enum",
    "clear_category_cache",
]
