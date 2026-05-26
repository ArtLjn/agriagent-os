"""还赊账 Skill — 对话式结清欠款记录。"""

from datetime import date
from decimal import Decimal

from skillify.models.schemas import ResultStatus, SkillResult
from skillify.skills.base import Skill

from app.core.database import SessionLocal
from app.models.cost import CostRecord
from app.schemas.cost import CostRecordCreate
from app.services.cost_service import create_record


class SettleDebtSkill(Skill):
    """还赊账 Skill。

    Agent 通过对话提取还款参数后调用此 Skill 结清赊账记录。
    支持部分还款和全额还清两种模式。
    """

    def name(self) -> str:
        return "settle_debt"

    def description(self) -> str:
        return (
            "还赊账，结清欠款。当用户说还钱、还账、还了XX时使用。"
            "触发词: 还钱、还账、还款、清账"
        )

    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "counterparty": {
                    "type": "string",
                    "description": "债权人名称/简称，如'老王'、'农资店'",
                },
                "amount": {
                    "type": "number",
                    "description": "还款金额，不传则全额还清",
                },
                "note": {
                    "type": "string",
                    "description": "备注",
                },
            },
            "required": ["counterparty"],
        }

    async def execute(self, params: dict, context) -> SkillResult:
        """执行还款操作。

        Args:
            params: Skill 参数，包含 counterparty、amount 等。
            context: Skill 执行上下文，包含 farm_id 等。

        Returns:
            SkillResult 包含成功/失败状态和回复消息。
        """
        counterparty = params.get("counterparty")
        amount = params.get("amount")

        # 校验必填参数
        error = self._validate_counterparty(counterparty)
        if error:
            return error

        # 校验金额（如果传了的话）
        if amount is not None:
            error = self._validate_amount(amount)
            if error:
                return error

        farm_id = getattr(context, "farm_id", 1) or 1

        db = SessionLocal()
        try:
            return self._do_settle(
                db, farm_id, counterparty, amount, params.get("note")
            )
        except Exception as exc:
            return SkillResult(
                status=ResultStatus.FAILED,
                reply=f"还款失败：{exc}",
            )
        finally:
            db.close()

    def _do_settle(
        self, db, farm_id: int, counterparty: str, amount, note: str | None
    ) -> SkillResult:
        """执行还款核心逻辑。

        Args:
            db: 数据库会话。
            farm_id: 农场 ID。
            counterparty: 债权人名称。
            amount: 还款金额，None 表示全额还清。
            note: 可选备注。

        Returns:
            SkillResult 包含成功/失败状态和回复消息。
        """
        # 查找赊账记录
        debt_records = self._find_debt_records(db, farm_id, counterparty)

        if not debt_records:
            return SkillResult(
                status=ResultStatus.FAILED,
                reply=f"没找到'{counterparty}'的赊账记录。",
            )

        # 计算还款金额
        if amount is None:
            # 全额还清：计算赊账总额
            total_debt = sum(
                (r.amount for r in debt_records),
                Decimal("0"),
            )
            settle_amount = total_debt
            settle_note = f"还{counterparty}（全额）"
        else:
            settle_amount = Decimal(str(amount))
            settle_note = f"还{counterparty}"

        # 追加用户备注
        if note:
            settle_note = f"{settle_note}，{note}"

        # 创建还款记录
        record_create = CostRecordCreate(
            record_type="income",
            category="还款",
            amount=settle_amount,
            record_date=date.today(),
            note=settle_note,
        )
        created = create_record(db, record_create, farm_id=farm_id)

        return SkillResult(
            status=ResultStatus.SUCCESS,
            reply=self._format_reply(created, counterparty),
        )

    @staticmethod
    def _find_debt_records(db, farm_id: int, counterparty: str) -> list:
        """查找指定债权人的赊账记录。

        Args:
            db: 数据库会话。
            farm_id: 农场 ID。
            counterparty: 债权人名称关键词。

        Returns:
            匹配的赊账 CostRecord 列表。
        """
        return (
            db.query(CostRecord)
            .filter(CostRecord.farm_id == farm_id)
            .filter(CostRecord.record_type == "cost")
            .filter(CostRecord.note.ilike(f"%{counterparty}%"))
            .all()
        )

    @staticmethod
    def _validate_counterparty(counterparty) -> SkillResult | None:
        """校验债权人参数，返回 None 表示通过。"""
        if (
            not counterparty
            or not isinstance(counterparty, str)
            or not counterparty.strip()
        ):
            return SkillResult(
                status=ResultStatus.FAILED,
                reply="还款失败：请提供债权人名称。",
            )
        return None

    @staticmethod
    def _validate_amount(amount) -> SkillResult | None:
        """校验还款金额，返回 None 表示通过。"""
        if not isinstance(amount, (int, float)) or amount <= 0:
            return SkillResult(
                status=ResultStatus.FAILED,
                reply="还款失败：金额无效，请提供大于0的金额。",
            )
        return None

    @staticmethod
    def _format_reply(record, counterparty: str) -> str:
        """格式化成功回复消息。"""
        lines = [
            f"已还款：还{counterparty} {record.amount}元",
            f"日期 {record.record_date}",
        ]
        if record.note:
            lines.append(f"备注：{record.note}")
        return "，".join(lines)
