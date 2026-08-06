"""planting_plan 规则配置。"""

REQUIRED_SLOTS = ("crop", "season", "total_area_mu")
COST_WORDS = ("成本", "预算", "花费", "多少钱", "投入")
CREATE_WORDS = ("按这个创建", "创建计划", "建立茬口", "生成茬口")
PLANNER_VERSION = "planting_plan.v1"
RULE_PLANNER_VERSION = "planting_plan.rules.v1"


def required_slot_questions(missing_slots: list[str]) -> list[str]:
    labels = {
        "crop": "想规划哪种作物？",
        "season": "目标季节或时间窗口是什么？",
        "total_area_mu": "计划面积是多少亩？",
    }
    return [labels[slot] for slot in missing_slots if slot in labels]


def user_requested_cost(user_input: str) -> bool:
    return any(word in user_input for word in COST_WORDS)


def user_requested_create(user_input: str) -> bool:
    return any(word in user_input for word in CREATE_WORDS)
