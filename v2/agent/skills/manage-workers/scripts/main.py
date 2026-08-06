"""manage_workers skill.

管理农场工人档案的查询/创建/更新/删除。对应业务侧 manage_workers MCP tool，
该 tool 接受 operation 参数路由到 query / create / update / delete。

风险等级随 operation 变化：
  - query                        → read
  - create/update/delete         → write_confirm

react.py 在执行前用 dynamic_risk_level() 取实际风险。
"""
from __future__ import annotations

from typing import Any

from agent.skills.base import Skill, SkillResult
from agent.skills.context import SkillContext


class ManageWorkersSkill(Skill):
    """管理农场工人档案（查询/创建/更新/删除）。"""

    kind = "mcp"
    mcp_tool = "manage_workers"

    @property
    def name(self) -> str:
        return "manage_workers"

    @property
    def description(self) -> str:
        return (
            "管理农场工人档案，支持 query/create/update/delete 操作。\n"
            "- query: 查询工人列表（read，active_only 可选）\n"
            "- create: 添加工人（[RISK: write_confirm]，需 name，同名幂等）\n"
            "- update: 更新工人信息（[RISK: write_confirm]，需 worker_id）\n"
            "- delete: 停用工人档案（[RISK: write_confirm]，保留历史用工）"
        )

    @property
    def risk_level(self) -> str:
        # 默认返回 read（对应 query）；实际风险由 dynamic_risk_level 计算。
        return "read"

    def dynamic_risk_level(self, params: dict[str, Any]) -> str:
        """根据 operation 参数返回实际风险等级。"""
        op = (params.get("operation") or "").lower()
        if op in ("create", "update", "delete"):
            return "write_confirm"
        return "read"  # query 或未知

    @property
    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "operation": {
                    "type": "string",
                    "enum": ["query", "create", "update", "delete"],
                    "description": "操作类型：query=查询，create=添加，update=更新，delete=停用",
                },
                "worker_id": {
                    "type": "integer",
                    "description": "工人 ID（update/delete 必填）",
                },
                "name": {
                    "type": "string",
                    "description": "工人姓名（create 必填，update 可选）",
                },
                "phone": {
                    "type": "string",
                    "description": "联系电话（create/update 可选）",
                },
                "default_pay_type": {
                    "type": "string",
                    "description": "默认计酬方式：daily/monthly/hourly（create/update 可选）",
                },
                "default_unit_price": {
                    "type": "number",
                    "description": "默认单价（create/update 可选）",
                },
                "note": {
                    "type": "string",
                    "description": "备注（create/update 可选）",
                },
                "status": {
                    "type": "string",
                    "description": "状态（update 可选）",
                },
                "active_only": {
                    "type": "boolean",
                    "description": "仅查询在职工人（query 可选，默认 true）",
                },
            },
            "required": ["operation"],
        }

    async def execute(self, params: dict[str, Any], ctx: SkillContext) -> SkillResult:
        """调用 business.manage_workers MCP tool。

        业务侧该 tool 会根据 operation 路由到对应的查询/添加/更新/停用逻辑。
        """
        result = await ctx.business_client.call_tool(self.mcp_tool, params)
        return SkillResult(data=result)


skill = ManageWorkersSkill()
