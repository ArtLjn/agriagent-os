"""账务分类候选归并推断。"""

_CATEGORY_CONSOLIDATION_RULES = (
    (
        ("大棚膜", "地膜", "棚膜", "薄膜", "防虫网", "遮阳网", "滴灌带", "水管"),
        ("农资", "设施耗材", "农用耗材", "耗材", "其他农资", "材料"),
    ),
    (
        ("化肥", "肥料", "复合肥", "有机肥", "尿素"),
        ("化肥", "肥料"),
    ),
    (
        ("种子", "种苗", "瓜苗", "苗盘"),
        ("种子", "种苗"),
    ),
    (
        ("农药", "杀虫剂", "杀菌剂", "除草剂"),
        ("农药",),
    ),
)


def infer_cost_category_from_text(
    categories: list[str],
    text: str,
    *,
    allow_fallback_other: bool,
) -> tuple[str, str] | None:
    """从已有候选分类中推断账务分类，不创建新分类。"""
    normalized = [str(category).strip() for category in categories if category]
    for category in _matched_categories(normalized, text):
        return category, "dynamic_exact_match"
    for category in _consolidated_categories(normalized, text):
        return category, "dynamic_consolidation"
    if allow_fallback_other and "其他" in normalized:
        return "其他", "fallback_other"
    return None


def _matched_categories(categories: list[str], text: str) -> list[str]:
    if not text:
        return []
    candidates = [
        category for category in categories if category and category != "其他"
    ]
    return sorted(
        (category for category in candidates if category in text),
        key=len,
        reverse=True,
    )


def _consolidated_categories(categories: list[str], text: str) -> list[str]:
    if not text:
        return []
    available = {category for category in categories if category and category != "其他"}
    matches: list[str] = []
    for item_terms, category_terms in _CATEGORY_CONSOLIDATION_RULES:
        if not any(term in text for term in item_terms):
            continue
        for category in category_terms:
            if category in available and category not in matches:
                matches.append(category)
    return matches
