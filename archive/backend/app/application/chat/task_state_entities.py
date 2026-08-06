"""TaskState 自然语言实体与缺失项抽取规则。"""

from __future__ import annotations

import re


def classify_task_type(user_input: str, assistant_reply: str) -> str:
    text = user_input + assistant_reply
    if is_crop_cycle_setup_intent(text):
        return "crop_cycle_setup"
    if any(keyword in text for keyword in ("诊断", "病害", "虫害", "症状", "叶斑")):
        return "diagnosis_followup"
    if has_planting_intent(text):
        return "planting_plan"
    if any(keyword in text for keyword in ("计划", "方案", "安排", "建议", "测算")):
        return "plan_draft"
    return "followup_task"


def next_action_for_task(
    task_type: str,
    missing: list[str],
    entities: dict[str, object],
) -> str | None:
    if missing:
        return f"等待用户补充：{missing[0]}"
    if task_type == "planting_plan" and _planting_plan_ready_for_setup(entities):
        return "询问是否创建作物模板、茬口和种植单元；缺少地块名称时先追问名称"
    return None


def extract_entities(text: str) -> dict[str, object]:
    if is_crop_cycle_setup_intent(text) or _has_crop_cycle_planning_signal(text):
        return _extract_crop_cycle_setup_entities(text)
    if has_planting_intent(text):
        return extract_planting_plan_entities(text)
    return _extract_general_entities(text)


def extract_entities_for_task(text: str, task_type: str) -> dict[str, object]:
    if task_type == "crop_cycle_setup":
        return _extract_crop_cycle_setup_entities(text)
    if task_type == "planting_plan":
        return extract_planting_plan_entities(text)
    return extract_entities(text)


def entity_source_for_existing_task(task_type: str, goal: str, user_input: str) -> str:
    if task_type in {"crop_cycle_setup", "planting_plan"}:
        return "\n".join(part for part in (str(goal or ""), user_input) if part)
    return user_input


def remaining_missing_after_user_reply_for_task(
    missing: list[str],
    user_input: str,
    task_type: str,
    entities: dict[str, object],
) -> list[str]:
    remaining = _remaining_missing_after_user_reply(missing, user_input)
    if task_type == "planting_plan":
        return planting_plan_missing_from_entities(remaining, entities)
    if task_type == "crop_cycle_setup":
        return _crop_cycle_setup_missing_from_entities(remaining, entities)
    return remaining


def planting_plan_missing_from_entities(
    current_missing: list[str],
    entities: dict[str, object],
) -> list[str]:
    required = []
    if entities.get("area_mu") in (None, ""):
        required.append("种植面积")
    if not any(
        entities.get(key) not in (None, "", {}, [])
        for key in ("area_target", "greenhouse", "planting_unit")
    ):
        required.append("地块")
    if entities.get("start_date") in (None, ""):
        required.append("计划播种时间")
    if entities.get("variety") in (None, ""):
        required.append("品种")
    return [item for item in current_missing if item in required]


def entity_observation_values(entities: dict[str, object]) -> list[str]:
    values = []
    for value in entities.values():
        if isinstance(value, dict):
            values.extend(str(item) for item in value.values() if item)
        elif value:
            values.append(str(value))
    return values


def merge_entities(
    base: dict[str, object], additions: dict[str, object]
) -> dict[str, object]:
    merged = dict(base)
    for key, value in additions.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = {**merged[key], **value}
        else:
            merged[key] = value
    return merged


def has_task_signal(text: str) -> bool:
    return any(
        keyword in text
        for keyword in (
            "帮我",
            "制定",
            "计划",
            "方案",
            "安排",
            "诊断",
            "分析",
            "怎么处理",
            "怎么办",
            "建议",
            "规划",
        )
    )


def has_natural_task_intent(text: str) -> bool:
    return has_planting_intent(text) or has_diagnosis_intent(text)


def has_planting_intent(text: str) -> bool:
    if not _extract_crop(text):
        return False
    return any(
        keyword in text
        for keyword in (
            "想种",
            "准备种",
            "打算种",
            "计划种",
            "要种",
            "能不能种",
            "适合种",
            "种植",
            "播种",
            "定植",
        )
    )


def has_diagnosis_intent(text: str) -> bool:
    return any(
        keyword in text
        for keyword in (
            "叶子发黄",
            "叶片发黄",
            "长斑",
            "烂根",
            "萎蔫",
            "枯萎",
            "虫",
            "病",
            "怎么处理",
            "怎么办",
        )
    )


def is_crop_cycle_setup_intent(text: str) -> bool:
    return "茬口" in text and any(
        word in text for word in ("创建", "新建", "新增", "建")
    )


def extract_planting_plan_entities(text: str) -> dict[str, object]:
    entities = _extract_general_entities(text)
    area_mu = _extract_area_mu(text)
    if area_mu is not None:
        entities["area_mu"] = area_mu
    variety = _extract_crop_variety_for_plan(text)
    if variety:
        entities["variety"] = variety
    start_date = _extract_start_date(text)
    if start_date:
        entities["start_date"] = start_date
    area_target = _extract_area_target(text)
    if area_target:
        entities["area_target"] = area_target
    return entities


def _remaining_missing_after_user_reply(
    missing: list[str], user_input: str
) -> list[str]:
    if not missing:
        return []
    return [
        item
        for item in missing
        if item and not _user_reply_resolves_missing_item(item, user_input)
    ]


def _user_reply_resolves_missing_item(missing_item: str, user_input: str) -> bool:
    text = user_input.strip()
    if missing_item in text:
        return True
    if "名称" in missing_item and _extract_planting_unit_name(text):
        return True
    if missing_item == "种植面积" and _extract_area_mu(text) is not None:
        return True
    if missing_item == "地块" and _extract_area_target(text):
        return True
    if missing_item == "计划播种时间" and _extract_start_date(text):
        return True
    if missing_item == "品种" and _extract_crop_variety_for_plan(text):
        return True
    core_word = _missing_core_word(missing_item)
    if core_word and core_word in text:
        return True
    return _input_unit_matches_missing_item(missing_item, text)


def _missing_core_word(missing_item: str) -> str:
    words = re.findall(r"[\u4e00-\u9fffA-Za-z0-9]+", missing_item)
    if not words:
        return missing_item
    text = "".join(words)
    for suffix in ("信息", "情况", "数据", "大小", "多少"):
        text = text.removesuffix(suffix)
    return text


def _input_unit_matches_missing_item(missing_item: str, user_input: str) -> bool:
    unit_patterns = _unit_patterns_for_missing_item(missing_item)
    if not unit_patterns:
        return False
    return any(re.search(pattern, user_input) for pattern in unit_patterns)


def _unit_patterns_for_missing_item(missing_item: str) -> list[str]:
    if any(keyword in missing_item for keyword in ("功率", "瓦数", "补光灯")):
        return [r"\d+(?:\.\d+)?\s*(?:瓦|w|W|千瓦|kw|KW)"]
    if any(keyword in missing_item for keyword in ("面积", "亩数", "棚室")):
        return [r"\d+(?:\.\d+)?\s*(?:亩|平方米|平米|㎡|m2|M2)"]
    if any(keyword in missing_item for keyword in ("重量", "用量", "剂量")):
        return [r"\d+(?:\.\d+)?\s*(?:斤|公斤|千克|克|g|G|kg|KG)"]
    if any(keyword in missing_item for keyword in ("数量", "株数", "棵数")):
        return [r"\d+(?:\.\d+)?\s*(?:株|棵|个|袋|瓶|箱)"]
    if any(keyword in missing_item for keyword in ("金额", "价格", "费用")):
        return [r"\d+(?:\.\d+)?\s*(?:元|块|万元|万)"]
    if any(keyword in missing_item for keyword in ("日期", "时间", "天数", "周期")):
        return [r"\d+(?:\.\d+)?\s*(?:天|小时|日|号)", r"(?:今天|明天|后天|昨天)"]
    return []


def _has_crop_cycle_planning_signal(text: str) -> bool:
    return "茬口" in text and any(
        keyword in text
        for keyword in ("规划", "计划", "安排", "创建", "新建", "新增", "建")
    )


def _extract_general_entities(text: str) -> dict[str, object]:
    crop = _extract_crop(text)
    entities = {}
    if crop:
        entities["crop"] = crop
    greenhouse = re.search(r"([\w一二三四五六七八九十\d号#-]+棚)", text)
    if greenhouse:
        entities["greenhouse"] = greenhouse.group(1)
    return entities


def _extract_crop_cycle_setup_entities(text: str) -> dict[str, object]:
    entities: dict[str, object] = {}
    crop = _extract_crop(text)
    if crop:
        entities["crop_name"] = crop
    variety = _extract_crop_variety(text) or _extract_crop_variety_for_plan(text)
    if variety:
        entities["variety"] = variety
    area_mu = _extract_area_mu(text)
    if area_mu is not None:
        entities["area_mu"] = area_mu
    start_date = _extract_start_date(text)
    if start_date:
        entities["start_date"] = start_date
    area_target = _extract_area_target(text)
    if area_target:
        entities["area_target"] = area_target

    planting_unit: dict[str, object] = {}
    unit_name = _extract_planting_unit_name(text)
    if unit_name:
        planting_unit["name"] = unit_name
        planting_unit["should_create"] = True
    if area_mu is not None and _has_planting_unit_create_intent(text):
        planting_unit["area_mu"] = area_mu
        planting_unit["should_create"] = True
    if planting_unit:
        entities["planting_unit"] = planting_unit
    return entities


def _crop_cycle_setup_missing_from_entities(
    current_missing: list[str],
    entities: dict[str, object],
) -> list[str]:
    if not current_missing:
        return []
    required = []
    if entities.get("crop_name") in (None, ""):
        required.append("作物")
    if entities.get("start_date") in (None, ""):
        required.append("起始日期")
    if entities.get("variety") in (None, ""):
        required.append("品种")
    if not any(
        entities.get(key) not in (None, "", {}, [])
        for key in ("area_mu", "area_target", "planting_unit")
    ):
        required.append("地块")
    normalized_missing = [
        item
        for item in current_missing
        if item and item not in {"以下关键信息", "关键信息"}
    ]
    return [
        item
        for item in normalized_missing
        if any(required_item in item for required_item in required)
    ]


def _planting_plan_ready_for_setup(entities: dict[str, object]) -> bool:
    return all(
        entities.get(key) not in (None, "")
        for key in ("crop", "area_mu", "start_date", "variety")
    ) and any(
        entities.get(key) not in (None, "", {}, [])
        for key in ("area_target", "greenhouse", "planting_unit")
    )


def _extract_crop(text: str) -> str:
    crops = (
        "番茄",
        "黄瓜",
        "西瓜",
        "水稻",
        "玉米",
        "辣椒",
        "茄子",
        "草莓",
        "小麦",
        "大豆",
    )
    for crop in crops:
        if crop in text:
            return crop
    match = re.search(r"给(.{1,8}?)(?:做|制定|出|安排|诊断|补光|施肥|打药)", text)
    return match.group(1).strip() if match else ""


def _extract_crop_variety(text: str) -> str:
    matches = re.findall(r"(?<!\d)(\d{2,})(?!\d)\s*(?!亩)", text)
    return matches[0] if matches else ""


def _extract_crop_variety_for_plan(text: str) -> str:
    numeric_variety = _extract_crop_variety(text)
    if numeric_variety:
        return numeric_variety

    crop = _extract_crop(text)
    if not crop:
        return ""
    phrase = _extract_crop_phrase_after_planting_action(text, crop)
    if not phrase or phrase == crop:
        return ""
    return phrase


def _extract_crop_phrase_after_planting_action(text: str, crop: str) -> str:
    pattern = (
        rf"(?:种|种植|播种|定植)\s*"
        rf"(?:个|一个|一些|点|点儿)?\s*"
        rf"(?:\d+(?:\.\d+)?|[一二两三四五六七八九十百]+)?\s*"
        rf"(?:亩|平米|平方米|㎡)?\s*"
        rf"([\u4e00-\u9fffA-Za-z0-9-]{{0,12}}{re.escape(crop)})"
    )
    matches = list(re.finditer(pattern, text))
    for match in reversed(matches):
        phrase = match.group(1).strip(" ，,。；;的地田")
        if phrase and phrase != crop:
            return phrase
    if not matches:
        fallback = re.search(
            rf"([\u4e00-\u9fffA-Za-z0-9-]{{1,8}}{re.escape(crop)})", text
        )
        if not fallback:
            return ""
        phrase = fallback.group(1).strip(" ，,。；;的地田")
        return "" if phrase == crop else phrase
    return ""


def _extract_area_mu(text: str) -> int | float | None:
    match = re.search(r"(\d+(?:\.\d+)?|[一二两三四五六七八九十百]+)\s*亩", text)
    if not match:
        return None
    value = _number_value(match.group(1))
    if value is None:
        return None
    return int(value) if value.is_integer() else value


def _number_value(raw_value: str) -> float | None:
    if re.fullmatch(r"\d+(?:\.\d+)?", raw_value):
        return float(raw_value)
    chinese_value = _chinese_number_value(raw_value)
    return float(chinese_value) if chinese_value is not None else None


def _chinese_number_value(raw_value: str) -> int | None:
    digits = {
        "一": 1,
        "二": 2,
        "两": 2,
        "三": 3,
        "四": 4,
        "五": 5,
        "六": 6,
        "七": 7,
        "八": 8,
        "九": 9,
    }
    if raw_value == "十":
        return 10
    if "百" in raw_value:
        left, _, right = raw_value.partition("百")
        hundred = digits.get(left, 1 if left == "" else 0)
        tail = _chinese_number_value(right) if right else 0
        return hundred * 100 + (tail or 0)
    if "十" in raw_value:
        left, _, right = raw_value.partition("十")
        ten = digits.get(left, 1 if left == "" else 0)
        tail = digits.get(right, 0) if right else 0
        return ten * 10 + tail
    return digits.get(raw_value)


def _extract_start_date(text: str) -> str:
    match = re.search(r"(下个月\s*\d{1,2}\s*号)", text)
    if match:
        return re.sub(r"\s+", "", match.group(1))
    for value in ("明年开春", "明年春天", "明年春季", "开春", "春季", "春天"):
        if value in text:
            return value
    match = re.search(r"(\d{1,2}\s*月(?:上旬|中旬|下旬|初|底)?)", text)
    return re.sub(r"\s+", "", match.group(1)) if match else ""


def _extract_area_target(text: str) -> str:
    if "连在一起" in text or "连片" in text:
        if "新租" in text:
            return "连片新租地"
        return "连片地"
    if "新租" in text and "地" in text:
        return "新租地"
    greenhouse = re.search(r"([\w一二三四五六七八九十\d号#-]+棚)", text)
    if greenhouse:
        return greenhouse.group(1)
    return ""


def _extract_planting_unit_name(text: str) -> str:
    match = re.search(r"(?:叫|命名为|名称是|名字叫)\s*([\w一-龥\d号#-]{1,20})", text)
    if not match:
        return ""
    name = match.group(1).strip(" ，,。；;！!？?")
    return name if any(keyword in name for keyword in ("棚", "地", "田", "区")) else ""


def _has_planting_unit_create_intent(text: str) -> bool:
    return bool(
        re.search(
            r"(?:新增|新建|创建|再建|建)\s*\d+(?:\.\d+)?\s*亩\s*(?:地|田|棚|种植单元)",
            text,
        )
        or re.search(r"(?:新增|新建|创建|再建|建).{0,8}(?:地块|大棚|种植单元)", text)
    )


__all__ = [
    "classify_task_type",
    "entity_observation_values",
    "entity_source_for_existing_task",
    "extract_entities",
    "extract_entities_for_task",
    "extract_planting_plan_entities",
    "has_diagnosis_intent",
    "has_natural_task_intent",
    "has_planting_intent",
    "has_task_signal",
    "is_crop_cycle_setup_intent",
    "merge_entities",
    "next_action_for_task",
    "planting_plan_missing_from_entities",
    "remaining_missing_after_user_reply_for_task",
]
