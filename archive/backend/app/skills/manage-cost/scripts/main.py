"""成本域聚合 Skill。"""

from skillify.models.schemas import ResultStatus, SkillResult
from skillify.skills.base import Skill

from app.skills.metadata import SkillPermissionLevel, SkillRiskLevel

from .analytics import analyze_cost
from .debt import query_debt, settle_debt
from .records import create_record, delete_record
from .summary import query_summary


class ManageCostSkill(Skill):
    """统一成本域业务能力 Skill。"""

    def name(self) -> str:
        return "manage_cost"

    def description(self) -> str:
        return (
            "管理农场账务。通过 operation 选择 create_record、delete_record、"
            "query_summary、analyze_cost、query_debt 或 settle_debt，支持记账、"
            "删账、查账、趋势分析、欠款查询和赊账结清。"
        )

    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "operation": {
                    "type": "string",
                    "description": (
                        "操作类型：create_record、delete_record、query_summary、"
                        "analyze_cost、query_debt、settle_debt"
                    ),
                    "enum": [
                        "create_record",
                        "delete_record",
                        "query_summary",
                        "analyze_cost",
                        "query_debt",
                        "settle_debt",
                    ],
                },
                "amount": {"type": "number", "description": "金额。"},
                "category": {"type": "string", "description": "账务分类。"},
                "record_date": {
                    "type": "string",
                    "description": "记录日期 YYYY-MM-DD。",
                },
                "record_type": {
                    "type": "string",
                    "description": "cost(支出)或 income(收入)，默认 cost。",
                    "default": "cost",
                },
                "note": {"type": "string", "description": "备注。"},
                "record_subtype": {
                    "type": "string",
                    "description": "赊账或未收款时传 赊账。",
                },
                "counterparty": {
                    "type": "string",
                    "description": "赊账、欠款、还款或往来对象。",
                },
                "due_date": {
                    "type": "string",
                    "description": "约定还款或收款日期 YYYY-MM-DD。",
                },
                "record_id": {"type": "integer", "description": "账务记录 ID。"},
                "cycle_id": {"type": "integer", "description": "种植周期 ID。"},
                "date_from": {"type": "string", "description": "开始日期。"},
                "date_to": {"type": "string", "description": "结束日期。"},
                "group_by": {
                    "type": "string",
                    "description": "none、category 或 month。",
                    "default": "none",
                },
                "compare_period": {
                    "type": "string",
                    "description": "none、last_month 或 last_year。",
                    "default": "none",
                },
                "direction": {
                    "type": "string",
                    "description": "payable、receivable 或 all。",
                    "enum": ["payable", "receivable", "all"],
                    "default": "payable",
                },
                "scope": {
                    "type": "string",
                    "description": "debt_only 或 total_payable。",
                    "enum": ["debt_only", "total_payable"],
                    "default": "debt_only",
                },
                "limit": {"type": "integer", "description": "最多返回对象数。"},
            },
            "required": ["operation"],
        }

    def metadata(self) -> dict:
        return {
            "permission_level": SkillPermissionLevel.READ,
            "risk_level": SkillRiskLevel.LOW,
            "domain": "finance",
            "capability": "manage_cost",
            "context_dependencies": ["farm", "cost_records", "cost_categories"],
            "evaluation_tags": ["cost", "finance", "debt"],
        }

    async def execute(self, params: dict, context) -> SkillResult:
        operation = str(params.get("operation") or "").strip()
        handlers = {
            "create_record": create_record,
            "delete_record": delete_record,
            "query_summary": query_summary,
            "analyze_cost": analyze_cost,
            "query_debt": query_debt,
            "settle_debt": settle_debt,
        }
        handler = handlers.get(operation)
        if handler is None:
            return SkillResult(
                status=ResultStatus.NEED_CLARIFY,
                reply="请说明要记账、查账、分析、查欠款、还款还是删除账务记录。",
            )
        return await handler(params, context)
