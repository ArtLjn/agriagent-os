"""RuleIntentClassifier 使用的无状态规则信号判断。"""

import re

from app.agent.router import classifier_extractors as extractors
from app.agent.router import classifier_hints as hints


def has_any(message: str, hint_values: tuple[str, ...]) -> bool:
    return any(hint in message for hint in hint_values)


def looks_like_active_crop_query(message: str) -> bool:
    return has_any(message, hints.QUERY_HINTS) and has_any(message, hints.CROP_HINTS)


def looks_like_farm_read(message: str) -> bool:
    return has_any(message, hints.QUERY_HINTS) and has_any(message, hints.FARM_HINTS)


def looks_like_planting_advice(message: str) -> bool:
    return "种" in message and has_any(message, hints.PLANTING_ADVICE_HINTS)


def looks_like_web_search(message: str) -> bool:
    return has_any(message, hints.WEB_SEARCH_HINTS)


def looks_like_weather_query(message: str) -> bool:
    return has_any(message, hints.WEATHER_HINTS)


def looks_like_weather_crop_impact_query(message: str) -> bool:
    return (
        looks_like_weather_query(message)
        and has_any(message, hints.CROP_HINTS)
        and has_any(message, ("影响", "适合", "建议", "要不要"))
    )


def looks_like_daily_operation_advice(message: str) -> bool:
    has_time = has_any(message, hints.DAILY_ADVICE_TIME_HINTS)
    has_advice_action = has_any(message, hints.DAILY_ADVICE_ACTION_HINTS)
    has_weather_sensitive_operation = has_any(
        message,
        hints.WEATHER_SENSITIVE_OPERATION_HINTS,
    )
    if has_time and has_advice_action:
        return True
    return has_time and "适合" in message and has_weather_sensitive_operation


def looks_like_create_worker(message: str) -> bool:
    if "工人" not in message:
        return False
    has_create_action = has_any(message, hints.WORKER_CREATE_HINTS)
    has_pay_hint = has_any(message, hints.WORKER_PAY_HINTS)
    return has_create_action or has_pay_hint


def looks_like_manage_worker(message: str) -> bool:
    return (
        looks_like_update_worker(message)
        or looks_like_deactivate_worker(message)
        or looks_like_restore_worker(message)
    )


def looks_like_manage_cost_category(message: str) -> bool:
    if has_any(message, hints.QUERY_HINTS):
        return False
    if not has_cost_category_target(message):
        return False
    return looks_like_create_action(message) or looks_like_delete_cost_category(message)


def looks_like_manage_planting_unit(message: str) -> bool:
    if looks_like_planting_unit_query(message):
        return False
    if not has_planting_unit_target(message):
        return False
    return (
        looks_like_create_action(message)
        or looks_like_update_planting_unit(message)
        or looks_like_delete_planting_unit(message)
    )


def looks_like_create_crop_template(message: str) -> bool:
    return "模板" in message and looks_like_create_action(message)


def looks_like_create_crop_cycle(message: str) -> bool:
    if has_any(message, hints.READ_BLOCKERS):
        return False
    if looks_like_planting_advice(message):
        return False
    if "茬口" in message and looks_like_create_action(message):
        return True
    return False


def looks_like_delete_crop_cycle(message: str) -> bool:
    if has_any(message, hints.READ_BLOCKERS):
        return False
    return "茬口" in message and has_any(message, ("删除", "删掉", "删"))


def looks_like_create_cost_record(message: str) -> bool:
    if has_any(message, hints.READ_BLOCKERS):
        return False
    if re.search(r"\d+\s*(?:元|块)", message) is None:
        return False
    return has_any(message, hints.COST_RECORD_WRITE_HINTS) and has_any(
        message,
        hints.COST_RECORD_ENTITIES,
    )


def looks_like_query_work_orders(message: str) -> bool:
    return has_any(message, hints.READ_BLOCKERS) and has_any(
        message,
        hints.WORK_ORDER_READ_HINTS,
    )


def looks_like_create_work_order(message: str) -> bool:
    if looks_like_manage_wage(message):
        return False
    if has_any(message, hints.READ_BLOCKERS):
        return False
    return (
        looks_like_farm_labor_work(message)
        or has_any(message, hints.WORK_ORDER_HINTS)
        or (extractors.extract_operation_type(message) is not None)
    )


def looks_like_cost_summary_query(message: str) -> bool:
    if looks_like_cost_category_query(message):
        return False
    if looks_like_manage_cost_category(message):
        return False
    return has_any(message, hints.COST_SUMMARY_HINTS)


def looks_like_finance_overview_query(message: str) -> bool:
    normalized = message.strip().lower()
    return normalized in hints.FINANCE_OVERVIEW_HINTS


def looks_like_debt_summary_query(message: str) -> bool:
    if looks_like_labor_payable_query(message):
        return False
    return has_any(message, hints.DEBT_SUMMARY_HINTS)


def looks_like_cost_analytics_query(message: str) -> bool:
    return has_any(message, hints.COST_ANALYTICS_HINTS)


def looks_like_delete_cost_record(message: str) -> bool:
    return has_any(message, hints.DELETE_COST_HINTS)


def looks_like_settle_debt(message: str) -> bool:
    if looks_like_debt_summary_query(message):
        return False
    return has_any(message, hints.SETTLE_DEBT_HINTS)


def looks_like_labor_payable_query(message: str) -> bool:
    if looks_like_create_worker(message):
        return False
    if looks_like_farm_labor_work(message):
        return False
    if looks_like_settle_labor_payment(message):
        return False
    if looks_like_manage_wage(message):
        return False
    return has_any(message, hints.LABOR_PAYABLE_HINTS)


def looks_like_settle_labor_payment(message: str) -> bool:
    has_labor = has_any(message, ("人工", "工钱", "工资"))
    return has_labor and has_any(message, hints.LABOR_SETTLE_HINTS)


def looks_like_manage_wage(message: str) -> bool:
    if not has_any(message, ("工资", "工钱", "人工费")):
        return False
    if looks_like_settle_labor_payment(message):
        return False
    has_record_action = has_any(message, hints.WAGE_RECORD_HINTS)
    has_wage_detail = (
        extractors.extract_operation_type(message) is not None
        and extractors.extract_worker_name(message) is not None
        and extractors.extract_unit_price(message) is not None
    )
    has_work_order_target = extractors.extract_unit_name(message) is not None or has_any(
        message,
        ("去", "到", "安排", "让", "叫", "派"),
    )
    return has_record_action or (has_wage_detail and not has_work_order_target)


def looks_like_farm_labor_work(message: str) -> bool:
    has_operation = extractors.extract_operation_type(message) is not None
    has_worker = extractors.extract_worker_name(message) is not None
    has_labor_hint = bool(
        re.search(r"\d+\s*天", message)
        or extractors.extract_unit_price(message) is not None
        or has_any(message, ("干了", "去", "到", "安排"))
    )
    return has_operation and has_worker and has_labor_hint


def looks_like_incomplete_farm_labor_work(message: str) -> bool:
    if extractors.extract_operation_type(message) is not None:
        return False
    has_worker = extractors.extract_worker_name(message) is not None
    has_quantity = extractors.extract_labor_quantity(message) is not None
    has_labor_verb = has_any(message, ("干了", "做了", "上了"))
    return has_worker and has_quantity and has_labor_verb


def looks_like_cost_category_query(message: str) -> bool:
    if looks_like_manage_cost_category(message):
        return False
    return has_any(message, hints.COST_CATEGORY_HINTS) or (
        "分类" in message and has_any(message, hints.QUERY_HINTS)
    )


def looks_like_crop_template_query(message: str) -> bool:
    if looks_like_create_crop_template(message):
        return False
    return has_any(message, hints.CROP_TEMPLATE_HINTS)


def looks_like_crop_cycle_list_query(message: str) -> bool:
    return has_any(message, hints.CROP_CYCLE_LIST_HINTS)


def looks_like_crop_cycle_detail_query(message: str) -> bool:
    if looks_like_create_crop_cycle(message):
        return False
    return bool(
        re.search(
            r"(?:看一下|查询|查一下|看看).{0,8}(?:\d+\s*号)?茬口"
            r"|(?:茬口|周期|cycle)\s*\d+"
            r"|\d+\s*(?:号|#)?\s*(?:茬口|周期)",
            message,
        )
    )


def looks_like_planting_unit_query(message: str) -> bool:
    return has_any(message, hints.PLANTING_UNIT_HINTS) and has_any(
        message,
        hints.QUERY_HINTS,
    )


def looks_like_user_settings_query(message: str) -> bool:
    return has_any(
        message,
        hints.USER_SETTINGS_HINTS,
    ) and not looks_like_update_user_settings(message)


def looks_like_update_user_settings(message: str) -> bool:
    if has_any(message, hints.USER_SETTINGS_READ_HINTS):
        return False
    return has_any(message, hints.USER_SETTINGS_HINTS) and any(
        re.search(pattern, message)
        for pattern in hints.USER_SETTINGS_UPDATE_PATTERNS
    )


def looks_like_worker_query(message: str) -> bool:
    if looks_like_create_worker(message):
        return False
    return has_any(message, hints.WORKER_QUERY_HINTS)


def looks_like_ambiguous_write(message: str) -> bool:
    if looks_like_manage_worker(message):
        return False
    if looks_like_manage_cost_category(message):
        return False
    if looks_like_manage_planting_unit(message):
        return False
    return has_any(message, hints.WRITE_ACTION_HINTS) and has_any(
        message,
        hints.WRITE_ENTITY_HINTS,
    )


def looks_like_update_worker(message: str) -> bool:
    has_update_action = has_any(message, hints.WORKER_UPDATE_HINTS)
    if not has_update_action:
        return False
    has_update_field = has_any(message, hints.WORKER_UPDATE_FIELDS)
    return has_worker_target(message) and has_update_field


def looks_like_deactivate_worker(message: str) -> bool:
    has_deactivate_action = has_any(message, hints.WORKER_DEACTIVATE_HINTS)
    return has_deactivate_action and has_worker_target(message)


def looks_like_restore_worker(message: str) -> bool:
    has_restore_action = has_any(message, hints.WORKER_RESTORE_HINTS)
    return has_restore_action and has_worker_target(message)


def has_worker_target(message: str) -> bool:
    return extractors.extract_worker_name(message) is not None


def looks_like_delete_cost_category(message: str) -> bool:
    has_delete_action = has_any(message, hints.COST_CATEGORY_DELETE_HINTS)
    return has_delete_action and has_explicit_cost_category_scope(message)


def has_cost_category_target(message: str) -> bool:
    return has_any(message, hints.COST_CATEGORY_ENTITY_HINTS)


def has_explicit_cost_category_scope(message: str) -> bool:
    return has_any(message, hints.COST_CATEGORY_SCOPE_HINTS) or bool(
        re.search(r"(?:分类|category)\s*#?\s*\d+", message, flags=re.IGNORECASE)
    )


def cost_category_action(message: str) -> str:
    if looks_like_delete_cost_category(message):
        return "delete"
    return "create"


def looks_like_update_planting_unit(message: str) -> bool:
    has_update_action = has_any(message, hints.PLANTING_UNIT_UPDATE_HINTS)
    return has_update_action and has_planting_unit_target(message)


def looks_like_delete_planting_unit(message: str) -> bool:
    has_delete_action = has_any(message, hints.PLANTING_UNIT_DELETE_HINTS)
    return has_delete_action and has_planting_unit_target(message)


def has_planting_unit_target(message: str) -> bool:
    if has_any(message, hints.AMBIGUOUS_PLANTING_UNIT_TARGETS):
        return False
    return bool(
        re.search(
            r"[一二三四五六七八九十\d]+\s*号棚"
            r"|[A-Za-z]\s*区"
            r"|(?:地块|大棚|棚区|种植单元)\s*[\u4e00-\u9fa5A-Za-z0-9]{1,8}",
            message,
        )
    )


def planting_unit_action(message: str) -> str:
    if looks_like_delete_planting_unit(message):
        return "delete"
    if looks_like_update_planting_unit(message):
        return "update"
    return "create"


def looks_like_create_action(message: str) -> bool:
    return bool(re.search(r"创建|新增|新建|建(?:个|一个)?|添加", message))


def worker_management_action(message: str) -> str:
    if looks_like_deactivate_worker(message):
        return "deactivate"
    if looks_like_restore_worker(message):
        return "restore"
    return "update"
