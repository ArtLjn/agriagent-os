---
name: manage_farm_logs
kind: mcp
mcp_tool: business.manage_farm_logs
risk_level: mixed
description: 管理农事日志，支持查询、创建、删除农事操作。写操作需用户确认。
triggers:
  - 农事记录
  - 浇水了
  - 施肥了
  - 删除农事
  - 最近农事
parameters:
  type: object
  properties:
    operation:
      type: string
      enum: [query, create, delete]
      description: 操作类型：query=查询，create=创建，delete=删除。
    cycle_id:
      type: integer
      description: 茬口 ID（create/delete 必填，query 可选过滤）。
    operation_type:
      type: string
      description: 操作类型（create 时必填），如"浇水"、"施肥"、"打药"。
    operation_date:
      type: string
      description: 操作日期 YYYY-MM-DD（create 时不传默认今天）。
    note:
      type: string
      description: 备注（create 时使用）。
    worker_names:
      type: array
      items:
        type: string
      description: 参与工人姓名列表（create 时使用）。
    log_id:
      type: integer
      description: 农事记录 ID（delete 必填）。
    days:
      type: integer
      description: 查询最近 N 天（query 时用，默认 7）。
    limit:
      type: integer
      description: 查询返回最大条数（query 时用，默认 20）。
  required: [operation]
---

# manage_farm_logs

管理农事日志，包含三种操作：
- `query` — 查询最近农事记录（read）
- `create` — 创建新农事记录（write_confirm）
- `delete` — 删除农事记录（write_high）

## 何时使用

- "最近有哪些农事" → operation=query
- "1号茬口最近一周干了什么" → operation=query, cycle_id=1, days=7
- "今天浇水了，记一笔" → operation=create, operation_type="浇水"
- "1号茬口刚才打了杀菌剂" → operation=create, cycle_id=1, operation_type="打药"
- "删除 8 号农事记录" → operation=delete, log_id=8

## 缺参策略

- create 缺 cycle_id：先调 `get_farm_status` 查活跃茬口，让用户选
- create 缺 operation_type：追问用户做了什么操作
- delete 缺 log_id：先调 query 查最近记录，让用户选

## HITL

- query 是 read，不闸门
- create 是 write_confirm，agent 在调用前必须先向用户确认
- delete 是 write_high，必须用户明确确认后才能执行
