"""manage_work_orders skill.

管理农事作业单的查询/详情/创建/更新/结算。对应业务侧 manage_work_orders MCP tool，
该 tool 接受 operation 参数路由到 query / detail / create / update / settle。

风险等级随 operation 变化：
  - query/detail      → read
  - create/update/settle → write_confirm

react.py 在执行前用 dynamic_risk_level() 取实际风险。
"""
from __future__ import annotations

from typing import Any

from agent.skills.base import Skill, SkillResult
from agent.skills.context import SkillContext


class ManageWorkOrdersSkill(Skill):
    """管理农事作业单（查询/详情/创建/更新/结算）。"""

    kind = "mcp"
    mcp_tool = "manage_work_orders"

    @property
    def name(self) -> str:
        return "manage_work_orders"

    @property
    def description(self) -> str:
        return (
            "管理农事作业单，支持 query/detail/create/update/settle 操作。\n"
            "- query: 查询作业单列表（read，可按 cycle_id 过滤）\n"
            "- detail: 查询作业单详情（read，需 work_order_id）\n"
            "- create: 创建作业单（[RISK: write_confirm]，需 operation_type, operation_date）\n"
            "- update: 更新作业单（[RISK: write_confirm]，需 work_order_id）\n"
            "- settle: 结算人工工资（[RISK: write_confirm]）"
        )

    @property
    def risk_level(self) -> str:
        # 默认返回 read（对应 query）；实际风险由 dynamic_risk_level 计算。
        return "read"

    def dynamic_risk_level(self, params: dict[str, Any]) -> str:
        """根据 operation 参数返回实际风险等级。"""
        op = (params.get("operation") or "").lower()
        if op in ("create", "update", "settle"):
            return "write_confirm"
        return "read"  # query/detail 或未知

    @property
    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "operation": {
                    "type": "string",
                    "enum": ["query", "detail", "create", "update", "settle"],
                    "description": "操作类型：query=列表，detail=详情，create=创建，"
                                   "update=更新，settle=结算人工工资",
                },
                "work_order_id": {
                    "type": "integer",
                    "description": "作业单 ID（detail/update 必填）",
                },
                "operation_type": {
                    "type": "string",
                    "description": "作业类型，如\"播种\"、\"采摘\"（create 必填，update 可选）",
                },
                "operation_date": {
                    "type": "string",
                    "description": "YYYY-MM-DD 作业日期（create 必填，update 可选）",
                },
                "cycle_id": {
                    "type": "integer",
                    "description": "茬口 ID（query 可选过滤，create 可选关联）",
                },
                "scope_type": {
                    "type": "string",
                    "description": "作业范围：cycle=茬口 / unit=单株（create 可选）",
                },
                "note": {
                    "type": "string",
                    "description": "备注（create/update 可选）",
                },
                "amount": {
                    "type": "number",
                    "description": "结算金额（settle 可选）",
                },
                "worker_name": {
                    "type": "string",
                    "description": "工人姓名（settle 可选过滤）",
                },
                "start_date": {
                    "type": "string",
                    "description": "YYYY-MM-DD 结算开始日期（settle 可选）",
                },
                "end_date": {
                    "type": "string",
                    "description": "YYYY-MM-DD 结算结束日期（settle 可选）",
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
        """调用 business.manage_work_orders MCP tool。

        业务侧该 tool 会根据 operation 路由到对应的查询/详情/创建/更新/结算逻辑。
        """
        result = await ctx.business_client.call_tool(self.mcp_tool, params)
        return SkillResult(data=result)


skill = ManageWorkOrdersSkill()
