"""App 端 Skill 展示目录。"""

from dataclasses import dataclass
from typing import Any

from app.agent.skills import get_skill_manager
from app.agent.skills.metadata import metadata_to_dict
from app.schemas.agent import AppSkillItem


@dataclass(frozen=True)
class SkillDisplay:
    """App 技能展示配置。"""

    title: str
    category: str
    icon: str
    icon_color: str
    recommended: bool = False


_APP_SKILL_ORDER = [
    "get_farm_status",
    "create_cost_record",
    "log_farm_activity",
    "manage_wages",
    "create_crop_cycle",
    "get_cost_analytics",
    "get_weather_forecast",
    "manage_user_settings",
]

_DISPLAY_BY_SKILL: dict[str, SkillDisplay] = {
    "get_farm_status": SkillDisplay("今日简报", "推荐", "clipboard-list", "blue", True),
    "create_cost_record": SkillDisplay(
        "智能记账", "记录", "receipt-yuan", "green", True
    ),
    "log_farm_activity": SkillDisplay("农事记录", "记录", "file-pen", "purple", True),
    "manage_wages": SkillDisplay("工资结算", "记录", "user-round", "orange", True),
    "create_crop_cycle": SkillDisplay(
        "批次管理", "生产", "layout-grid", "purple", True
    ),
    "get_cost_analytics": SkillDisplay("成本分析", "经营", "pie-chart", "blue", True),
    "get_weather_forecast": SkillDisplay(
        "天气提醒", "推荐", "cloud-sun", "amber", True
    ),
    "manage_user_settings": SkillDisplay("偏好设置", "设置", "settings", "gray"),
}

_CATEGORY_BY_TAG = {
    "cost": "经营",
    "debt": "经营",
    "analytics": "经营",
    "summary": "经营",
    "labor": "记录",
    "wage": "记录",
    "farm_logs": "记录",
    "operation_work_order": "生产",
    "crop_cycle": "生产",
    "crop_template": "生产",
    "weather": "推荐",
    "user_settings": "设置",
}

_ICON_BY_CATEGORY = {
    "推荐": ("sparkles", "blue"),
    "记录": ("file-pen", "purple"),
    "经营": ("chart-column", "green"),
    "生产": ("sprout", "teal"),
    "设置": ("settings", "gray"),
}


def list_app_skills() -> list[AppSkillItem]:
    """列出 App 可展示的一级能力卡片。

    这里返回的是产品入口，不是 Agent 内部工具清单。内部读写工具可能服务于
    同一个 App 能力，不能直接暴露给移动端技能页。
    """
    manager = get_skill_manager()
    items: list[AppSkillItem] = []
    for skill_name in _APP_SKILL_ORDER:
        skill = manager.get_skill(skill_name)
        if not skill:
            continue
        metadata = metadata_to_dict(skill)
        if not metadata.get("enabled", True):
            continue
        items.append(_build_app_skill_item(skill, metadata))
    return sorted(items, key=_sort_key)


def _build_app_skill_item(skill: Any, metadata: dict[str, Any]) -> AppSkillItem:
    name = skill.name()
    display = _DISPLAY_BY_SKILL.get(name)
    category = display.category if display else _infer_category(metadata)
    icon, icon_color = _infer_icon(category)
    return AppSkillItem(
        key=name,
        title=display.title if display else _fallback_title(name),
        description=_short_description(skill.description()),
        category=category,
        icon=display.icon if display else icon,
        icon_color=display.icon_color if display else icon_color,
        recommended=display.recommended if display else False,
        enabled=True,
    )


def _infer_category(metadata: dict[str, Any]) -> str:
    for tag in metadata.get("evaluation_tags", []):
        category = _CATEGORY_BY_TAG.get(str(tag))
        if category:
            return category
    return "推荐"


def _infer_icon(category: str) -> tuple[str, str]:
    return _ICON_BY_CATEGORY.get(category, ("sparkles", "blue"))


def _fallback_title(name: str) -> str:
    return name.replace("_", " ").title()


def _short_description(description: str) -> str:
    text = description.strip()
    if len(text) <= 36:
        return text
    return f"{text[:35]}..."


def _sort_key(item: AppSkillItem) -> tuple[int, int, str]:
    category_rank = {"推荐": 0, "记录": 1, "经营": 2, "生产": 3, "设置": 4}
    return (
        category_rank.get(item.category, 9),
        0 if item.recommended else 1,
        item.title,
    )


__all__ = ["list_app_skills"]
