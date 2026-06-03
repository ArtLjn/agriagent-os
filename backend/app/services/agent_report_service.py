"""Agent 报告生成服务。"""

import json
import logging
from pathlib import Path

from jinja2 import Template
from langchain_core.messages import HumanMessage
from sqlalchemy.orm import Session

from app.agent.guardrails import filter_output
from app.agent.llm import get_llm
from app.infra.json_repair import safe_parse_json
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
    summary, advice_items = _parse_report_advice(raw)
    structured_data = _build_structured_report(report_data, summary, advice_items)
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
        report_data.cycles = [
            cycle for cycle in report_data.cycles if cycle["cycle_id"] == cycle_id
        ]
        report_data.costs = [
            cost for cost in report_data.costs if cost.get("cycle_id") == cycle_id
        ]
        report_data.logs = [
            log for log in report_data.logs if log.get("cycle_id") == cycle_id
        ]
    return report_data


async def _generate_llm_report(report_data) -> str:
    data_json = json.dumps(
        {
            "report_type": report_data.report_type,
            "period": f"{report_data.period_start.isoformat()} ~ {report_data.period_end.isoformat()}",
            "overview": report_data.overview,
            "cycles": report_data.cycles,
            "costs": report_data.costs,
            "logs": report_data.logs,
        },
        ensure_ascii=False,
        default=str,
    )
    prompts_dir = Path(__file__).parent.parent.parent / "prompts"
    template_path = prompts_dir / "structured_report.j2"
    prompt_text = Template(template_path.read_text()).render(report_data_json=data_json)
    response = await get_llm().ainvoke([HumanMessage(content=prompt_text)])
    return filter_output(response.content or "")


def _parse_report_advice(raw: str) -> tuple[str, list[ReportAdviceItem]]:
    summary = ""
    advice_items: list[ReportAdviceItem] = []
    try:
        parsed = safe_parse_json(raw)
        if isinstance(parsed, dict):
            summary = str(parsed.get("summary", ""))[:200]
            for item in parsed.get("advice_items", []):
                advice_items.append(
                    ReportAdviceItem(
                        title=str(item.get("title", ""))[:20],
                        detail=str(item.get("detail", ""))[:100],
                        priority=int(item.get("priority", 2)),
                    )
                )
    except Exception as exc:
        logger.warning("报告建议解析失败，使用 fallback | error=%s", exc)

    if not advice_items:
        summary = summary or (raw[:100] if raw else "报告生成完成")
        advice_items = [
            ReportAdviceItem(title="农事建议", detail=summary[:100], priority=2)
        ]
    return summary, advice_items


def _build_structured_report(
    report_data,
    summary: str,
    advice_items: list[ReportAdviceItem],
) -> StructuredReportData:
    return StructuredReportData(
        report_type=report_data.report_type,
        period_start=report_data.period_start,
        period_end=report_data.period_end,
        overview=ReportOverviewMetrics(**report_data.overview),
        cycles=[ReportCycleItem(**cycle) for cycle in report_data.cycles],
        costs=[ReportCostItem(**cost) for cost in report_data.costs],
        logs=[ReportLogItem(**log) for log in report_data.logs],
        advice=advice_items,
        summary=summary,
    )


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
        f"**总结**：{structured_data.summary}",
        "",
        "**建议**：",
    ]
    for item in structured_data.advice:
        priority_label = {1: "【高】", 2: "【中】", 3: "【低】"}.get(item.priority, "")
        content_lines.append(f"- {priority_label}{item.title}：{item.detail}")
    return "\n".join(content_lines)


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
    db.add(record)
    try:
        db.commit()
        db.refresh(record)
    except Exception:
        db.rollback()
        raise
    logger.info("报告已保存 | record_id=%s", record.id)
    return record


__all__ = ["generate_report"]
