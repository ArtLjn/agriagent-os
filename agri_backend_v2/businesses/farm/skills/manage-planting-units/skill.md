---
schema_version: 1
name: manage_planting_units
kind: mcp
mcp_tool: business.manage_planting_units
risk_level: mixed
description: 查询或创建茬口下真实存在的地块、棚或种植区域，不用茬口 field_name 字符串代替实体。
triggers: [种植单元, 地块, 大棚, 种植区域]
operations:
  query: {tool_name: query_planting_units, description: 查询真实种植单元，可按茬口过滤。, risk_level: read, parameters: [cycle_id], required: []}
  detail: {tool_name: get_planting_unit_detail, description: 查询指定种植单元详情。, risk_level: read, parameters: [unit_id], required: [unit_id]}
  create: {tool_name: create_planting_unit, description: 在指定茬口下创建真实种植单元。, risk_level: write_confirm, parameters: [cycle_id, name, area_mu, planted_date, status, note], required: [cycle_id, name]}
parameters:
  type: object
  properties:
    operation: {type: string, enum: [query, detail, create]}
    cycle_id: {type: integer, description: 当前农场的茬口 ID。}
    unit_id: {type: integer, description: 种植单元 ID。}
    name: {type: string, description: 地块、棚或区域名称。}
    area_mu: {type: number, description: 面积，单位亩。}
    planted_date: {type: string, description: 种植日期，格式 YYYY-MM-DD。}
    status: {type: string, description: 状态，默认 active。}
    note: {type: string, description: 位置或备注。}
  required: [operation]
---

# manage_planting_units

种植单元是独立业务实体；完整种植任务由聚合计划在同一事务中创建。
