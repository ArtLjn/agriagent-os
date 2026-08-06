"""报告 A2UI section 组装工具。"""

from __future__ import annotations

from decimal import Decimal


def metric_items(metric_facts: dict) -> list[dict]:
    """生成 A2UI 指标项。"""
    labor = metric_facts.get("labor", {})
    return [
        {"label": "农事记录", "value": str(metric_facts.get("log_count", 0)), "unit": "次"},
        {"label": "作业单", "value": str(metric_facts.get("work_order_count", 0)), "unit": "个"},
        {"label": "净收支", "value": str(metric_facts.get("net_profit", "0")), "unit": "元"},
        {"label": "人工成本", "value": str(labor.get("labor_cost", "0")), "unit": "元"},
    ]


def _format_amount(amount: Decimal) -> str:
    """格式化金额，去除不必要的零。"""
    if amount == amount.to_integral_value():
        return str(int(amount))
    return str(amount.normalize())


def build_report_sections(
    report_type: str,
    *,
    metric_facts: dict,
    cycles: list[dict],
    costs: list[dict],
    logs: list[dict],
    work_orders: list[dict],
    labor_summary: dict,
    previous_period: dict,
    weather: dict,
    source_refs: list[dict],
) -> list[dict]:
    """根据报告类型组装 A2UI section。"""
    if report_type == "monthly":
        return _monthly_sections(
            metric_facts=metric_facts,
            cycles=cycles,
            costs=costs,
            logs=logs,
            work_orders=work_orders,
            labor_summary=labor_summary,
            previous_period=previous_period,
            source_refs=source_refs,
        )
    return _weekly_sections(
        metric_facts=metric_facts,
        cycles=cycles,
        costs=costs,
        logs=logs,
        work_orders=work_orders,
        weather=weather,
        source_refs=source_refs,
    )


def _source_ids(refs: list[dict], *source_types: str) -> list[str]:
    allowed = set(source_types)
    return [ref["id"] for ref in refs if ref["source_type"] in allowed]


def _weekly_sections(
    *,
    metric_facts: dict,
    cycles: list[dict],
    costs: list[dict],
    logs: list[dict],
    work_orders: list[dict],
    weather: dict,
    source_refs: list[dict],
) -> list[dict]:
    weather_risk = _weather_risk_payload(weather)
    return [
        {
            "type": "weekly_snapshot",
            "title": "本周快照",
            "items": metric_items(metric_facts),
            "data": metric_facts,
            "source_ref_ids": _source_ids(
                source_refs, "farm_log", "cost_record", "operation_work_order", "labor_entry"
            ),
        },
        {
            "type": "operation_review",
            "title": "农事执行复盘",
            "items": logs[:10],
            "data": {"total": len(logs)},
            "source_ref_ids": _source_ids(source_refs, "farm_log"),
        },
        {
            "type": "work_order_status",
            "title": "作业单状态",
            "items": work_orders[:10],
            "data": {"total": len(work_orders)},
            "source_ref_ids": _source_ids(source_refs, "operation_work_order"),
        },
        {
            "type": "crop_stage_updates",
            "title": "茬口阶段进展",
            "items": cycles[:10],
            "data": {"total": len(cycles)},
            "source_ref_ids": _source_ids(source_refs, "crop_cycle", "cycle_stage"),
        },
        {
            "type": "finance_flow",
            "title": "财务流水",
            "items": costs[:10],
            "data": {
                "total": len(costs),
                "total_cost": metric_facts.get("total_cost", "0"),
                "total_income": metric_facts.get("total_income", "0"),
                "net_profit": metric_facts.get("net_profit", "0"),
            },
            "source_ref_ids": _source_ids(source_refs, "cost_record", "labor_entry"),
        },
        {
            "type": "weather_risks",
            "title": "未来天气风险",
            "items": weather_risk["items"],
            "data": weather_risk["data"],
            "source_ref_ids": _source_ids(source_refs, "weather_service"),
        },
        {
            "type": "next_actions",
            "title": "下周行动建议",
            "items": weather_risk["actions"],
            "data": {},
            "source_ref_ids": _source_ids(
                source_refs, "crop_cycle", "operation_work_order", "weather_service"
            ),
        },
    ]


def _weather_risk_payload(weather: dict) -> dict:
    warnings = [str(item) for item in weather.get("warnings", []) if item]
    if not weather.get("available"):
        return {
            "items": [],
            "actions": [],
            "data": {
                "available": False,
                "risk_level": "none",
                "summary": "天气信源暂不可用，本周行动以已记录农事和现场观察为准。",
                "action_hint": "关键露天作业前建议重新确认当地天气。",
                "warnings": [],
                "error": weather.get("error"),
            },
        }

    items = [_weather_warning_item(warning) for warning in warnings]
    risk_level = _weather_risk_level(items)
    summary = _weather_summary(warnings, risk_level)
    action_hint = _weather_action_hint(items)
    actions = []
    if action_hint:
        actions.append(
            {
                "source": "weather",
                "title": "避开天气风险窗口",
                "detail": action_hint,
                "priority": 2 if risk_level == "medium" else 1,
            }
        )
    return {
        "items": items,
        "actions": actions,
        "data": {
            "available": True,
            "risk_level": risk_level,
            "summary": summary,
            "action_hint": action_hint,
            "warnings": warnings,
            "error": None,
        },
    }


def _weather_warning_item(warning: str) -> dict:
    title = "天气风险"
    suggested_action = "作业前确认天气变化，必要时调整作业时段。"
    priority = 2
    if "雨" in warning or "降水" in warning:
        title = "明显降雨"
        suggested_action = "露天打药、施肥和采收尽量避开降雨窗口。"
    elif "高温" in warning or "热" in warning:
        title = "高温风险"
        suggested_action = "避开午后高温作业，关注棚内通风和补水。"
    elif "大风" in warning or "风" in warning:
        title = "大风风险"
        suggested_action = "暂停喷药和覆膜等受风影响较大的作业。"
    elif "低温" in warning or "降温" in warning or "寒潮" in warning:
        title = "低温风险"
        suggested_action = "提前检查保温覆盖，保护幼苗和开花坐果作物。"
    if "暴" in warning or "强" in warning or "寒潮" in warning:
        priority = 1
    return {
        "title": title,
        "detail": warning,
        "priority": priority,
        "suggested_action": suggested_action,
    }


def _weather_risk_level(items: list[dict]) -> str:
    if not items:
        return "low"
    if any(item["priority"] == 1 for item in items):
        return "high"
    return "medium"


def _weather_summary(warnings: list[str], risk_level: str) -> str:
    if not warnings:
        return "未来几天暂无明显天气风险，可按既定农事计划推进。"
    risk_label = {"high": "较高", "medium": "中等", "low": "较低"}.get(
        risk_level, "中等"
    )
    return f"未来天气风险{risk_label}：" + "；".join(warnings[:2])


def _weather_action_hint(items: list[dict]) -> str:
    if not items:
        return "按原计划推进，关键作业前复核天气即可。"
    actions = [item["suggested_action"] for item in items[:2]]
    return " ".join(actions)


def _monthly_sections(
    *,
    metric_facts: dict,
    cycles: list[dict],
    costs: list[dict],
    logs: list[dict],
    work_orders: list[dict],
    labor_summary: dict,
    previous_period: dict,
    source_refs: list[dict],
) -> list[dict]:
    cost_by_category: dict[str, Decimal] = {}
    operation_counts: dict[str, int] = {}
    unsettled_items = []
    for cost in costs:
        if cost.get("record_type") == "cost":
            category = cost.get("category") or "未分类"
            amount = Decimal(str(cost.get("amount", "0")))
            cost_by_category[category] = cost_by_category.get(category, Decimal("0")) + amount
        if cost.get("record_type") == "cost" and cost.get("note"):
            unsettled_items.append(cost)
    for log in logs:
        op_type = log.get("operation_type") or "未知操作"
        operation_counts[op_type] = operation_counts.get(op_type, 0) + 1
    return [
        {
            "type": "monthly_kpis",
            "title": "月度指标",
            "items": metric_items(metric_facts),
            "data": metric_facts,
            "source_ref_ids": _source_ids(
                source_refs, "farm_log", "cost_record", "operation_work_order", "labor_entry"
            ),
        },
        {
            "type": "period_comparison",
            "title": "环比对比",
            "items": [],
            "data": previous_period,
            "source_ref_ids": [],
        },
        {
            "type": "cost_structure",
            "title": "成本结构",
            "items": [
                {"category": category, "amount": _format_amount(amount)}
                for category, amount in sorted(cost_by_category.items())
            ],
            "data": {"total": len(cost_by_category)},
            "source_ref_ids": _source_ids(source_refs, "cost_record"),
        },
        {
            "type": "cycle_portfolio",
            "title": "茬口组合",
            "items": cycles[:10],
            "data": {"total": len(cycles)},
            "source_ref_ids": _source_ids(source_refs, "crop_cycle", "cycle_stage"),
        },
        {
            "type": "operation_distribution",
            "title": "农事分布",
            "items": [
                {"operation_type": key, "count": value}
                for key, value in sorted(operation_counts.items())
            ],
            "data": {"log_total": len(logs), "work_order_total": len(work_orders)},
            "source_ref_ids": _source_ids(source_refs, "farm_log", "operation_work_order"),
        },
        {
            "type": "labor_summary",
            "title": "用工汇总",
            "items": [],
            "data": labor_summary,
            "source_ref_ids": _source_ids(source_refs, "labor_entry", "worker"),
        },
        {
            "type": "finance_exceptions",
            "title": "异常事项",
            "items": unsettled_items[:10],
            "data": {"total": len(unsettled_items)},
            "source_ref_ids": _source_ids(source_refs, "cost_record", "labor_entry"),
        },
        {
            "type": "next_month_plan",
            "title": "下月计划",
            "items": [],
            "data": {},
            "source_ref_ids": _source_ids(source_refs, "crop_cycle", "cycle_stage"),
        },
    ]


__all__ = ["build_report_sections", "metric_items"]
