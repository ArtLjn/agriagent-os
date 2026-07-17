"""Admin 配置应用用例。"""

from pathlib import Path

from app.prompt.registry import get_registry


def list_prompt_templates() -> dict:
    """列出 Prompt 模板。"""
    registry = get_registry()
    items = []
    for name in registry.list_names():
        content = registry.get(name)
        versions = registry.list_versions(name)
        items.append(
            {
                "name": name,
                "version": versions[0] if versions else "unknown",
                "active": True,
                "content_length": len(content),
                "content": content,
            }
        )
    return {"items": items, "total": len(items)}


def reload_prompt_templates(prompts_dir: Path) -> dict:
    """重载 Prompt 模板。"""
    get_registry().reload(prompts_dir)
    return {"status": "ok", "message": "模板已重新加载"}
