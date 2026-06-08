"""记账 Skill — 对话式创建成本/收入记录。"""

from datetime import date

from skillify.models.schemas import ResultStatus, SkillResult
from skillify.skills.base import Skill

from app.agent.skills.context import require_farm_context
from app.core.date_context import get_request_date
from app.core.database import SessionLocal
from app.models.cost_category import CostCategory
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
            "记录一笔农场支出或收入。当用户说记一笔、买了化肥200块、"
            "卖了西瓜赚了5000、花了多少钱、赊账记账时，调用此工具。"
            "需要提供金额和分类，可选提供日期、类型、备注。"
        )

    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "amount": {
                    "type": "number",
                    "description": "金额，必须大于0且不超过10000000。w/万表示乘以10000，超过上限时不要调用本工具，应向用户确认。",
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
                    "description": "备注，如'买苹果种子，向王秉着赊账'",
                },
                "record_subtype": {
                    "type": "string",
                    "description": "记录子类型。赊账或未收款时传'赊账'。",
                },
                "counterparty": {
                    "type": "string",
                    "description": "赊账或未收款对象，如'王秉着'、'老王农资店'。",
                },
                "due_date": {
                    "type": "string",
                    "description": "约定还款或收款日期 YYYY-MM-DD，可选。",
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
        if isinstance(amount, str):
            try:
                amount = float(amount)
            except (ValueError, TypeError):
                pass
        category = params.get("category")

        # 校验必填参数
        error = self._validate_required(amount, category)
        if error:
            return error
        route_error = self._guard_wrong_route(category, params.get("note"))
        if route_error:
            return route_error

        # 解析可选参数
        record_date = self._parse_date(params.get("record_date"))
        record_type = params.get("record_type", "cost")
        note = params.get("note")
        record_subtype = self._normalize_record_subtype(params.get("record_subtype"))
        counterparty = self._clean_optional_text(params.get("counterparty"))
        due_date = self._parse_optional_date(params.get("due_date"))
        farm_id, context_error = require_farm_context(context, "记账")
        if context_error:
            return context_error

        # 构造 Schema 并创建记录
        record_create = CostRecordCreate(
            record_type=record_type,
            category=category,
            amount=amount,
            record_date=record_date,
            note=note,
            record_subtype=record_subtype,
            counterparty=counterparty,
            due_date=due_date,
        )

        db = SessionLocal()
        try:
            category_error = self._validate_category_choice(
                db, farm_id, category, record_type
            )
            if category_error:
                return category_error
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
    def _guard_wrong_route(category, note) -> SkillResult | None:
        """拦截明显应该走还账 Skill 的错误路由。"""
        category_text = str(category or "").strip()
        note_text = str(note or "").strip()
        if category_text == "还款":
            return SkillResult(
                status=ResultStatus.NEED_CLARIFY,
                reply=(
                    "这像是在还赊账，不应创建普通收入/还款记录。"
                    "请改用 settle_debt，并提供还款对象和金额。"
                ),
            )
        if note_text.startswith(("还", "结清", "清账")) and category_text in {
            "还款",
            "其他",
        }:
            return SkillResult(
                status=ResultStatus.NEED_CLARIFY,
                reply="这像是在还账，请使用 settle_debt 处理原赊账记录。",
            )
        return None

    @staticmethod
    def _validate_category_choice(
        db, farm_id: int, category: str, record_type: str
    ) -> SkillResult | None:
        """分类存在时校验分类，避免 Agent 用“其他”糊弄必填项。"""
        category_count = db.query(CostCategory).filter_by(farm_id=farm_id).count()
        if category_count == 0:
            return None
        category_exists = (
            db.query(CostCategory)
            .filter(
                CostCategory.farm_id == farm_id,
                CostCategory.name == category,
                CostCategory.type == record_type,
            )
            .first()
        )
        if category == "其他" or category_exists is None:
            return SkillResult(
                status=ResultStatus.NEED_CLARIFY,
                reply=(
                    "记账分类不明确，请从已有分类中选择，"
                    "例如种子、化肥、农药、人工、水电、地租或销售。"
                ),
            )
        return None

    @staticmethod
    def _parse_date(date_str: str | None) -> date:
        """解析日期字符串，无效时回退到今天。"""
        if not date_str:
            return get_request_date()
        try:
            return date.fromisoformat(date_str)
        except (ValueError, TypeError):
            return get_request_date()

    @staticmethod
    def _parse_optional_date(date_str: str | None) -> date | None:
        """解析可选日期字符串，无效时忽略。"""
        if not date_str:
            return None
        try:
            return date.fromisoformat(date_str)
        except (ValueError, TypeError):
            return None

    @staticmethod
    def _normalize_record_subtype(value) -> str | None:
        """规范化账单子类型。"""
        if not value or not isinstance(value, str):
            return None
        if value.strip() in {"赊账", "欠款", "未结", "未收款", "应付", "应收"}:
            return "赊账"
        return value.strip()[:50] or None

    @staticmethod
    def _clean_optional_text(value) -> str | None:
        """清理可选文本字段。"""
        if not value or not isinstance(value, str):
            return None
        return value.strip()[:100] or None

    @staticmethod
    def _format_reply(record) -> str:
        """格式化成功回复消息。"""
        type_label = "收入" if record.record_type == "income" else "支出"
        lines = [f"💰 已记账：**{record.category}** {record.amount}元（{type_label}）"]
        if getattr(record, "record_subtype", None) == "赊账":
            counterparty = getattr(record, "counterparty", None)
            label = f"赊账：{counterparty}" if counterparty else "赊账"
            lines.append(f"🧾 {label}")
        if record.note:
            if "赊账" in record.note:
                lines.append(f"📝 {record.note}")
            else:
                lines.append(f"📝 备注：{record.note}")
        recorded_at = getattr(record, "recorded_at", None)
        if recorded_at:
            time_text = recorded_at.strftime("%Y-%m-%d %H:%M")
            lines.append(f"📅 {time_text}")
        else:
            lines.append(f"📅 {record.record_date}")
        return "\n".join(lines)
