"""茬口域聚合 Skill 与轻量 operation。"""

from datetime import date

from skillify.models.schemas import ResultStatus, SkillResult
from skillify.skills.base import Skill

from app.shared.database import SessionLocal
from app.domains.planting.cycle_models import CropCycle
from app.domains.planting.cycle_schemas import CropCycleCreate
from app.domains.planting import crop_service
from app.domains.planting import cycle_service
from app.domains.farm import context_service as farm_context_service
from app.skills.context import require_farm_context
from app.skills.metadata import SkillPermissionLevel, SkillRiskLevel

from .update_cycle import update_cycle
from .update_stage import update_stage


async def create_cycle(params: dict, context) -> SkillResult:
    """执行建茬口操作。"""
    crop_name = params.get("crop_name")
    if not crop_name or not isinstance(crop_name, str) or not crop_name.strip():
        return SkillResult(
            status=ResultStatus.FAILED,
            reply="建茬口失败：请提供作物名称。",
        )

    crop_name = crop_name.strip()
    season = params.get("season") or _current_season()
    start_date = _parse_date(params.get("start_date"))
    field_name = params.get("field_name")
    farm_id, context_error = require_farm_context(context, "建茬口")
    if context_error:
        return context_error

    db = SessionLocal()
    try:
        template = crop_service.find_template_by_name(db, crop_name, farm_id)
        if not template:
            return SkillResult(
                status=ResultStatus.NEED_CLARIFY,
                reply=f"系统还没有{crop_name}模板，要帮你创建一个吗？",
            )

        cycle_name = f"{season}{crop_name}"
        cycle_create = CropCycleCreate(
            name=cycle_name,
            crop_template_id=template.id,
            start_date=start_date,
            field_name=field_name,
        )
        created = cycle_service.create_crop_cycle(db, cycle_create, farm_id=farm_id)

        reply = _format_create_reply(created)
        return SkillResult(status=ResultStatus.SUCCESS, reply=reply)
    except Exception as exc:
        return SkillResult(
            status=ResultStatus.FAILED,
            reply=f"建茬口失败：{exc}",
        )
    finally:
        db.close()


async def delete_cycle(params: dict, context) -> SkillResult:
    """执行删除茬口操作。"""
    farm_id, context_error = require_farm_context(context, "删除茬口")
    if context_error:
        return context_error
    cycle_id = params.get("cycle_id")
    if not cycle_id:
        return SkillResult(
            status=ResultStatus.NEED_CLARIFY, reply="删除茬口需要 cycle_id。"
        )
    db = SessionLocal()
    try:
        cycle_service.delete_crop_cycle(db, int(cycle_id), farm_id)
        return SkillResult(
            status=ResultStatus.SUCCESS, reply=f"已删除茬口 #{cycle_id}。"
        )
    except Exception as exc:
        return SkillResult(status=ResultStatus.FAILED, reply=f"删除茬口失败：{exc}")
    finally:
        db.close()


async def query_cycles(params: dict, context) -> SkillResult:
    """执行茬口列表查询。"""
    farm_id, context_error = require_farm_context(context, "查询茬口列表")
    if context_error:
        return context_error
    db = SessionLocal()
    try:
        limit = int(params.get("limit") or 100)
        status = params.get("status")
        cycles = cycle_service.get_crop_cycles(db, farm_id=farm_id, limit=limit)
        if status:
            cycles = [cycle for cycle in cycles if cycle.status == status]
        if not cycles:
            return SkillResult(status=ResultStatus.SUCCESS, reply="暂无茬口。")

        lines = ["茬口列表："]
        for cycle in cycles:
            lines.append(_format_cycle(cycle))
        return SkillResult(status=ResultStatus.SUCCESS, reply="\n".join(lines))
    except Exception as exc:
        return SkillResult(status=ResultStatus.FAILED, reply=f"查询茬口列表失败：{exc}")
    finally:
        db.close()


async def query_cycle_info(params: dict, context) -> SkillResult:
    """执行茬口详情查询。"""
    cycle_id = params.get("cycle_id")
    farm_id, context_error = require_farm_context(context, "查询茬口")
    if context_error:
        return context_error
    db = SessionLocal()
    try:
        if cycle_id is None:
            summary = await farm_context_service.build_summary(db, farm_id=farm_id)
            reply = "未指定茬口 ID，已先返回当前农场状态：\n" + summary
            return SkillResult(status=ResultStatus.SUCCESS, reply=reply)

        cycle = (
            db.query(CropCycle)
            .filter(CropCycle.id == cycle_id, CropCycle.farm_id == farm_id)
            .first()
        )
        if not cycle:
            return SkillResult(
                status=ResultStatus.SUCCESS,
                reply=f"未找到 ID 为 {cycle_id} 的种植周期。",
            )

        lines = [
            f"茬口：{cycle.name}",
            f"开始日期：{cycle.start_date}",
            f"地块：{cycle.field_name or '未指定'}",
            f"状态：{cycle.status}",
            "阶段安排：",
        ]
        for stage in sorted(cycle.stages, key=lambda s: s.order_index):
            current_marker = " [当前]" if stage.is_current else ""
            lines.append(
                f"  {stage.name}{current_marker}: "
                f"{stage.start_date} ~ {stage.end_date} "
                f"({stage.duration_days}天) "
                f"关键任务：{stage.key_tasks or '无'}"
            )

        return SkillResult(status=ResultStatus.SUCCESS, reply="\n".join(lines))
    finally:
        db.close()


class ManageCropCycleSkill(Skill):
    """统一茬口业务能力 Skill。"""

    def name(self) -> str:
        return "manage_crop_cycle"

    def description(self) -> str:
        return (
            "管理农场种植茬口。通过 operation 选择 create_cycle、query_cycles、"
            "query_cycle_info、update_cycle、update_stage 或 delete_cycle，支持"
            "创建种植周期、查询列表和详情、调整日期阶段状态，以及删除茬口。"
        )

    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "operation": {
                    "type": "string",
                    "description": (
                        "操作类型：create_cycle、query_cycles、query_cycle_info、"
                        "update_cycle、update_stage、delete_cycle"
                    ),
                    "enum": [
                        "create_cycle",
                        "query_cycles",
                        "query_cycle_info",
                        "update_cycle",
                        "update_stage",
                        "delete_cycle",
                    ],
                },
                "cycle_id": {"type": "integer", "description": "茬口 ID。"},
                "crop_name": {
                    "type": "string",
                    "description": "作物名称，如玉米、辣椒、西瓜。",
                },
                "cycle_name": {
                    "type": "string",
                    "description": "茬口名称，如夏季玉米，用于定位已有茬口。",
                },
                "season": {"type": "string", "description": "季节，如春季、秋季。"},
                "start_date": {
                    "type": "string",
                    "description": "开始日期 YYYY-MM-DD。",
                },
                "field_name": {"type": "string", "description": "地块名称。"},
                "name": {"type": "string", "description": "新的茬口名称。"},
                "area": {"type": "number", "description": "面积，亩。"},
                "status": {
                    "type": "string",
                    "description": "状态 active、planned 或 finished。",
                },
                "status_filter": {
                    "type": "string",
                    "description": "列表查询状态过滤 active、planned 或 finished。",
                },
                "current_stage": {
                    "type": "string",
                    "description": "当前阶段名称。",
                },
                "stage_name": {
                    "type": "string",
                    "description": "目标阶段名称，兼容旧 update_crop_stage 参数。",
                },
                "stage": {"type": "string", "description": "当前阶段名称别名。"},
                "note": {"type": "string", "description": "批次备注。"},
                "batch_note": {"type": "string", "description": "批次备注。"},
                "current_cycle_id": {
                    "type": "integer",
                    "description": "上下文中的当前茬口 ID。",
                },
                "context_cycle_id": {
                    "type": "integer",
                    "description": "上下文补齐的茬口 ID。",
                },
                "limit": {"type": "integer", "description": "列表返回数量。"},
            },
            "required": ["operation"],
        }

    def metadata(self) -> dict:
        return {
            "permission_level": SkillPermissionLevel.READ,
            "risk_level": SkillRiskLevel.LOW,
            "domain": "crop",
            "capability": "manage_crop_cycle",
            "context_dependencies": [
                "farm",
                "active_cycles",
                "crop_cycles",
                "crop_templates",
            ],
            "cache_invalidation": ["crop_cycle", "get_farm_status"],
            "confirmation_schema": {
                "target_fields": ["cycle_id", "cycle_name", "crop_name"],
                "changed_fields": ["operation", "start_date", "deleted"],
                "inferred_fields": ["crop_name", "cycle_name", "current_context"],
                "editable_fields": [
                    "operation",
                    "cycle_id",
                    "cycle_name",
                    "crop_name",
                    "start_date",
                    "season",
                    "name",
                    "area",
                    "status",
                    "current_stage",
                    "note",
                ],
                "risk_notes": [
                    "修改开始日期会同步重算该茬口所有阶段起止日期。",
                    "删除茬口会级联删除阶段、农事日志、成本记录和种植单元。",
                ],
            },
            "evaluation_tags": ["crop_cycle", "crop", "production"],
        }

    async def execute(self, params: dict, context) -> SkillResult:
        operation = str(params.get("operation") or "").strip()
        handlers = {
            "create_cycle": create_cycle,
            "query_cycles": query_cycles,
            "query_cycle_info": query_cycle_info,
            "update_cycle": update_cycle,
            "update_stage": update_stage,
            "delete_cycle": delete_cycle,
        }
        handler = handlers.get(operation)
        if handler is None:
            return SkillResult(
                status=ResultStatus.NEED_CLARIFY,
                reply="请说明要新建、查询列表、查看详情、修改还是删除茬口。",
            )
        return await handler(params, context)


def _current_season() -> str:
    """根据当前月份推算季节。"""
    month = date.today().month
    if 3 <= month <= 5:
        return "春季"
    if 6 <= month <= 8:
        return "夏季"
    if 9 <= month <= 11:
        return "秋季"
    return "冬季"


def _parse_date(date_str: str | None) -> date:
    """解析日期字符串，无效时回退到今天。"""
    if not date_str:
        return date.today()
    try:
        return date.fromisoformat(date_str)
    except (ValueError, TypeError):
        return date.today()


def _format_date_m_d(date_val) -> str:
    """将 date 对象或字符串转为 M/D 格式。"""
    if isinstance(date_val, str):
        parts = date_val.split("-")
        return f"{int(parts[1])}/{int(parts[2])}"
    if isinstance(date_val, date):
        return f"{date_val.month}/{date_val.day}"
    return str(date_val)


def _format_create_reply(cycle) -> str:
    """格式化建茬口成功回复。"""
    sorted_stages = sorted(cycle.stages, key=lambda s: s.order_index)
    stage_lines = [
        f"{i + 1}. {s.name}（{_format_date_m_d(s.start_date)} ~ "
        f"{_format_date_m_d(s.end_date)}，{s.duration_days}天）"
        for i, s in enumerate(sorted_stages)
    ]
    stages_text = "\n".join(stage_lines)
    return f"✅ 茬口「{cycle.name}」已创建！\n\n📋 **阶段规划**\n{stages_text}"


def _format_cycle(cycle) -> str:
    template_name = getattr(getattr(cycle, "crop_template", None), "name", "未知作物")
    current = next((stage for stage in cycle.stages if stage.is_current), None)
    stage_text = current.name if current else "未知阶段"
    area_text = f"，{cycle.total_area_mu}亩" if cycle.total_area_mu is not None else ""
    field_text = f"，地块：{cycle.field_name}" if cycle.field_name else ""
    season_text = f"，{cycle.season}" if cycle.season else ""
    return (
        f"- #{cycle.id} {cycle.name}（{template_name}，{cycle.status}，"
        f"{stage_text}，开始 {cycle.start_date}{season_text}{area_text}{field_text}）"
    )


__all__ = [
    "ManageCropCycleSkill",
    "create_cycle",
    "delete_cycle",
    "query_cycle_info",
    "query_cycles",
    "update_cycle",
    "update_stage",
]
