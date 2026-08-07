---
schema_version: 1
name: manage_cost
kind: mcp
mcp_tool: business.manage_cost
risk_level: mixed
description: |
  管理农场财务记账。根据用户意图选择 operation：
  - create: 用户要记账/记录收支（如「买化肥100」「收入500」「花了200买农药」「今天支出300」）
  - query: 用户要查看/搜索已有的收支记录（如「查一下账」「最近花了多少」「今天的记录」）
  - summary: 用户要看年度收支汇总（如「今年汇总」「2026年收支」）
  - profit: 用户要分析某茬口的利润（如「这茬赚了多少」）
  - delete: 用户要删除某条记录（如「删掉那条记录」）
  - categories: 用户要查看成本分类列表（如「有哪些分类」）
  注意：用户说「买/花/支出/收入/赚」等表示新增记录 → 用 create，不是 query。
triggers:
  - 买
  - 花费
  - 支出
  - 收入
  - 记账
  - 成本
  - 利润
  - 汇总
operations:
  query:
    tool_name: query_cost_records
    description: 查询农场成本和收入记录，可按茬口或分类筛选。
    risk_level: read
    parameters: [cycle_id, category, skip, limit]
    required: []
  create:
    tool_name: create_cost_record
    description: 记录一笔农场支出或收入。根据用户表述填写 cost 或 income、金额、分类和日期。
    risk_level: write_confirm
    parameters: [record_type, category, amount, record_date, cycle_id, note, counterparty]
    required: [record_type, category, amount, record_date]
  summary:
    tool_name: summarize_cost_records
    description: 查询指定年份的农场收支汇总。
    risk_level: read
    parameters: [year]
    required: [year]
  profit:
    tool_name: analyze_crop_cycle_profit
    description: 分析指定茬口的收入、成本和利润。
    risk_level: read
    parameters: [cycle_id]
    required: [cycle_id]
  delete:
    tool_name: delete_cost_record
    description: 删除指定的成本或收入记录。
    risk_level: write_high
    parameters: [record_id]
    required: [record_id]
  categories:
    tool_name: list_cost_categories
    description: 查询农场可用的成本和收入分类。
    risk_level: read
    parameters: []
    required: []
parameters:
  type: object
  properties:
    operation:
      type: string
      enum: [query, create, summary, profit, delete, categories]
      description: |
        根据用户意图选择：
        create=新增收支记录（买/花/支出/收入/赚→选这个），
        query=查看已有记录（查/看/搜索/最近→选这个），
        summary=年度汇总，profit=茬口利润，
        delete=删除记录，categories=查分类列表
    record_type:
      type: string
      enum: [cost, income]
      description: 记录类型：cost=支出 / income=收入（create 必填）
    category:
      type: string
      description: 成本分类（create 必填，query 可选过滤）
    amount:
      type: number
      description: 金额（create 必填）
    record_date:
      type: string
      description: YYYY-MM-DD 记账日期（create 必填）
    cycle_id:
      type: integer
      description: 茬口 ID（query/profit 可选过滤，create 可选关联）
    note:
      type: string
      description: 备注（create 可选）
    counterparty:
      type: string
      description: 交易对手（create 可选）
    record_id:
      type: integer
      description: 记录 ID（delete 必填）
    year:
      type: integer
      description: 年份（summary 必填）
    skip:
      type: integer
      description: 分页偏移（query，默认 0）
    limit:
      type: integer
      description: 分页大小（query，默认 20）
  required: [operation]
---

# manage_cost

管理农场财务记账，支持 6 种操作：
- `create` — 新增收支记录（write_confirm）
- `query` — 查询收支记录（read）
- `summary` — 年度收支汇总（read）
- `profit` — 茬口利润分析（read）
- `delete` — 删除记录（write_high）
- `categories` — 成本分类列表（read）

## 何时使用

- "今天买化肥100" → operation=create, record_type=cost, amount=100, category=肥料
- "收入500" → operation=create, record_type=income, amount=500
- "查一下最近的账" → operation=query
- "今年收支汇总" → operation=summary, year=2026
- "这茬口赚了多少" → operation=profit, cycle_id=N

## 缺参策略

- create 缺 record_type：从上下文推断（买/花→cost，收入/赚→income），否则追问
- create 缺 amount：从文本提取数字，否则追问
- create 缺 category：默认「其他」
- create 缺 record_date：默认今天
- summary 缺 year：用当前年份
- profit 缺 cycle_id：先调 get_farm_status 查活跃茬口

## HITL

- create 是 write_confirm，agent 在调用前必须先向用户确认
- delete 是 write_high，必须用户明确确认后才能执行
- query/summary/profit/categories 是 read，不闸门
