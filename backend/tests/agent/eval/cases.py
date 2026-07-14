"""Eval 用例数据。

设计意图（13_Agent范式规范化设计.md §5.9.5）：
- B 类：按意图/写操作/多意图/闲聊维度覆盖
- D 类：同意图不同表达方式
- E2 类：多轮污染场景
"""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class EvalCase:
    case_id: str
    category: str  # B_QUERY / B_WRITE / B_MULTI_INTENT / B_CHITCHAT / E2_MULTITURN
    user_message: str
    expected_skill: str | None  # 期望工具；闲聊负例为 None
    pollution_data: dict[str, str] | None = None  # 注入 ContextBundle 的污染数据
    skill_mock_return: dict | None = None  # Skill mock 返回值（与污染不同）
    previous_turns: list[str] = field(default_factory=list)  # E2 多轮历史


B_QUERY_CASES: list[EvalCase] = [
    # Weather (4)
    EvalCase("q-weather-1", "B_QUERY", "天气如何", "get_weather_forecast"),
    EvalCase("q-weather-2", "B_QUERY", "今天下雨吗", "get_weather_forecast"),
    EvalCase("q-weather-3", "B_QUERY", "明天出门要带伞吗", "get_weather_forecast"),
    EvalCase("q-weather-4", "B_QUERY", "看下天气预报", "get_weather_forecast"),
    # Crop cycles (4)
    EvalCase("q-cycle-1", "B_QUERY", "我的茬口", "manage_crop_cycle"),
    EvalCase("q-cycle-2", "B_QUERY", "当前种了什么", "manage_crop_cycle"),
    EvalCase("q-cycle-3", "B_QUERY", "几号棚在种", "manage_crop_cycle"),
    EvalCase("q-cycle-4", "B_QUERY", "种植批次列表", "manage_crop_cycle"),
    # Workers (4)
    EvalCase("q-workers-1", "B_QUERY", "我的工人", "get_workers"),
    EvalCase("q-workers-2", "B_QUERY", "有哪些工人", "get_workers"),
    EvalCase("q-workers-3", "B_QUERY", "工人列表", "get_workers"),
    EvalCase("q-workers-4", "B_QUERY", "现在谁在干", "get_workers"),
    # Labor payables (4)
    EvalCase("q-payables-1", "B_QUERY", "未付人工", "get_labor_payables"),
    EvalCase("q-payables-2", "B_QUERY", "还欠多少人工钱", "get_labor_payables"),
    EvalCase("q-payables-3", "B_QUERY", "应付工资", "get_labor_payables"),
    EvalCase("q-payables-4", "B_QUERY", "人工欠款", "get_labor_payables"),
    # Debt summary (4)
    EvalCase("q-debt-1", "B_QUERY", "欠款", "get_debt_summary"),
    EvalCase("q-debt-2", "B_QUERY", "还欠别人多少", "get_debt_summary"),
    EvalCase("q-debt-3", "B_QUERY", "赊账统计", "get_debt_summary"),
    EvalCase("q-debt-4", "B_QUERY", "欠谁钱", "get_debt_summary"),
]

B_WRITE_CASES: list[EvalCase] = [
    EvalCase("w-cost-1", "B_WRITE", "记一笔化肥200元", "create_cost_record"),
    EvalCase("w-cost-2", "B_WRITE", "今天买了50块农药", "create_cost_record"),
    EvalCase("w-cost-3", "B_WRITE", "卖了300元西瓜", "create_cost_record"),
    EvalCase("w-log-1", "B_WRITE", "今天浇水了", "manage_farm_logs"),
    EvalCase("w-log-2", "B_WRITE", "记一下昨天施肥", "manage_farm_logs"),
    EvalCase("w-cycle-1", "B_WRITE", "新建茬口种西瓜", "manage_crop_cycle"),
    EvalCase("w-worker-1", "B_WRITE", "新来工人李丽日薪100", "manage_workers"),
    EvalCase("w-wage-1", "B_WRITE", "给李海记15天压瓜工资每天180", "manage_wages"),
    EvalCase("w-settle-1", "B_WRITE", "把李海这笔工资结了", "settle_labor_payment"),
    EvalCase(
        "w-order-1", "B_WRITE", "李海今天去6号棚压蔓", "create_operation_work_order"
    ),
]

B_MULTI_INTENT_CASES: list[EvalCase] = [
    EvalCase(
        "m-1", "B_MULTI_INTENT", "新来工人李丽工资100一天，今天去6号棚收水稻", None
    ),
    EvalCase("m-2", "B_MULTI_INTENT", "记一笔化肥200元，顺便看看还欠多少钱", None),
    EvalCase("m-3", "B_MULTI_INTENT", "李海这个月干了15天压瓜", None),
    EvalCase("m-4", "B_MULTI_INTENT", "浇水了，同时给李海结一下工资", None),
    EvalCase("m-5", "B_MULTI_INTENT", "新建茬口番茄，再记一笔种子费50", None),
]

B_CHITCHAT_CASES: list[EvalCase] = [
    EvalCase("c-1", "B_CHITCHAT", "你好", None),
    EvalCase("c-2", "B_CHITCHAT", "今天真热", None),
    EvalCase("c-3", "B_CHITCHAT", "谢谢", None),
    EvalCase("c-4", "B_CHITCHAT", "你是谁", None),
    EvalCase("c-5", "B_CHITCHAT", "再见", None),
    EvalCase("c-6", "B_CHITCHAT", "今天干点啥", None),
    EvalCase("c-7", "B_CHITCHAT", "在吗", None),
    EvalCase("c-8", "B_CHITCHAT", "好的", None),
]

E2_MULTITURN_CASES: list[EvalCase] = [
    EvalCase(
        "e2-1",
        "E2_MULTITURN",
        "天气如何",
        "get_weather_forecast",
        previous_turns=["你好", "最近忙啥"],
        pollution_data={"weather_snapshot": "晴 30℃"},
        skill_mock_return={"weather": "雨 25℃", "forecast": "未来 3 小时有雨"},
    ),
    EvalCase(
        "e2-2",
        "E2_MULTITURN",
        "我的茬口",
        "manage_crop_cycle",
        previous_turns=["你好", "我管理农场"],
        pollution_data={"crop_cycle_details": "西瓜苗期"},
        skill_mock_return={"cycles": [{"name": "番茄", "stage": "开花期"}]},
    ),
    EvalCase(
        "e2-3",
        "E2_MULTITURN",
        "未付人工",
        "get_labor_payables",
        previous_turns=["记一笔", "好的"],
        pollution_data={"labor_payables_snapshot": "未付 500 元"},
        skill_mock_return={"payables": [{"worker": "李海", "amount": 800}]},
    ),
    EvalCase(
        "e2-4",
        "E2_MULTITURN",
        "我的工人",
        "get_workers",
        previous_turns=["你好", "今天天气不错"],
        pollution_data={"worker_list_snapshot": "李海、王五"},
        skill_mock_return={
            "workers": [{"name": "李海"}, {"name": "王五"}, {"name": "赵六"}]
        },
    ),
    EvalCase(
        "e2-5",
        "E2_MULTITURN",
        "欠款",
        "get_debt_summary",
        previous_turns=["记账", "好的"],
        pollution_data={"debt_summary_snapshot": "欠 1000"},
        skill_mock_return={"debts": [{"party": "张三", "amount": 1500}]},
    ),
]


def all_eval_cases() -> list[EvalCase]:
    return (
        B_QUERY_CASES
        + B_WRITE_CASES
        + B_MULTI_INTENT_CASES
        + B_CHITCHAT_CASES
        + E2_MULTITURN_CASES
    )


def cases_by_category(category: str) -> list[EvalCase]:
    return [c for c in all_eval_cases() if c.category == category]
