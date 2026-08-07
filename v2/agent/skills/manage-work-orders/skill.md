---
schema_version: 1
name: manage_work_orders
kind: mcp
mcp_tool: business.manage_work_orders
risk_level: mixed
description: |
  管理农事作业单。根据用户意图选择 operation：
  - create: 用户要创建作业单（如「创建播种作业单」「安排今天施肥」）
  - settle: 用户要结算人工工资（如「结算工人工资」「算算人工费用」）
  - query: 用户要查看作业单列表（如「有哪些作业单」「查作业单」）
  - detail: 用户要看某个作业单详情（需 work_order_id）
  - update: 用户要修改作业单（需 work_order_id）
  注意：用户说「创建/安排/派工」→create，「结算/算工资」→settle。
triggers:
  - 作业单
  - 派工
  - 结算
  - 人工费
operations:
  query: {tool_name: query_work_orders, description: 查询农事作业单列表，可按茬口筛选。, risk_level: read, parameters: [cycle_id, skip, limit], required: []}
  detail: {tool_name: get_work_order_detail, description: 查询指定农事作业单的详细信息。, risk_level: read, parameters: [work_order_id], required: [work_order_id]}
  create:
    tool_name: create_work_order
    description: 创建一条浇水、施肥、播种、采摘等农事作业单。
    risk_level: write_confirm
    parameters: [operation_type, operation_date, cycle_id, scope_type, note]
    required: [operation_type, operation_date]
  update: {tool_name: update_work_order, description: 修改指定作业单的作业内容、日期、茬口、范围或备注。, risk_level: write_confirm, parameters: [work_order_id, operation_type, operation_date, cycle_id, scope_type, note], required: [work_order_id]}
  settle: {tool_name: settle_work_orders, description: 按工人或日期范围结算农事作业的人工费用。, risk_level: write_confirm, parameters: [amount, worker_name, start_date, end_date], required: []}
parameters:
  type: object
  properties:
    operation:
      type: string
      enum: [query, detail, create, update, settle]
      description: |
        根据用户意图选择：
        create=创建作业单（创建/安排/派工→选这个），
        settle=结算工资（结算/算工资→选这个），
        query=查列表，detail=查详情，update=修改
    work_order_id:
      type: integer
      description: 作业单 ID（detail/update 必填）
    operation_type:
      type: string
      description: 作业类型，如"播种"、"采摘"（create 必填，update 可选）
    operation_date:
      type: string
      description: YYYY-MM-DD 作业日期（create 必填，update 可选）
    cycle_id:
      type: integer
      description: 茬口 ID（query 可选过滤，create 可选关联）
    scope_type:
      type: string
      description: 作业范围：cycle=茬口 / unit=单株（create 可选）
    note:
      type: string
      description: 备注（create/update 可选）
    amount:
      type: number
      description: 结算金额（settle 可选）
    worker_name:
      type: string
      description: 工人姓名（settle 可选过滤）
    start_date:
      type: string
      description: YYYY-MM-DD 结算开始日期（settle 可选）
    end_date:
      type: string
      description: YYYY-MM-DD 结算结束日期（settle 可选）
    skip:
      type: integer
      description: 分页偏移（query，默认 0）
    limit:
      type: integer
      description: 分页大小（query，默认 20）
  required: [operation]
---

# manage_work_orders

管理农事作业单，支持 5 种操作：
- `create` — 创建作业单（write_confirm）
- `settle` — 结算人工工资（write_confirm）
- `query` — 查列表（read）
- `detail` — 查详情（read）
- `update` — 修改（write_confirm）

## HITL

- create/update/settle 是 write_confirm，需用户确认
- query/detail 是 read，不闸门
