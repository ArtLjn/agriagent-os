"""RuleIntentClassifier 使用的无状态参数抽取辅助。"""

import re

from app.agent.router import classifier_hints as hints

_WAGE_OPERATION_TYPES = ("打药", "浇水", "施肥", "除草", "翻地")
_NON_WORKER_NAMES = {
    "工人",
    "员工",
    "师傅",
    "今天",
    "昨天",
    "前天",
    "早上",
    "上午",
    "中午",
    "下午",
    "晚上",
}


def extract_labor_payment_params(message: str) -> dict:
    params = {"operation": "settle_payment"}
    worker = extract_worker_name(message)
    amount = extract_money_amount(message)
    if worker:
        params["worker"] = worker
    if amount is not None:
        params["amount"] = amount
    return params


def extract_wage_params(message: str) -> dict:
    params: dict = {"operation": "manage_wage", "action": "save"}
    worker = extract_worker_name(message)
    operation_type = extract_wage_operation_type(message)
    quantity = extract_labor_quantity(message)
    unit_price = extract_unit_price(message)
    if worker:
        params["worker_name"] = worker
    if operation_type:
        params["operation_type"] = operation_type
    if quantity is not None:
        params["quantity"] = quantity
        params["pay_type"] = "daily"
    if unit_price is not None:
        params["unit_price"] = unit_price
    return params


def extract_incomplete_farm_labor_evidence(message: str) -> dict:
    return build_farm_labor_evidence(
        worker=extract_worker_name(message),
        operation_type=None,
        quantity=extract_labor_quantity(message),
        unit_price=None,
    )


def extract_worker_params(message: str) -> dict:
    params: dict = {"default_pay_type": "daily"}
    name = extract_worker_name(message)
    price = extract_unit_price(message)
    if name:
        params["name"] = name
    if price is not None:
        params["default_unit_price"] = price
    return params


def extract_worker_management_params(message: str, action: str) -> dict:
    params: dict = {"action": action}
    name = extract_worker_name(message)
    phone = extract_phone(message)
    price = extract_unit_price(message)
    if name:
        params["name"] = name
    if phone:
        params["phone"] = phone
    if price is not None:
        params["default_unit_price"] = price
        params.setdefault("default_pay_type", "daily")
    return params


def extract_work_order_params(message: str) -> dict:
    params: dict = {}
    name = extract_worker_name(message)
    unit_name = extract_unit_name(message)
    unit_price = extract_unit_price(message)
    operation_type = extract_operation_type(message)
    quantity = extract_work_order_quantity(message)
    if name:
        params["workers"] = [name]
    if unit_name:
        params["unit_names"] = [unit_name]
    if operation_type:
        params["operation_type"] = operation_type
    if quantity is not None:
        params["quantity"] = quantity
        params["pay_type"] = "daily"
    if unit_price is not None:
        params["unit_price"] = unit_price
    return params


def extract_planting_unit_params(message: str, action: str) -> dict:
    params: dict = {"operation": "manage_units", "action": action}
    area_mu = extract_area_mu(message)
    unit_names = extract_ordered_unit_names(message)
    crop_name = extract_bound_crop_name(message)
    if area_mu is not None:
        params["area_mu"] = area_mu
    if len(unit_names) == 1:
        params["name"] = unit_names[0]
    elif len(unit_names) > 1:
        params["unit_names"] = unit_names
    if crop_name:
        params["crop_name"] = crop_name
    if "这个茬口" in message or "该茬口" in message:
        params["cycle_ref"] = "current"
    return params


def extract_area_mu(message: str) -> int | float | None:
    match = re.search(r"(?P<area>\d+(?:\.\d+)?)\s*亩", message)
    if not match:
        return None
    value = float(match.group("area"))
    return int(value) if value.is_integer() else value


def extract_ordered_unit_names(message: str) -> list[str]:
    names = [
        item.replace(" ", "")
        for item in re.findall(
            r"[一二三四五六七八九十\d]+\s*号(?:棚|地块|地)?", message
        )
    ]
    return _merge_unique_names(names)


def extract_bound_crop_name(message: str) -> str | None:
    patterns = (
        r"绑定(?P<crop>[\u4e00-\u9fa5A-Za-z0-9]{1,12})茬口",
        r"给(?P<crop>[\u4e00-\u9fa5A-Za-z0-9]{1,12})茬口",
    )
    for pattern in patterns:
        match = re.search(pattern, message)
        if not match:
            continue
        crop = match.group("crop").strip()
        if crop not in {"这个", "该", "当前"}:
            return crop
    return None


def _merge_unique_names(names: list[str]) -> list[str]:
    merged: list[str] = []
    seen: set[str] = set()
    for name in names:
        if name in seen:
            continue
        merged.append(name)
        seen.add(name)
    return merged


def extract_work_order_evidence(message: str) -> dict:
    return build_farm_labor_evidence(
        worker=extract_worker_name(message),
        operation_type=extract_operation_type(message),
        quantity=extract_work_order_quantity(message),
        unit_price=extract_unit_price(message),
    )


def build_farm_labor_evidence(
    *,
    worker: str | None,
    operation_type: str | None,
    quantity: int | None,
    unit_price: int | None,
) -> dict:
    evidence: dict = {"write_risk": "implicit_farm_labor_work"}
    if worker:
        evidence["worker"] = worker
    if operation_type:
        evidence["operation_type"] = operation_type
    if quantity is not None:
        evidence["quantity"] = quantity
        evidence["pay_type"] = "daily"
    if unit_price is not None:
        evidence["unit_price"] = unit_price
    return evidence


def missing_work_order_fields(params: dict) -> list[str]:
    missing: list[str] = []
    if not params.get("operation_type"):
        missing.append("operation_type")
    if params.get("workers") and params.get("unit_price") is None:
        missing.append("unit_price_or_default_wage")
    return missing


def extract_worker_name(message: str) -> str | None:
    name_chars = r"[\u4e00-\u9fa5A-Za-z0-9]{1,8}"
    patterns = (
        r"(?P<name>[\u4e00-\u9fa5]{2,4}?)(?:今天|昨天|前天)?(?:来了|来了一天|上工|出勤)",
        r"(?P<name>[\u4e00-\u9fa5]{2,4}?)(?:今天|昨天|前天)?.{0,8}?(?:打药|浇水|施肥|除草|翻地).{0,8}?(?:\d+\s*(?:元|块)|一?天|\d+\s*天)",
        rf"(?:工人|员工|师傅)(?P<name>{name_chars})(?:工资|日薪|每天)",
        r"(?:把|将)?(?P<name>[\u4e00-\u9fa5]{2,4})的(?:电话|手机号|手机)",
        r"(?:今天|昨天|前天|这个月|本月)?(?P<name>[\u4e00-\u9fa5]{2,4})(?:去|到).{0,16}?(?:采收|授粉|装车|整枝|打杈|压蔓|压瓜|留瓜|垫瓜)",
        r"(?P<name>[\u4e00-\u9fa5]{2,4})(?:这个月|本月).{0,4}?干了\s*\d+\s*天",
        r"(?P<name>[\u4e00-\u9fa5]{2,4})(?:这个月|本月)?.{0,4}?干了\s*\d+\s*天",
        r"(?P<name>[\u4e00-\u9fa5]{2,4})(?:工资|日薪|每天)",
        rf"(?:工人|员工|师傅)(?P<name>{name_chars})",
    )
    for pattern in patterns:
        match = re.search(pattern, message)
        if match:
            name = match.group("name")
            name = re.sub(r"^(?:让|叫|安排)", "", name)
            if name not in _NON_WORKER_NAMES:
                return name
    return None


def extract_unit_price(message: str) -> int | None:
    match = re.search(
        r"(?:工资|日薪|每天|每人|单价)\s*"
        r"(?P<price>\d+)\s*(?:元|块)?\s*(?:一?天|/天|每天)?"
        r"|(?:一?天|每天)\s*(?P<attendance_price>\d+)\s*(?:元|块)?"
        r"|(?P<price_before>\d+)\s*(?:元|块)\s*(?:一?天|/天|每天|每人)"
        r"|(?P<slash_price>\d+)\s*/天"
        r"|每天\s*(?P<daily_price>\d+)\s*(?:元|块)?",
        message,
    )
    if not match:
        return None
    price = (
        match.group("price")
        or match.group("attendance_price")
        or match.group("price_before")
        or match.group("slash_price")
        or match.group("daily_price")
    )
    return int(price)


def extract_money_amount(message: str) -> int | None:
    match = re.search(r"(?P<amount>\d+)\s*(?:元|块|百|千)?", message)
    if not match:
        return None
    return int(match.group("amount"))


def extract_phone(message: str) -> str | None:
    match = re.search(r"(?P<phone>1[3-9]\d{9})", message)
    if not match:
        return None
    return match.group("phone")


def extract_labor_quantity(message: str) -> int | None:
    if re.search(r"(?:来了一天|上工一天|出勤一天|一天)", message):
        return 1
    match = re.search(r"(?P<quantity>\d+)\s*天", message)
    if not match:
        return None
    return int(match.group("quantity"))


def extract_work_order_quantity(message: str) -> int | None:
    match = re.search(
        r"(?:干了|做了|上工|出勤)\s*(?P<quantity>\d+)\s*天"
        r"|(?P<worker>[\u4e00-\u9fa5A-Za-z0-9]{1,8})(?:这个月|本月)?.{0,4}?干了\s*(?P<worker_quantity>\d+)\s*天",
        message,
    )
    if not match:
        return None
    quantity = match.group("quantity") or match.group("worker_quantity")
    return int(quantity)


def extract_unit_name(message: str) -> str | None:
    field_match = re.search(
        r"(?:去|到|在)(?P<unit>[\u4e00-\u9fa5A-Za-z0-9]{1,12}?"
        r"(?:大棚|田块|地块|棚|田|地))(?=采收|授粉|作业|$)",
        message,
    )
    if field_match:
        return field_match.group("unit")
    match = re.search(r"(?P<unit>\d+\s*号棚)", message)
    if not match:
        return None
    return match.group("unit").replace(" ", "")


def extract_operation_type(message: str) -> str | None:
    if "采收" in message or re.search(r"收(?:水稻|麦|菜|瓜|果|玉米)", message):
        return "采收"
    for operation_type in hints.OPERATION_HINTS:
        if operation_type in message:
            return operation_type
    return None


def extract_wage_operation_type(message: str) -> str | None:
    operation_type = extract_operation_type(message)
    if operation_type:
        return operation_type
    for item in _WAGE_OPERATION_TYPES:
        if item in message:
            return item
    return None
