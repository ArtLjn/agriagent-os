---
schema_version: 1
name: manage_planting_plan
kind: mcp
mcp_tool: business.prepare_planting_plan
risk_level: mixed
description: |
  处理完整种植目标。先准备包含作物模板、茬口和真实种植单元的原子计划，
  用户批准后再提交同一份计划；不要自行拆成多个互不关联的写操作。
triggers: [种植计划, 创建地块并种植, 开始种植, 新建种植项目]
operations:
  prepare:
    tool_name: prepare_planting_plan
    mcp_tool: business.prepare_planting_plan
    inject_operation: false
    description: 准备完整种植计划并返回审批摘要，不写入业务实体。无同作物模板且用户已要求规划时，生成名称与目标作物一致的自定义模板草案并使用 create_custom。
    risk_level: read
    capability_group: planting_plan
    data_scope: farm_operations
    freshness_requirement: current_farm_state
    approval_followup:
      tool_name: commit_planting_plan
      arguments_from_result: [client_request_id, approval_fingerprint, plan]
    parameters: [crop_name, total_area_mu, field_name, field_location, field_location_confirmed, start_date, cycle_name, variety, template_strategy, template_id, system_template_id, custom_template, advisory]
    required: [crop_name, total_area_mu, field_name, start_date]
  commit:
    tool_name: commit_planting_plan
    mcp_tool: business.commit_planting_plan
    inject_operation: false
    description: 提交用户已批准的完整种植计划；由 Runtime 在 prepare 审批通过后用原始参数自动调用，不暴露给模型。
    risk_level: write_confirm
    expose_to_model: false
    finalize_after_success: true
    parameters: [client_request_id, approval_fingerprint, plan]
    required: [client_request_id, approval_fingerprint, plan]
parameters:
  type: object
  properties:
    operation:
      type: string
      enum: [prepare, commit]
    crop_name:
      type: string
      description: 用户明确要种植的目标作物名称。
    total_area_mu:
      type: number
      description: 总种植面积，单位亩，必须大于 0。
    field_name:
      type: string
      description: 要创建的真实地块、棚或区域名称。
    field_location:
      type: string
      description: 地块位置或备注；不确定时不得用农场地址静默替代。
    field_location_confirmed:
      type: boolean
      description: 仅在农场默认位置与目标地块位置冲突且用户已明确确认目标地块位置后设为 true。
    start_date:
      type: string
      description: 计划开始日期，格式 YYYY-MM-DD。
    cycle_name:
      type: string
      description: 茬口名称，可不填并由业务层生成。
    variety:
      type: string
      description: 作物品种，可选。
    template_strategy:
      type: string
      enum: [auto, existing, import_system, create_custom]
      description: 模板处理方式；auto 只允许同作物精确匹配，不允许无关模板兜底；无匹配且用户要求规划时使用 create_custom。
    template_id:
      type: integer
      description: 已有农场模板 ID，仅在确认属于目标作物时使用。
    system_template_id:
      type: integer
      description: 系统模板 ID；提交时会先导入当前农场再绑定。
    custom_template:
      type: object
      description: 无匹配模板时提供的自定义模板，至少包含 stages。
    advisory:
      type: object
      description: 天气、位置等只读建议，不参与业务实体标识。
    client_request_id:
      type: string
      description: 准备阶段返回的幂等请求 ID。
    approval_fingerprint:
      type: string
      description: 准备阶段返回的审批指纹，提交时必须原样传递。
    plan:
      type: object
      description: 准备阶段返回的完整 plan，禁止审批后修改。
  required: [operation]
---

# manage_planting_plan

完整种植目标必须使用 `prepare_planting_plan` → 用户确认 →
`commit_planting_plan`。模型只负责调用 `prepare_planting_plan`；
prepare 返回 ready 后，Runtime 用原始请求 ID、审批指纹和 plan 自动驱动审批与提交，
模型不得自行重建或改写提交参数。提交成功后直接根据结构化结果答复，不能继续调用写工具。
