---
schema_version: 1
name: manage_crop_templates
kind: mcp
mcp_tool: business.manage_crop_templates
risk_level: mixed
description: 管理当前农场可绑定的作物模板；系统模板必须先导入农场，不能直接绑定茬口。
triggers: [作物模板, 生长阶段, 导入系统模板, 新建模板]
operations:
  query:
    tool_name: query_crop_templates
    description: 查询当前农场已有作物模板。
    risk_level: read
    execution: {mode: parallel_safe, max_concurrency: 4}
    parameters: [skip, limit]
    required: []
  detail:
    tool_name: get_crop_template_detail
    description: 查询当前农场指定作物模板详情。
    risk_level: read
    execution: {mode: parallel_safe, max_concurrency: 4}
    parameters: [template_id]
    required: [template_id]
  create: {tool_name: create_crop_template, description: 创建带生长阶段的农场作物模板。, risk_level: write_confirm, parameters: [name, variety, category, stages], required: [name, stages]}
  import_system: {tool_name: import_system_crop_template, description: 将系统作物模板复制到当前农场后返回可绑定的农场模板 ID。, risk_level: write_confirm, parameters: [system_template_id], required: [system_template_id]}
parameters:
  type: object
  properties:
    operation: {type: string, enum: [query, detail, create, import_system]}
    name: {type: string, description: 作物模板名称。}
    variety: {type: string, description: 作物品种。}
    category: {type: string, description: 作物分类。}
    stages:
      type: array
      minItems: 1
      description: 生长阶段列表；每个阶段都必须提供完整的周期和顺序信息。
      items:
        type: object
        properties:
          name: {type: string, description: 阶段名称。}
          duration_days: {type: integer, minimum: 1, maximum: 3650, description: 阶段持续天数。}
          order_index: {type: integer, minimum: 0, description: 阶段顺序，从 0 开始。}
          key_tasks: {type: string, maxLength: 500, description: 阶段关键农事任务。}
        required: [name, duration_days, order_index]
    template_id: {type: integer, description: 当前农场模板 ID。}
    system_template_id: {type: integer, description: 待导入的系统模板 ID。}
    skip: {type: integer, description: 分页偏移。}
    limit: {type: integer, description: 分页大小。}
  required: [operation]
---

# manage_crop_templates

模板写操作独立于茬口 CRUD。完整种植任务优先使用聚合种植计划能力。
