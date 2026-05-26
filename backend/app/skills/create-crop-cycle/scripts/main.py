"""建茬口 Skill — 对话式创建种植茬口。"""

from datetime import date

from skillify.models.schemas import ResultStatus, SkillResult
from skillify.skills.base import Skill

from app.core.database import SessionLocal
from app.schemas.cycle import CropCycleCreate
from app.services import crop_service, cycle_service


class CreateCropCycleSkill(Skill):
    """创建种植茬口的 Skill。

    Agent 通过对话提取作物名称和季节后，查找模板并创建茬口。
    """

    def name(self) -> str:
        return "create_crop_cycle"

    def description(self) -> str:
        return (
            "创建一个新的种植茬口。当用户说建茬口、种什么、"
            "开始种某作物时使用。"
            "触发词: 建茬口、种、开始种"
        )

    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "crop_name": {
                    "type": "string",
                    "description": "作物名称，如'辣椒'、'西瓜'",
                },
                "season": {
                    "type": "string",
                    "description": "季节，如'春季'、'秋季'，默认当前季节",
                },
                "start_date": {
                    "type": "string",
                    "description": "开始日期 YYYY-MM-DD，默认今天",
                },
                "field_name": {
                    "type": "string",
                    "description": "地块名称（可选）",
                },
            },
            "required": ["crop_name"],
        }

    async def execute(self, params: dict, context) -> SkillResult:
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
        farm_id = getattr(context, "farm_id", 1) or 1

        db = SessionLocal()
        try:
            # 1. 模糊搜索模板
            template = crop_service.find_template_by_name(db, crop_name, farm_id)
            if not template:
                return SkillResult(
                    status=ResultStatus.NEED_CLARIFY,
                    reply=f"系统还没有{crop_name}模板，要帮你创建一个吗？",
                )

            # 2. 构造茬口数据并创建
            cycle_name = f"{season}{crop_name}"
            cycle_create = CropCycleCreate(
                name=cycle_name,
                crop_template_id=template.id,
                start_date=start_date,
                field_name=field_name,
            )
            created = cycle_service.create_crop_cycle(db, cycle_create, farm_id=farm_id)

            # 3. 格式化回复
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


def _format_reply(cycle) -> str:
    """格式化成功回复消息，包含茬口名称和阶段列表。"""
    stage_lines = [
        f"  {s.name}（{s.start_date} ~ {s.end_date}，{s.duration_days}天）"
        for s in sorted(cycle.stages, key=lambda s: s.order_index)
    ]
    stages_text = "\n".join(stage_lines)
    return (
        f"已建茬口「{cycle.name}」，"
        f"开始日期 {cycle.start_date}\n阶段规划：\n{stages_text}"
    )
