"""记农事 Skill — 对话式记录农事操作。"""

from datetime import date

from skillify.models.schemas import ResultStatus, SkillResult
from skillify.skills.base import Skill

from app.core.database import SessionLocal
from app.models.cycle import CropCycle
from app.schemas.log import FarmLogCreate
from app.services import log_service


class LogFarmActivitySkill(Skill):
    """记录农事操作的 Skill。

    Agent 通过对话提取农事类型后，自动关联茬口并记录日志。
    """

    def name(self) -> str:
        return "log_farm_activity"

    def description(self) -> str:
        return (
            "记录一条农事操作。当用户说做了什么农活、浇了水、施了肥、"
            "打药时使用。触发词: 记农事、浇水、施肥、打药、干了啥"
        )

    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "operation_type": {
                    "type": "string",
                    "description": "农事操作类型，如'浇水'、'施肥'、'打药'",
                },
                "operation_date": {
                    "type": "string",
                    "description": "操作日期 YYYY-MM-DD，默认今天",
                },
                "note": {
                    "type": "string",
                    "description": "备注详情",
                },
                "cycle_id": {
                    "type": "integer",
                    "description": "关联的茬口ID（可选，不传则关联第一个活跃茬口）",
                },
            },
            "required": ["operation_type"],
        }

    async def execute(self, params: dict, context) -> SkillResult:
        """执行记农事操作。"""
        operation_type = params.get("operation_type")
        if (
            not operation_type
            or not isinstance(operation_type, str)
            or not operation_type.strip()
        ):
            return SkillResult(
                status=ResultStatus.FAILED,
                reply="记农事失败：请提供操作类型（如浇水、施肥、打药）。",
            )

        operation_type = operation_type.strip()
        operation_date = _parse_date(params.get("operation_date"))
        note = params.get("note")
        farm_id = getattr(context, "farm_id", 1) or 1

        db = SessionLocal()
        try:
            # 确定 cycle_id：显式传入 > 自动查询第一个活跃茬口
            cycle_id = params.get("cycle_id")
            if not cycle_id:
                cycle_id = _find_first_active_cycle(db, farm_id)
                if not cycle_id:
                    return SkillResult(
                        status=ResultStatus.NEED_CLARIFY,
                        reply="当前没有活跃的茬口，请先建一个茬口再来记录农事。",
                    )

            # 创建农事日志
            log_create = FarmLogCreate(
                cycle_id=cycle_id,
                operation_type=operation_type,
                operation_date=operation_date,
                note=note,
            )
            created = log_service.create_log(db, log_create, farm_id=farm_id)

            reply = _format_reply(created)
            return SkillResult(status=ResultStatus.SUCCESS, reply=reply)
        except Exception as exc:
            return SkillResult(
                status=ResultStatus.FAILED,
                reply=f"记农事失败：{exc}",
            )
        finally:
            db.close()


def _parse_date(date_str: str | None) -> date:
    """解析日期字符串，无效时回退到今天。"""
    if not date_str:
        return date.today()
    try:
        return date.fromisoformat(date_str)
    except (ValueError, TypeError):
        return date.today()


def _find_first_active_cycle(db, farm_id: int) -> int | None:
    """查询指定 farm 下第一个活跃茬口的 ID。"""
    cycle = (
        db.query(CropCycle)
        .filter(CropCycle.farm_id == farm_id, CropCycle.status == "active")
        .order_by(CropCycle.id)
        .first()
    )
    return cycle.id if cycle else None


def _format_reply(log) -> str:
    """格式化成功回复消息。"""
    parts = [f"已记录「{log.operation_type}」"]
    if log.operation_date:
        parts.append(f"日期 {log.operation_date}")
    if log.note:
        parts.append(f"备注: {log.note}")
    return "，".join(parts)
