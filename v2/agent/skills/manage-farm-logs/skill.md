---
schema_version: 1
name: manage_farm_logs
kind: mcp
mcp_tool: business.manage_farm_logs
risk_level: mixed
description: |
  管理农事日志。根据用户意图选择 operation：
  - create: 用户要记录农事操作（如「今天施肥」「给1号茬口浇水」「记录打药」）
  - query: 用户要查看已有农事（如「最近做了什么」「查农事记录」「这周干了啥」）
  - update: 用户要修改某条农事（如「把那条施肥改成30斤」「更新日志」）
  - delete: 用户要删除某条农事（如「删掉那条记录」）
  注意：用户说「做了XX/施肥/浇水/打药」等表示新增农事 → 用 create，不是 query。
triggers:
  - 农事记录
  - 浇水了
  - 施肥了
  - 打药
  - 删除农事
  - 最近农事
operations:
  query: {tool_name: query_farm_logs, description: 查询用户已经做过的农事记录；用户问“最近做了什么”“这几天干了啥”“最近农活”时必须使用此工具，不要改用农场概览或作业单查询。, risk_level: read, parameters: [cycle_id, days, limit], required: []}
  create:
    tool_name: create_farm_log
    description: 记录已经完成的浇水、施肥、打药、播种、采摘等农事活动。
    risk_level: write_confirm
    parameters: [cycle_id, operation_type, operation_date, note, worker_names]
    required: [cycle_id, operation_type]
  update: {tool_name: update_farm_log, description: 修改指定农事记录的操作、日期、备注或参与工人。, risk_level: write_confirm, parameters: [log_id, cycle_id, operation_type, operation_date, note, worker_names], required: [log_id]}
  delete: {tool_name: delete_farm_log, description: 删除指定农事记录。, risk_level: write_high, parameters: [log_id], required: [log_id]}
parameters:
  type: object
  properties:
    operation:
      type: string
      enum: [query, create, update, delete]
      description: |
        根据用户意图选择：
        create=记录新农事（施肥/浇水/打药/播种→选这个），
        query=查看已有农事（查/看/最近→选这个），
        update=修改已有记录，delete=删除记录
    cycle_id:
      type: integer
      description: 茬口 ID（create/delete 必填，query 可选过滤，update 可选更新）
    operation_type:
      type: string
      description: 操作类型，如"浇水"、"施肥"（create 必填，update 可选）
    operation_date:
      type: string
      description: YYYY-MM-DD（create/update 不传默认今天）
    note:
      type: string
      description: 备注（create/update 可选）
    worker_names:
      type: array
      items:
        type: string
      description: 参与工人姓名列表（update 时全量替换）
    log_id:
      type: integer
      description: 农事记录 ID（update/delete 必填）
    days:
      type: integer
      description: 查询最近 N 天，默认 7
    limit:
      type: integer
      description: 查询返回最大条数，默认 20
  required: [operation]
---

# manage_farm_logs

管理农事日志，支持 4 种操作：
- `create` — 创建农事记录（write_confirm）
- `query` — 查询最近农事（read）
- `update` — 更新农事记录（write_confirm）
- `delete` — 删除农事记录（write_high）

## 何时使用

- "今天浇水了" → operation=create, operation_type="浇水"
- "1号茬口最近一周干了什么" → operation=query, cycle_id=1, days=7
- "把那条施肥改成30斤" → operation=update, log_id=N
- "删除 8 号农事记录" → operation=delete, log_id=8

## 缺参策略

- create 缺 cycle_id：先调 `get_farm_status` 查活跃茬口，让用户选
- create 缺 operation_type：追问用户做了什么操作
- delete 缺 log_id：先调 query 查最近记录，让用户选

## HITL

- create/update 是 write_confirm，agent 在调用前必须先向用户确认
- delete 是 write_high，必须用户明确确认后才能执行
- query 是 read，不闸门
