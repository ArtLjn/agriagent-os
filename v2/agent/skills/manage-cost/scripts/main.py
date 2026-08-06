"""manage_cost skill.

管理农场财务记账的查询/创建/汇总/利润/删除/分类。对应业务侧 manage_cost MCP tool，
该 tool 接受 operation 参数路由到 query / create / summary / profit / delete /
categories。

风险等级随 operation 变化：
  - query/summary/profit/categories → read
  - create                          → write_confirm
  - delete                          → write_high

react.py 在执行前用 dynamic_risk_level() 取实际风险。
"""
from __future__ import annotations

from typing import Any

from agent.skills.base import Skill, SkillResult
from agent.skills.context import SkillContext


class ManageCostSkill(Skill):
    """管理农场财务记账（查询/创建/汇总/利润/删除/分类）。"""

    kind = "mcp"
    mcp_tool = "manage_cost"

    @property
    def name(self) -> str:
        return "manage_cost"

    @property
    def description(self) -> str:
        return (
            "管理农场财务记账，支持 query/create/summary/profit/delete/categories 操作。\n"
            "- query: 查询收支记录（read，可按 cycle_id 和 category 过滤）\n"
            "- create: 记账（[RISK: write_confirm]，record_type=cost/income，需 category, amount, record_date）\n"
            "- summary: 年度收支汇总（read，需 year）\n"
            "- profit: 茬口利润分析（read，需 cycle_id）\n"
            "- delete: 删除记录（[RISK: write_high]，需 record_id）\n"
            "- categories: 查询成本分类列表（read）"
        )

    @property
    def risk_level(self) -> str:
        # 默认返回 read（对应 query）；实际风险由 dynamic_risk_level 计算。
        return "read"

    def dynamic_risk_level(self, params: dict[str, Any]) -> str:
        """根据 operation 参数返回实际风险等级。"""
        op = (params.get("operation") or "").lower()
        if op == "create":
            return "write_confirm"
        if op == "delete":
            return "write_high"
        return "read"  # query/summary/profit/categories 或未知

    @property
    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "operation": {
                    "type": "string",
                    "enum": ["query", "create", "summary", "profit", "delete", "categories"],
                    "description": "操作类型：query=查询记录，create=记账，summary=年度汇总，"
                                   "profit=茬口利润，delete=删除记录，categories=成本分类",
                },
                "record_type": {
                    "type": "string",
                    "description": "记录类型：cost=支出 / income=收入（create 必填）",
                },
                "category": {
                    "type": "string",
                    "description": "成本分类（create 必填，query 可选过滤）",
                },
                "amount": {
                    "type": "number",
                    "description": "金额（create 必填）",
                },
                "record_date": {
                    "type": "string",
                    "description": "YYYY-MM-DD 记账日期（create 必填）",
                },
                "cycle_id": {
                    "type": "integer",
                    "description": "茬口 ID（query/profit 可选过滤，create 可选关联）",
                },
                "note": {
                    "type": "string",
                    "description": "备注（create 可选）",
                },
                "counterparty": {
                    "type": "string",
                    "description": "交易对手（create 可选）",
                },
                "record_id": {
                    "type": "integer",
                    "description": "记录 ID（delete 必填）",
                },
                "year": {
                    "type": "integer",
                    "description": "年份（summary 必填）",
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
        """调用 business.manage_cost MCP tool。

        业务侧该 tool 会根据 operation 路由到对应的查询/记账/汇总/利润/删除/分类逻辑。
        """
        result = await ctx.business_client.call_tool(self.mcp_tool, params)
        return SkillResult(data=result)


skill = ManageCostSkill()
