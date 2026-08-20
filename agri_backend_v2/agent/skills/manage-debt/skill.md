---
schema_version: 1
name: manage_debt
kind: mcp
mcp_tool: business.manage_debt
risk_level: mixed
description: |
  管理农场赊账。根据用户意图选择 operation：
  - create: 用户要记录赊账（如「欠张三500化肥款」「李四借了300」「应收王五200」）
  - query: 用户要查看未结清赊账（如「谁还欠钱」「查赊账」「未结清的有哪些」）
  - repay: 用户要记录还款/结算（如「张三还了200」「结清李四的账」）
  - summary: 用户要看赊账汇总（如「总共欠多少」「按人汇总」）
  注意：用户说「欠/借/赊」表示新增赊账→create，「还/结清」表示还款→repay。
triggers:
  - 欠
  - 赊
  - 借
  - 还款
  - 结清
  - 赊账
operations:
  query: {tool_name: query_debts, description: 查询未结清的应收或应付赊账，可按交易对手筛选。, risk_level: read, parameters: [counterparty, skip, limit], required: []}
  create:
    tool_name: create_debt_record
    description: 记录一笔新的应收或应付赊账，根据用户表述填写类型、金额、日期和交易对手。
    risk_level: write_confirm
    parameters: [record_type, category, amount, record_date, counterparty, cycle_id, note]
    required: [record_type, amount, record_date]
  repay: {tool_name: repay_debt, description: 记录交易对手的还款或结清赊账。, risk_level: write_confirm, parameters: [counterparty, amount, record_date, note], required: [counterparty]}
  summary: {tool_name: summarize_debts, description: 按交易对手汇总农场应收和应付赊账。, risk_level: read, parameters: [], required: []}
parameters:
  type: object
  properties:
    operation:
      type: string
      enum: [query, create, repay, summary]
      description: |
        根据用户意图选择：
        create=记录新赊账（欠/借/赊→选这个），
        repay=还款结算（还/结清→选这个），
        query=查看未结清，summary=按人汇总
    record_type:
      type: string
      enum: [debt_payable, debt_receivable]
      description: 赊账类型：debt_payable=应付 / debt_receivable=应收（create 必填）
    category:
      type: string
      description: 赊账分类（create 可选，默认“赊账”）
    amount:
      type: number
      description: 金额（create/repay 必填）
    record_date:
      type: string
      description: YYYY-MM-DD 记账日期（create 必填）
    counterparty:
      type: string
      description: 交易对手（create/query/repay 可选过滤）
    cycle_id:
      type: integer
      description: 茬口 ID（create 可选关联）
    note:
      type: string
      description: 备注（create 可选）
    skip:
      type: integer
      description: 分页偏移（query，默认 0）
    limit:
      type: integer
      description: 分页大小（query，默认 20）
  required: [operation]
---

# manage_debt

管理农场赊账，支持 4 种操作：
- `create` — 记录新赊账（write_confirm）
- `query` — 查询未结清赊账（read）
- `repay` — 还款结算（write_confirm）
- `summary` — 按交易对手汇总（read）

## 何时使用

- "欠张三500化肥款" → operation=create, record_type=debt_payable, amount=500
- "李四还了200" → operation=repay, counterparty=李四, amount=200
- "谁还欠钱" → operation=query
- "总共欠多少" → operation=summary

## HITL

- create/repay 是 write_confirm，需用户确认
- query/summary 是 read，不闸门
