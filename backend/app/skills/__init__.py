"""Farm Manager Skill 包 — skillify SDK 驱动。"""

import asyncio
import logging
from typing import Any

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field, create_model
from skillify.manager import SkillManager

logger = logging.getLogger(__name__)

_manager: SkillManager | None = None


def get_skill_manager() -> SkillManager:
    """获取全局 SkillManager 单例。"""
    global _manager
    if _manager is None:
        _manager = SkillManager(python_packages=["app.skills"])
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


def _schema_to_pydantic(name: str, schema: dict[str, Any]) -> type[BaseModel]:
    """将 JSON Schema 转为 Pydantic BaseModel。"""
    properties = schema.get("properties", {})
    required = set(schema.get("required", []))
    fields: dict[str, Any] = {}
    type_map = {"string": str, "integer": int, "number": float, "boolean": bool}

    for field_name, field_def in properties.items():
        py_type = type_map.get(field_def.get("type", "string"), str)
        if field_name not in required:
            py_type = py_type | None
        default = field_def.get("default") if field_name not in required else ...
        desc = field_def.get("description", "")
        fields[field_name] = (py_type, Field(default=default, description=desc))

    return create_model(f"{name}Schema", **fields)


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


def skills_to_langchain_tools(manager: SkillManager) -> list[StructuredTool]:
    """将 skillify Skills 转为 LangChain StructuredTool 列表。"""
    tools = []
    for skill_def in manager.list_skills():
        skill = manager.get_skill(skill_def.name)
        if not skill:
            continue
        args_schema = _schema_to_pydantic(skill.name(), skill.parameters_schema())
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


def get_langchain_tools() -> list[StructuredTool]:
    """获取 LangChain Tool 列表（供 LangGraph 使用）。"""
    return skills_to_langchain_tools(get_skill_manager())


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


__all__ = [
    "get_skill_manager",
    "skills_to_langchain_tools",
    "get_langchain_tools",
    "get_skill_registry",
    "clear_skill_cache",
]
