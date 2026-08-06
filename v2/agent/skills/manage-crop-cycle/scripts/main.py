"""manage_crop_cycle skill.

管理种植茬口的查询/详情/创建/推进/更新/删除/模板。对应业务侧 manage_crop_cycle
MCP tool，该 tool 接受 operation 参数路由到 query / detail / create / advance /
update / delete / templates / system_templates。

风险等级随 operation 变化：
  - query/detail/templates/system_templates → read
  - create/advance/update                  → write_confirm
  - delete                                 → write_high

react.py 在执行前用 dynamic_risk_level() 取实际风险。
"""
from __future__ import annotations

from typing import Any

from agent.skills.base import Skill, SkillResult
from agent.skills.context import SkillContext


class ManageCropCycleSkill(Skill):
    """管理种植茬口（查询/详情/创建/推进/更新/删除/模板）。"""

    kind = "mcp"
    mcp_tool = "manage_crop_cycle"

    @property
    def name(self) -> str:
        return "manage_crop_cycle"

    @property
    def description(self) -> str:
        return (
            "管理种植茬口，支持 query/detail/create/advance/update/delete/templates/system_templates 操作。\n"
            "- query: 查询茬口列表（read）\n"
            "- detail: 查询茬口详情含阶段（read）\n"
            "- create: 创建茬口（[RISK: write_confirm]，需 name, crop_template_id, start_date）\n"
            "- advance: 推进茬口到下一阶段（[RISK: write_confirm]）\n"
            "- update: 更新茬口信息（[RISK: write_confirm]）\n"
            "- delete: 删除茬口（[RISK: write_high]，不可恢复）\n"
            "- templates: 查询农场作物模板（read）\n"
            "- system_templates: 查询系统作物模板（read）\n"
            "缺 crop_template_id 可先调 templates 或 system_templates 查询。"
        )

    @property
    def risk_level(self) -> str:
        # 默认返回 read（对应 query）；实际风险由 dynamic_risk_level 计算。
        return "read"

    def dynamic_risk_level(self, params: dict[str, Any]) -> str:
        """根据 operation 参数返回实际风险等级。"""
        op = (params.get("operation") or "").lower()
        if op in ("create", "advance", "update"):
            return "write_confirm"
        if op == "delete":
            return "write_high"
        return "read"  # query/detail/templates/system_templates 或未知

    @property
    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "operation": {
                    "type": "string",
                    "enum": [
                        "query", "detail", "create", "advance",
                        "update", "delete", "templates", "system_templates",
                    ],
                    "description": "操作类型：query=列表，detail=详情，create=创建，"
                                   "advance=推进阶段，update=更新，delete=删除，"
                                   "templates=农场作物模板，system_templates=系统作物模板",
                },
                "cycle_id": {
                    "type": "integer",
                    "description": "茬口 ID（detail/advance/update/delete 必填）",
                },
                "name": {
                    "type": "string",
                    "description": "茬口名称（create 必填，update 可选）",
                },
                "crop_template_id": {
                    "type": "integer",
                    "description": "作物模板 ID（create 必填，update 可选）",
                },
                "start_date": {
                    "type": "string",
                    "description": "YYYY-MM-DD 开播日期（create 必填，update 可选）",
                },
                "field_name": {
                    "type": "string",
                    "description": "地块名称（create/update 可选）",
                },
                "total_area_mu": {
                    "type": "number",
                    "description": "种植面积（亩，create/update 可选）",
                },
                "season": {
                    "type": "string",
                    "description": "季节（create/update 可选）",
                },
                "batch_note": {
                    "type": "string",
                    "description": "批次备注（create/update 可选）",
                },
                "skip": {
                    "type": "integer",
                    "description": "分页偏移（query/templates/system_templates，默认 0）",
                },
                "limit": {
                    "type": "integer",
                    "description": "分页大小（query/templates/system_templates，默认 20）",
                },
                "category": {
                    "type": "string",
                    "description": "分类过滤（system_templates 可选）",
                },
            },
            "required": ["operation"],
        }

    async def execute(self, params: dict[str, Any], ctx: SkillContext) -> SkillResult:
        """调用 business.manage_crop_cycle MCP tool。

        业务侧该 tool 会根据 operation 路由到对应的查询/创建/推进/更新/删除/模板逻辑。
        """
        result = await ctx.business_client.call_tool(self.mcp_tool, params)
        return SkillResult(data=result)


skill = ManageCropCycleSkill()
