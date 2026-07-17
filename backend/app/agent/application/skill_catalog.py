"""App 端 Skill 展示目录。"""

from dataclasses import dataclass
from typing import Any

from app.skills import get_skill_manager
from app.skills.metadata import metadata_to_dict
from app.schemas.agent import AppSkillItem


@dataclass(frozen=True)
class SkillDisplay:
    """App 技能展示配置。"""

    title: str
    category: str
    icon: str
    icon_color: str
    summary: str
    details: str
    examples: tuple[str, ...] = ()
    recommended: bool = False


_APP_SKILL_ORDER = [
    "get_farm_status",
    "manage_cost",
    "manage_farm_logs",
    "manage_labor_payment",
    "manage_crop_cycle",
    "weather",
    "manage_user_settings",
]

_DISPLAY_BY_SKILL: dict[str, SkillDisplay] = {
    "get_farm_status": SkillDisplay(
        title="今日简报",
        category="推荐",
        icon="clipboard-list",
        icon_color="blue",
        summary="汇总待办、近期农事、花费和天气。",
        details="获取当前农场综合状态，帮助你快速了解今天要关注的种植进度、农事记录、花费变化和天气风险。",
        examples=("今天农场怎么样", "最近有什么风险", "帮我看下今日待办"),
        recommended=True,
    ),
    "manage_cost": SkillDisplay(
        title="智能账务",
        category="经营",
        icon="receipt-yuan",
        icon_color="green",
        summary="智能记账、查账、成本分析和欠款还款。",
        details="聚合账务经营能力，支持一句话记录支出、收入和赊账，查询账单与欠款，分析收支趋势，并在确认后处理还款或删账。",
        examples=("买化肥花了200元", "本月成本怎么看", "还欠老王农资多少钱"),
        recommended=True,
    ),
    "manage_crop_cycle": SkillDisplay(
        title="批次管理",
        category="生产",
        icon="layout-grid",
        icon_color="purple",
        summary="管理种植茬口、阶段和批次。",
        details="根据作物、季节、面积和地块信息创建种植批次，也能查询茬口列表和详情，调整开始日期、阶段、状态或删除批次。",
        examples=("春茬种西瓜", "我的茬口有哪些", "把玉米茬口改到9月1开始"),
        recommended=True,
    ),
    "weather": SkillDisplay(
        title="天气提醒",
        category="推荐",
        icon="cloud-sun",
        icon_color="amber",
        summary="查看7天天气和农事风险。",
        details="获取未来天气预报和灾害预警，用于安排浇水、打药、采收、覆膜等对天气敏感的农事。",
        examples=("明天适合打药吗", "最近有雨吗", "未来一周天气怎么样"),
        recommended=True,
    ),
    "manage_farm_logs": SkillDisplay(
        title="农事记录",
        category="记录",
        icon="file-pen",
        icon_color="purple",
        summary="记录、查询和管理农事日志。",
        details="把浇水、施肥、打药等日常农活记录到对应茬口里，也能查询最近日志并在确认后修改或删除记录。",
        examples=("今天6号棚浇水了", "最近7天农事日志", "删除8号农事日志"),
        recommended=True,
    ),
    "manage_labor_payment": SkillDisplay(
        title="工资结算",
        category="记录",
        icon="user-round",
        icon_color="orange",
        summary="记录工人工资、欠款和结算。",
        details="聚合人工付款能力，支持查询未付人工、结算或补付工资、保存或更新独立工资记录。",
        examples=("张三今天工资120", "结清李四200元", "看看还有谁工资没付"),
        recommended=True,
    ),
    "manage_user_settings": SkillDisplay(
        title="偏好设置",
        category="设置",
        icon="settings",
        icon_color="gray",
        summary="更新昵称、默认城市和显示偏好。",
        details="管理芽芽使用时需要记住的基础偏好，比如你的显示名称、常用天气城市和默认农场设置。",
        examples=("把默认城市改成苏州", "以后叫我老李", "查看我的偏好设置"),
    ),
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
        description=display.details if display else skill.description().strip(),
        summary=display.summary if display else _short_description(skill.description()),
        details=display.details if display else skill.description().strip(),
        examples=list(display.examples) if display else [],
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
