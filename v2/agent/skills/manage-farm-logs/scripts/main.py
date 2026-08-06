"""manage-farm-logs skill.

统一管理农事日志的查询/创建/更新/删除。对应业务侧 manage_farm_logs MCP tool，
该 tool 接受 operation 参数路由到 query / create / update / delete。

风险等级随 operation 变化：
  - query  → read
  - create → write_confirm
  - update → write_confirm
  - delete → write_high

react.py 在执行前用 dynamic_risk_level() 取实际风险。
"""
from __future__ import annotations

from typing import Any

from agent.skills.base import Skill, SkillResult
from agent.skills.context import SkillContext


class ManageFarmLogsSkill(Skill):
    """管理农事日志（查询/创建/更新/删除）。"""

    kind = "mcp"
    mcp_tool = "manage_farm_logs"

    @property
    def name(self) -> str:
        return "manage_farm_logs"

    @property
    def description(self) -> str:
        return (
            "管理农事日志，支持 query/create/update/delete 四种 operation。\n"
            "- query: 查询最近农事（read，可按 cycle_id 和 days 过滤）\n"
            "- create: 创建农事记录（[RISK: write_confirm]，cycle_id 和 operation_type 必填）\n"
            "- update: 更新农事记录（[RISK: write_confirm]，log_id 必填，其余可选）\n"
            "- delete: 删除农事记录（[RISK: write_high]，log_id 必填，不可恢复）\n"
            "缺 cycle_id 可先调 get_farm_status；缺 log_id 可先调 query。"
        )

    @property
    def risk_level(self) -> str:
        # 默认返回 read（对应 query）；实际风险由 dynamic_risk_level 计算。
        return "read"

    def dynamic_risk_level(self, params: dict[str, Any]) -> str:
        """根据 operation 参数返回实际风险等级。"""
        op = (params.get("operation") or "").lower()
        if op in ("create", "update"):
            return "write_confirm"
        if op == "delete":
            return "write_high"
        return "read"  # query 或未知

    @property
    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "operation": {
                    "type": "string",
                    "enum": ["query", "create", "update", "delete"],
                    "description": "操作类型：query=查询，create=创建，update=更新，delete=删除",
                },
                "cycle_id": {
                    "type": "integer",
                    "description": "茬口 ID（create 必填，query 可选过滤，update 可选更新）",
                },
                "operation_type": {
                    "type": "string",
                    'description': '操作类型，如"浇水"、"施肥"（create 必填，update 可选）',
                },
                "operation_date": {
                    "type": "string",
                    "description": "YYYY-MM-DD（create/update 不传默认今天）",
                },
                "note": {"type": "string", "description": "备注（create/update 可选）"},
                "worker_names": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "参与工人姓名列表（update 时全量替换）",
                },
                "log_id": {
                    "type": "integer",
                    "description": "农事记录 ID（update/delete 必填）",
                },
                "days": {"type": "integer", "description": "查询最近 N 天，默认 7"},
                "limit": {"type": "integer", "description": "查询返回最大条数，默认 20"},
            },
            "required": ["operation"],
        }

    async def execute(self, params: dict[str, Any], ctx: SkillContext) -> SkillResult:
        """调用 business.manage_farm_logs MCP tool。

        业务侧该 tool 会根据 operation 路由到对应的查询/创建/更新/删除逻辑。
        """
        result = await ctx.business_client.call_tool(self.mcp_tool, params)
        return SkillResult(data=result)


skill = ManageFarmLogsSkill()
