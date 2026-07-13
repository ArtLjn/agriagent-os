"""创建茬口 operation。"""

from datetime import date

from skillify.models.schemas import ResultStatus, SkillResult

from app.core.database import SessionLocal
from app.agent.skills.context import require_farm_context
from app.schemas.cycle import CropCycleCreate
from app.services import crop_service, cycle_service


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

        reply = _format_reply(created)
        return SkillResult(status=ResultStatus.SUCCESS, reply=reply)
    except Exception as exc:
        return SkillResult(
            status=ResultStatus.FAILED,
            reply=f"建茬口失败：{exc}",
        )
    finally:
        db.close()


def _current_season() -> str:
    """根据当前月份推算季节。"""
    month = date.today().month
    if 3 <= month <= 5:
        return "春季"
    elif 6 <= month <= 8:
        return "夏季"
    elif 9 <= month <= 11:
        return "秋季"
    else:
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


def _format_reply(cycle) -> str:
    """格式化成功回复，使用 emoji + 有序列表展示阶段。"""
    sorted_stages = sorted(cycle.stages, key=lambda s: s.order_index)
    stage_lines = [
        f"{i + 1}. {s.name}（{_format_date_m_d(s.start_date)} ~ "
        f"{_format_date_m_d(s.end_date)}，{s.duration_days}天）"
        for i, s in enumerate(sorted_stages)
    ]
    stages_text = "\n".join(stage_lines)
    return f"✅ 茬口「{cycle.name}」已创建！\n\n📋 **阶段规划**\n{stages_text}"
