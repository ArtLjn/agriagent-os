---
schema_version: 1
name: manage_workers
kind: mcp
mcp_tool: business.manage_workers
risk_level: mixed
description: |
  管理农场工人档案。根据用户意图选择 operation：
  - create: 用户要添加工人（如「加个工人张三」「新录一个工人」）
  - query: 用户要查看工人列表（如「有哪些工人」「工人名单」）
  - update: 用户要修改工人信息（如「改张三电话」「更新工人信息」）
  - delete: 用户要停用工人（如「停用张三」「去掉这个工人」）
  注意：用户说「加人/招工/录工人」→create，不是 query。
triggers:
  - 工人
  - 招工
  - 加人
operations:
  query: {tool_name: query_workers, description: 查询农场工人档案列表，可只查看在职工人。, risk_level: read, parameters: [active_only], required: []}
  create: {tool_name: create_worker, description: 新增一名农场工人，填写姓名以及可选的联系方式和计酬信息。, risk_level: write_confirm, parameters: [name, phone, default_pay_type, default_unit_price, note], required: [name]}
  update: {tool_name: update_worker, description: 修改指定工人的姓名、电话、计酬方式、单价、备注或状态。, risk_level: write_confirm, parameters: [worker_id, name, phone, default_pay_type, default_unit_price, note, status], required: [worker_id]}
  delete: {tool_name: deactivate_worker, description: 停用指定工人并保留历史用工记录。, risk_level: write_confirm, parameters: [worker_id], required: [worker_id]}
parameters:
  type: object
  properties:
    operation:
      type: string
      enum: [query, create, update, delete]
      description: |
        根据用户意图选择：
        create=添加工人（加人/招工/录工人→选这个），
        query=查工人列表（查/看/有哪些→选这个），
        update=修改信息，delete=停用工人
    worker_id:
      type: integer
      description: 工人 ID（update/delete 必填）
    name:
      type: string
      description: 工人姓名（create 必填，update 可选）
    phone:
      type: string
      description: 联系电话（create/update 可选）
    default_pay_type:
      type: string
      description: 默认计酬方式：daily/monthly/hourly（create/update 可选）
    default_unit_price:
      type: number
      description: 默认单价（create/update 可选）
    note:
      type: string
      description: 备注（create/update 可选）
    status:
      type: string
      description: 状态（update 可选）
    active_only:
      type: boolean
      description: 仅查询在职工人（query 可选，默认 true）
  required: [operation]
---

# manage_workers

管理农场工人档案，支持 4 种操作：
- `create` — 添加工人（write_confirm，同名幂等）
- `query` — 查列表（read）
- `update` — 修改信息（write_confirm）
- `delete` — 停用工人（write_confirm，保留历史用工）

## HITL

- create/update/delete 是 write_confirm，需用户确认
- query 是 read，不闸门
