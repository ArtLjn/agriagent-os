"""还赊账 Skill — 对话式结清欠款记录。"""

from decimal import Decimal

from skillify.models.schemas import ResultStatus, SkillResult
from skillify.skills.base import Skill

from app.agent.skills.context import require_farm_context
from app.core.database import SessionLocal
from app.services import debt_service


class SettleDebtSkill(Skill):
    """还赊账 Skill。

    Agent 通过对话提取还款参数后调用此 Skill 结清赊账记录。
    支持部分还款和全额还清两种模式。
    """

    def name(self) -> str:
        return "settle_debt"

    def description(self) -> str:
        return (
            "还赊账、结清欠款。当用户说还钱、还账、还款、清账、"
            "还了老王多少钱、把欠的账结了时，调用此工具。"
            "需要提供债权人名称，可选提供还款金额。"
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

        farm_id, context_error = require_farm_context(context, "还款")
        if context_error:
            return context_error

        db = SessionLocal()
        try:
            return self._do_settle(
                db, farm_id, counterparty, amount, params.get("note")
            )
        except ValueError as exc:
            return SkillResult(
                status=ResultStatus.FAILED,
                reply=f"还款失败：{exc}",
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
        settlement_amount = None if amount is None else Decimal(str(amount))
        updated = debt_service.settle_debt(
            db,
            farm_id=farm_id,
            counterparty=counterparty,
            amount=settlement_amount,
            note=note,
        )

        return SkillResult(
            status=ResultStatus.SUCCESS,
            reply=self._format_reply(updated, counterparty),
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
        try:
            normalized = Decimal(str(amount))
        except Exception:
            normalized = None
        if (
            normalized is None
            or not normalized.is_finite()
            or normalized <= 0
        ):
            return SkillResult(
                status=ResultStatus.FAILED,
                reply="还款失败：金额无效，请提供大于0的金额。",
            )
        return None

    @staticmethod
    def _format_reply(record, counterparty: str) -> str:
        """格式化成功回复消息。"""
        settled_amount = getattr(record, "settled_amount", None)
        remaining_amount = getattr(record, "unsettled_amount", None)
        if remaining_amount is None and settled_amount is not None:
            remaining_amount = Decimal(str(record.amount)) - Decimal(
                str(settled_amount)
            )
        lines = [
            f"已更新{counterparty}账单",
            f"账单：{record.category}",
            f"已结：{settled_amount}元",
            f"剩余：{remaining_amount}元",
            f"settlement_status：{record.settlement_status}",
            f"日期 {record.record_date}",
        ]
        return "，".join(lines)
