"""记账 Skill — 对话式创建成本/收入记录。"""

from datetime import date

from skillify.models.schemas import ResultStatus, SkillResult
from skillify.skills.base import Skill

from app.core.database import SessionLocal
from app.schemas.cost import CostRecordCreate
from app.services.cost_service import create_record


class CreateCostRecordSkill(Skill):
    """创建成本或收入记录的 Skill。

    Agent 通过对话提取记账参数后调用此 Skill 直接创建记录。
    """

    def name(self) -> str:
        return "create_cost_record"

    def description(self) -> str:
        return (
            "创建一笔成本或收入记录。当用户提到买了什么东西花了多少钱、"
            "或者卖了什么赚了多少钱时使用。"
            "触发词: 记账、花了、买了、卖了、收入、支出"
        )

    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "amount": {
                    "type": "number",
                    "description": "金额，必须大于0",
                },
                "category": {
                    "type": "string",
                    "description": "分类，如'化肥'、'人工'、'大棚膜'",
                },
                "record_date": {
                    "type": "string",
                    "description": "记录日期 YYYY-MM-DD，默认今天",
                },
                "record_type": {
                    "type": "string",
                    "description": "cost(支出)或income(收入)，默认cost",
                },
                "note": {
                    "type": "string",
                    "description": "备注，如'赊账-农资店老王'",
                },
            },
            "required": ["amount", "category"],
        }

    async def execute(self, params: dict, context) -> SkillResult:
        """执行记账操作。

        Args:
            params: Skill 参数，包含 amount、category 等。
            context: Skill 执行上下文，包含 farm_id 等。

        Returns:
            SkillResult 包含成功/失败状态和回复消息。
        """
        amount = params.get("amount")
        category = params.get("category")

        # 校验必填参数
        error = self._validate_required(amount, category)
        if error:
            return error

        # 解析可选参数
        record_date = self._parse_date(params.get("record_date"))
        record_type = params.get("record_type", "cost")
        note = params.get("note")
        farm_id = getattr(context, "farm_id", 1) or 1

        # 构造 Schema 并创建记录
        record_create = CostRecordCreate(
            record_type=record_type,
            category=category,
            amount=amount,
            record_date=record_date,
            note=note,
        )

        db = SessionLocal()
        try:
            created = create_record(db, record_create, farm_id=farm_id)
            reply = self._format_reply(created)
            return SkillResult(status=ResultStatus.SUCCESS, reply=reply)
        except Exception as exc:
            return SkillResult(
                status=ResultStatus.FAILED,
                reply=f"记账失败：{exc}",
            )
        finally:
            db.close()

    @staticmethod
    def _validate_required(amount, category) -> SkillResult | None:
        """校验必填参数，返回 None 表示通过。"""
        if not amount or not isinstance(amount, (int, float)) or amount <= 0:
            return SkillResult(
                status=ResultStatus.FAILED,
                reply="记账失败：金额无效，请提供大于0的金额。",
            )
        if not category or not isinstance(category, str):
            return SkillResult(
                status=ResultStatus.FAILED,
                reply="记账失败：分类不能为空。",
            )
        return None

    @staticmethod
    def _parse_date(date_str: str | None) -> date:
        """解析日期字符串，无效时回退到今天。"""
        if not date_str:
            return date.today()
        try:
            return date.fromisoformat(date_str)
        except (ValueError, TypeError):
            return date.today()

    @staticmethod
    def _format_reply(record) -> str:
        """格式化成功回复消息。"""
        type_label = "收入" if record.record_type == "income" else "支出"
        payment = "赊账" if record.note and "赊账" in record.note else "现金"
        lines = [
            f"已记账：{record.category} {record.amount}元",
            f"（{payment}），{type_label}，日期 {record.record_date}",
        ]
        if record.note:
            lines.append(f"备注：{record.note}")
        return " ".join(lines)
