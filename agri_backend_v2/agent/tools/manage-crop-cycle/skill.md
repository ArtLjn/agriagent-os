---
schema_version: 1
name: manage_crop_cycle
kind: mcp
mcp_tool: business.manage_crop_cycle
risk_level: mixed
description: |
  管理种植茬口。根据用户意图选择 operation：
  - create: 用户要新建茬口（如「新建1号茬口种番茄」「开一个新茬口」）
  - advance: 用户要推进茬口到下一阶段（如「1号茬口该移栽了」「进入下一阶段」）
  - query: 用户要查看茬口列表（如「有哪些茬口」「当前几个茬口」）
  - detail: 用户要看某个茬口详情（如「1号茬口什么情况」「这茬口到哪步了」）
  - update: 用户要修改茬口信息（如「改茬口名称」「更新面积」）
  - delete: 用户要删除茬口（如「删掉那个茬口」）
  - templates: 查看农场作物模板
  - system_templates: 查看系统作物模板
  注意：用户说「新建/开播/种」→create，「推进/下一阶段」→advance。
triggers:
  - 茬口
  - 新建茬口
  - 推进
  - 种植
  - 开播
operations:
  query: {tool_name: query_crop_cycles, description: 查询当前农场的种植茬口列表。, risk_level: read, parameters: [skip, limit], required: []}
  detail: {tool_name: get_crop_cycle_detail, description: 查询指定茬口的作物、面积、生长阶段等详细信息。, risk_level: read, parameters: [cycle_id], required: [cycle_id]}
  create:
    tool_name: create_crop_cycle
    description: 新建一个种植茬口。必须绑定与目标作物一致的农场模板；系统模板需先导入。
    risk_level: write_confirm
    parameters: [name, crop_name, crop_template_id, start_date, field_name, total_area_mu, season, batch_note]
    required: [name, crop_name, crop_template_id, start_date]
  advance: {tool_name: advance_crop_cycle, description: 将指定茬口推进到下一个生长阶段。, risk_level: write_confirm, parameters: [cycle_id], required: [cycle_id]}
  update: {tool_name: update_crop_cycle, description: 修改指定茬口的名称、作物模板、日期、地块、面积或备注。, risk_level: write_confirm, parameters: [cycle_id, name, crop_template_id, start_date, field_name, total_area_mu, season, batch_note], required: [cycle_id]}
  delete: {tool_name: delete_crop_cycle, description: 删除指定种植茬口。, risk_level: write_high, parameters: [cycle_id], required: [cycle_id]}
  templates:
    tool_name: list_crop_templates
    capability_group: crop_template_catalog
    data_scope: farm_imported_templates
    freshness_requirement: current_farm_state
    description: 查询当前农场可用的作物模板。创建茬口前可先调用本工具取得 crop_template_id。
    risk_level: read
    execution: {mode: parallel_safe, max_concurrency: 4}
    parameters: [skip, limit]
    required: []
  system_templates:
    tool_name: list_system_crop_templates
    capability_group: crop_template_catalog
    data_scope: system_templates
    freshness_requirement: system_catalog
    description: 查询系统提供的作物模板，可按分类筛选。
    risk_level: read
    execution: {mode: parallel_safe, max_concurrency: 4}
    parameters: [skip, limit, category]
    required: []
parameters:
  type: object
  properties:
    operation:
      type: string
      enum: [query, detail, create, advance, update, delete, templates, system_templates]
      description: |
        根据用户意图选择：
        create=新建茬口（新建/开播/种→选这个），
        advance=推进阶段（推进/下一阶段→选这个），
        query=查列表，detail=查详情，
        update=修改，delete=删除，
        templates=农场模板，system_templates=系统模板
    cycle_id:
      type: integer
      description: 茬口 ID（detail/advance/update/delete 必填）
    name:
      type: string
      description: 茬口名称（create 必填，update 可选）
    crop_name:
      type: string
      description: 目标作物名称；必须与绑定模板一致（create 必填）
    crop_template_id:
      type: integer
      description: 作物模板 ID（create 必填，update 可选）
    start_date:
      type: string
      description: YYYY-MM-DD 开播日期（create 必填，update 可选）
    field_name:
      type: string
      description: 地块名称（create/update 可选）
    total_area_mu:
      type: number
      description: 种植面积（亩，create/update 可选）
    season:
      type: string
      description: 季节（create/update 可选）
    batch_note:
      type: string
      description: 批次备注（create/update 可选）
    skip:
      type: integer
      description: 分页偏移（query/templates/system_templates，默认 0）
      default: 0
    limit:
      type: integer
      description: 分页大小（query/templates/system_templates，默认 20）
      default: 20
    category:
      type: string
      description: 分类过滤（system_templates 可选）
  required: [operation]
---

# manage_crop_cycle

管理种植茬口，支持 8 种操作：
- `create` — 新建茬口（write_confirm）
- `advance` — 推进到下一阶段（write_confirm）
- `query` — 查列表（read）
- `detail` — 查详情（read）
- `update` — 修改信息（write_confirm）
- `delete` — 删除茬口（write_high）
- `templates` — 农场作物模板（read）
- `system_templates` — 系统作物模板（read）

## 何时使用

- "新建一个茬口种番茄" → operation=create
- "1号茬口该移栽了" → operation=advance, cycle_id=1
- "有哪些茬口" → operation=query
- "删掉那个茬口" → operation=delete, cycle_id=N

## HITL

- create/advance/update 是 write_confirm，需用户确认
- delete 是 write_high，必须用户明确确认
- query/detail/templates/system_templates 是 read，不闸门
