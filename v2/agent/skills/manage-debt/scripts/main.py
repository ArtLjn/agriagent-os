"""manage_debt skill.

管理农场赊账的查询/创建/还款/汇总。对应业务侧 manage_debt MCP tool，
该 tool 接受 operation 参数路由到 query / create / repay / summary。

风险等级随 operation 变化：
  - query/summary   → read
  - create/repay    → write_confirm

react.py 在执行前用 dynamic_risk_level() 取实际风险。
"""
from __future__ import annotations

from typing import Any

from agent.skills.base import Skill, SkillResult
from agent.skills.context import SkillContext


class ManageDebtSkill(Skill):
    """管理农场赊账（查询/创建/还款/汇总）。"""

    kind = "mcp"
    mcp_tool = "manage_debt"

    @property
    def name(self) -> str:
        return "manage_debt"

    @property
    def description(self) -> str:
        return (
            "管理农场赊账，支持 query/create/repay/summary 操作。\n"
            "- query: 查询未结清赊账记录（read，可按 counterparty 过滤）\n"
            "- create: 记录赊账（[RISK: write_confirm]，需 record_type, amount, record_date）\n"
            "- repay: 还款结算（[RISK: write_confirm]，需 counterparty）\n"
            "- summary: 按交易对手汇总债务（read）"
        )

    @property
    def risk_level(self) -> str:
        # 默认返回 read（对应 query）；实际风险由 dynamic_risk_level 计算。
        return "read"

    def dynamic_risk_level(self, params: dict[str, Any]) -> str:
        """根据 operation 参数返回实际风险等级。"""
        op = (params.get("operation") or "").lower()
        if op in ("create", "repay"):
            return "write_confirm"
        return "read"  # query/summary 或未知

    @property
    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "operation": {
                    "type": "string",
                    "enum": ["query", "create", "repay", "summary"],
                    "description": "操作类型：query=查询未结清，create=记录赊账，"
                                   "repay=还款结算，summary=按交易对手汇总",
                },
                "record_type": {
                    "type": "string",
                    "description": "赊账类型：debt_payable=应付 / debt_receivable=应收（create 必填）",
                },
                "amount": {
                    "type": "number",
                    "description": "金额（create/repay 必填）",
                },
                "record_date": {
                    "type": "string",
                    "description": "YYYY-MM-DD 记账日期（create 必填）",
                },
                "counterparty": {
                    "type": "string",
                    "description": "交易对手（create/query/repay 可选过滤）",
                },
                "cycle_id": {
                    "type": "integer",
                    "description": "茬口 ID（create 可选关联）",
                },
                "note": {
                    "type": "string",
                    "description": "备注（create 可选）",
                },
                "skip": {
                    "type": "integer",
                    "description": "分页偏移（query，默认 0）",
                },
                "limit": {
                    "type": "integer",
                    "description": "分页大小（query，默认 20）",
                },
            },
            "required": ["operation"],
        }

    async def execute(self, params: dict[str, Any], ctx: SkillContext) -> SkillResult:
        """调用 business.manage_debt MCP tool。

        业务侧该 tool 会根据 operation 路由到对应的查询/记录/还款/汇总逻辑。
        """
        result = await ctx.business_client.call_tool(self.mcp_tool, params)
        return SkillResult(data=result)


skill = ManageDebtSkill()
