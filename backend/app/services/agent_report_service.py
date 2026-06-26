"""Agent 报告生成服务。"""

import json
import logging
from decimal import Decimal
from pathlib import Path

from jinja2 import Template
from langchain_core.messages import HumanMessage
from sqlalchemy.orm import Session

from app.agent.guardrails import filter_output
from app.agent.llm import get_llm
from app.core.json_repair import safe_parse_json
from app.infra.repository_runtime import (
    get_agent_record_repository,
    run_maybe_awaitable,
)
from app.models.agent_record import AgentRecord
from app.schemas.agent import ReportResponse
from app.schemas.structured_report import (
    ReportAdviceItem,
    ReportCostItem,
    ReportCycleItem,
    ReportLogItem,
    ReportOverviewMetrics,
    StructuredReportData,
)
from app.services import report_data_service
from app.services.report_sections import build_report_sections, metric_items

logger = logging.getLogger(__name__)


async def generate_report(
    db: Session,
    farm_id: int,
    cycle_id: int | None = None,
    report_type: str = "weekly",
) -> ReportResponse:
    """生成结构化种植报告并保存。"""
    logger.info("生成报告 | type=%s cycle=%s farm=%s", report_type, cycle_id, farm_id)
    report_data = await _load_report_data(db, farm_id, cycle_id, report_type)
    raw = await _generate_llm_report(report_data)
    copywriting = _parse_report_copywriting(raw, report_type)
    structured_data = _build_structured_report(report_data, copywriting)
    content = _render_human_readable_content(report_type, report_data, structured_data)
    record = _save_report_record(
        db,
        farm_id=farm_id,
        cycle_id=cycle_id,
        record_type=report_type,
        content=content,
        structured_data=structured_data,
    )
    return ReportResponse(
        cycle_id=record.cycle_id,
        report_type=record.record_type,
        content=record.content,
        structured_data=structured_data.model_dump(mode="json"),
        created_at=record.created_at,
    )


async def _load_report_data(
    db: Session,
    farm_id: int,
    cycle_id: int | None,
    report_type: str,
):
    if report_type == "monthly":
        report_data = await report_data_service.get_monthly_report_data(db, farm_id)
    else:
        report_data = await report_data_service.get_weekly_report_data(db, farm_id)

    if cycle_id is not None:
        report_data = _filter_report_data_by_cycle(report_data, cycle_id)
    return report_data


def _filter_report_data_by_cycle(report_data, cycle_id: int):
    """按茬口过滤报告事实，并重建派生结构化字段。"""
    report_data.cycles = [
        cycle for cycle in report_data.cycles if cycle["cycle_id"] == cycle_id
    ]
    report_data.costs = [
        cost for cost in report_data.costs if cost.get("cycle_id") == cycle_id
    ]
    report_data.logs = [
        log for log in report_data.logs if log.get("cycle_id") == cycle_id
    ]
    report_data.operation_work_orders = [
        order
        for order in getattr(report_data, "operation_work_orders", [])
        if order.get("cycle_id") == cycle_id
    ]
    order_ids = {order["id"] for order in report_data.operation_work_orders}
    report_data.labor_entries = [
        entry
        for entry in getattr(report_data, "labor_entries", [])
        if entry.get("work_order_id") in order_ids
    ]
    allowed_ref_ids = _cycle_source_ref_ids(report_data)
    report_data.source_refs = [
        ref
        for ref in getattr(report_data, "source_refs", [])
        if ref["id"] in allowed_ref_ids
    ]
    report_data.source_summary = _source_summary(report_data.source_refs)
    report_data.metric_facts = _cycle_metric_facts(report_data)
    report_data.metrics = metric_items(report_data.metric_facts)
    report_data.previous_period = _cycle_previous_period(report_data)
    report_data.sections = build_report_sections(
        report_data.report_type,
        metric_facts=report_data.metric_facts,
        cycles=report_data.cycles,
        costs=report_data.costs,
        logs=report_data.logs,
        work_orders=report_data.operation_work_orders,
        labor_summary=report_data.labor_summary,
        previous_period=report_data.previous_period or {},
        weather=report_data.weather,
        source_refs=report_data.source_refs,
    )
    return report_data


def _cycle_source_ref_ids(report_data) -> set[str]:
    allowed = {
        ref_id
        for cycle in report_data.cycles
        for ref_id in cycle.get("source_ref_ids", [])
    }
    allowed.update(f"cost_record:{item['id']}" for item in report_data.costs)
    allowed.update(f"farm_log:{item['id']}" for item in report_data.logs)
    allowed.update(
        f"operation_work_order:{item['id']}"
        for item in report_data.operation_work_orders
    )
    allowed.update(f"labor_entry:{item['id']}" for item in report_data.labor_entries)
    worker_ids = {
        entry["worker_id"]
        for entry in report_data.labor_entries
        if entry.get("worker_id") is not None
    }
    allowed.update(f"worker:{worker_id}" for worker_id in worker_ids)
    if report_data.farm:
        allowed.add(f"farm:{report_data.farm['id']}")
    if report_data.user_settings:
        allowed.add(f"user_setting:{report_data.user_settings['id']}")
    if report_data.weather.get("available"):
        allowed.add("weather_service")
    return allowed


def _source_summary(source_refs: list[dict]) -> list[dict]:
    counts: dict[str, int] = {}
    for ref in source_refs:
        counts[ref["source_type"]] = counts.get(ref["source_type"], 0) + 1
    return [
        {"source_type": source_type, "count": count}
        for source_type, count in sorted(counts.items())
    ]


def _cycle_metric_facts(report_data) -> dict:
    total_cost = _sum_amounts(
        cost["amount"] for cost in report_data.costs if cost["record_type"] == "cost"
    )
    total_income = _sum_amounts(
        cost["amount"] for cost in report_data.costs if cost["record_type"] == "income"
    )
    labor_cost = _sum_amounts(
        entry["payable_amount"] for entry in report_data.labor_entries
    )
    paid_amount = _sum_amounts(
        entry["paid_amount"] for entry in report_data.labor_entries
    )
    unpaid_amount = _sum_amounts(
        entry["unpaid_amount"] for entry in report_data.labor_entries
    )
    worker_count = len(
        {
            entry["worker_id"]
            for entry in report_data.labor_entries
            if entry.get("worker_id") is not None
        }
    )
    report_data.labor_summary = {
        "entry_count": len(report_data.labor_entries),
        "worker_count": worker_count,
        "payable_amount": _format_number(labor_cost),
        "paid_amount": _format_number(paid_amount),
        "unpaid_amount": _format_number(unpaid_amount),
        "labor_cost": _format_number(labor_cost),
    }
    overview = {
        "active_cycles": len(report_data.cycles),
        "log_count": len(report_data.logs),
        "total_cost": _format_number(total_cost),
        "total_income": _format_number(total_income),
        "net_profit": _format_number(total_income - total_cost),
    }
    report_data.overview = overview
    return {
        **overview,
        "work_order_count": len(report_data.operation_work_orders),
        "cost_record_count": len(report_data.costs),
        "labor": report_data.labor_summary,
    }


def _cycle_previous_period(report_data) -> dict:
    previous_period = dict(report_data.previous_period or {})
    previous_period["has_baseline"] = False
    previous_period["changes"] = {}
    previous_period["metrics"] = {
        "total_cost": "0",
        "total_income": "0",
        "net_profit": "0",
        "log_count": 0,
        "work_order_count": 0,
    }
    return previous_period


def _sum_amounts(values) -> Decimal:
    return sum((Decimal(str(value or "0")) for value in values), Decimal("0"))


def _format_number(value: Decimal) -> str:
    return (
        str(int(value))
        if value == value.to_integral_value()
        else str(value.normalize())
    )


async def _generate_llm_report(report_data) -> str:
    data_json = json.dumps(
        {
            "report_type": report_data.report_type,
            "period": getattr(
                report_data,
                "period",
                {
                    "start": report_data.period_start.isoformat(),
                    "end": report_data.period_end.isoformat(),
                    "label": "本月" if report_data.report_type == "monthly" else "本周",
                    "granularity": (
                        "month" if report_data.report_type == "monthly" else "week"
                    ),
                },
            ),
            "overview": report_data.overview,
            "cycles": report_data.cycles,
            "costs": report_data.costs,
            "logs": report_data.logs,
            "metrics": getattr(report_data, "metrics", []),
            "sections": getattr(report_data, "sections", []),
            "source_summary": getattr(report_data, "source_summary", []),
        },
        ensure_ascii=False,
        default=str,
    )
    prompts_dir = Path(__file__).parent.parent.parent / "prompts"
    template_path = prompts_dir / "structured_report.j2"
    prompt_text = Template(template_path.read_text()).render(report_data_json=data_json)
    response = await get_llm().ainvoke([HumanMessage(content=prompt_text)])
    return filter_output(response.content or "")


def _parse_report_copywriting(raw: str, report_type: str) -> dict:
    """解析 LLM 文案输出，只保留允许的文案字段。"""
    fallback = _fallback_copywriting(report_type, raw)
    try:
        parsed = safe_parse_json(raw)
        if isinstance(parsed, dict):
            summary = _coerce_summary(parsed.get("summary"))
            recommendations = _coerce_recommendations(
                parsed.get("recommendations", parsed.get("advice_items", []))
            )
            highlights = _coerce_highlights(parsed.get("highlights", []))
            if summary or recommendations or highlights:
                return {
                    "summary": summary or fallback["summary"],
                    "recommendations": recommendations or fallback["recommendations"],
                    "highlights": highlights,
                }
    except Exception as exc:
        logger.warning("报告建议解析失败，使用 fallback | error=%s", exc)
    return fallback


def _coerce_summary(value) -> dict:
    if isinstance(value, dict):
        text = str(value.get("text", ""))[:200]
        title = str(value.get("title", ""))[:40]
        return {"title": title, "text": text} if title or text else {}
    if value:
        return {"title": "", "text": str(value)[:200]}
    return {}


def _coerce_highlights(value) -> list[dict]:
    if not isinstance(value, list):
        return []
    highlights = []
    for item in value[:5]:
        if isinstance(item, dict):
            text = str(item.get("text", ""))[:100]
            if text:
                highlights.append({"text": text})
        elif item:
            highlights.append({"text": str(item)[:100]})
    return highlights


def _coerce_recommendations(value) -> list[dict]:
    if not isinstance(value, list):
        return []
    recommendations = []
    for item in value[:5]:
        if not isinstance(item, dict):
            continue
        title = str(item.get("title", ""))[:20]
        detail = str(item.get("detail", ""))[:120]
        try:
            priority = int(item.get("priority", 2))
        except (TypeError, ValueError):
            priority = 2
        priority = min(3, max(1, priority))
        if title or detail:
            recommendations.append(
                {"title": title, "detail": detail, "priority": priority}
            )
    return recommendations


def _fallback_copywriting(report_type: str, raw: str = "") -> dict:
    type_label = "月报" if report_type == "monthly" else "周报"
    summary_text = raw[:100] if raw else f"{type_label}生成完成"
    return {
        "summary": {"title": f"{type_label}总结", "text": summary_text},
        "highlights": [],
        "recommendations": [
            {
                "title": "持续记录",
                "detail": "保持农事、成本和用工记录完整，便于后续复盘。",
                "priority": 2,
            }
        ],
    }


def _build_structured_report(
    report_data,
    copywriting: dict,
) -> StructuredReportData:
    summary = _summary_with_highlights(copywriting)
    payload = {
        "report_type": report_data.report_type,
        "period_start": report_data.period_start,
        "period_end": report_data.period_end,
        "overview": ReportOverviewMetrics(**report_data.overview),
        "cycles": [ReportCycleItem(**cycle) for cycle in report_data.cycles],
        "costs": [ReportCostItem(**cost) for cost in report_data.costs],
        "logs": [ReportLogItem(**log) for log in report_data.logs],
        "advice": [
            ReportAdviceItem(**item) for item in copywriting["recommendations"][:4]
        ],
        "summary": summary,
        "period": getattr(
            report_data,
            "period",
            {
                "start": report_data.period_start,
                "end": report_data.period_end,
                "label": "本月" if report_data.report_type == "monthly" else "本周",
                "granularity": (
                    "month" if report_data.report_type == "monthly" else "week"
                ),
            },
        ),
        "metrics": getattr(report_data, "metrics", []),
        "sections": getattr(report_data, "sections", []),
        "recommendations": copywriting["recommendations"],
        "source_summary": getattr(report_data, "source_summary", []),
        "source_refs": getattr(report_data, "source_refs", []),
    }
    return StructuredReportData(**payload)


def _summary_with_highlights(copywriting: dict) -> dict:
    summary = dict(copywriting["summary"])
    summary["highlights"] = [
        item["text"] for item in copywriting.get("highlights", []) if item.get("text")
    ]
    return summary


def _render_human_readable_content(
    report_type: str,
    report_data,
    structured_data: StructuredReportData,
) -> str:
    type_label = "周报" if report_type == "weekly" else "月报"
    content_lines = [
        f"## {type_label} ({report_data.period_start} ~ {report_data.period_end})",
        "",
        f"**农场概览**：活跃茬口 {structured_data.overview.active_cycles} 个，"
        f"农事 {structured_data.overview.log_count} 次，"
        f"净收支 {structured_data.overview.net_profit} 元",
        "",
        f"**总结**：{_summary_text(structured_data.summary)}",
        "",
        "**建议**：",
    ]
    for item in structured_data.advice:
        priority_label = {1: "【高】", 2: "【中】", 3: "【低】"}.get(item.priority, "")
        content_lines.append(f"- {priority_label}{item.title}：{item.detail}")
    return "\n".join(content_lines)


def _summary_text(summary) -> str:
    """兼容新旧摘要结构，提取 Markdown 摘要文本。"""
    if isinstance(summary, dict):
        return str(summary.get("text", ""))
    if hasattr(summary, "text"):
        return str(summary.text)
    return str(summary)


def _save_report_record(
    db: Session,
    *,
    farm_id: int,
    cycle_id: int | None,
    record_type: str,
    content: str,
    structured_data: StructuredReportData,
) -> AgentRecord:
    record = AgentRecord(
        cycle_id=cycle_id,
        record_type=record_type,
        content=content,
        meta=json.dumps(structured_data.model_dump(mode="json"), ensure_ascii=False),
        farm_id=farm_id,
    )
    try:
        record = run_maybe_awaitable(get_agent_record_repository(db).create(record))
    except Exception:
        db.rollback()
        raise
    logger.info("报告已保存 | record_id=%s", record.id)
    return record


__all__ = ["generate_report"]
