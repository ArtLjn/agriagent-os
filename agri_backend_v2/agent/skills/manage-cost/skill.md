---
schema_version: 1
name: manage_cost
kind: mcp
mcp_tool: business.manage_cost
risk_level: mixed
description: |
  管理农场财务记账（实际收支流水）。根据用户意图选择 operation：
  - create: 用户要记账/记录实际收支（如「买化肥100」「收入500」「花了200买农药」）
  - query: 用户要查看/搜索已有的收支记录（如「查一下账」「最近花了多少」）
  - summary: 用户要看年度收支汇总（如「今年汇总」「2026年收支」）
  - profit: 用户要分析某茬口的利润（如「这茬赚了多少」）
  - delete: 用户要删除某条记录
  - categories: 用户要查看成本分类列表
  - create_category: 用户要创建财务分类（如「创建一个人工分类」）
  - delete_category: 用户要删除自定义分类
  注意：工人工资不通过此 skill 记账。工人工资通过 manage_work_orders(add_labor)
  记录工时，月底用 manage_work_orders(settle) 统一结算，系统自动生成成本账单。
triggers:
  - 买
  - 花费
  - 支出
  - 收入
  - 记账
  - 成本
  - 利润
  - 汇总
  - 分类
operations:
  query:
    tool_name: query_cost_records
    description: 查询农场成本和收入记录，可按茬口或分类筛选。
    risk_level: read
    parameters: [cycle_id, category, skip, limit]
    required: []
  create:
    tool_name: create_cost_record
    description: 记录一笔农场实际支出或收入。支出默认未结算（settled_amount=0），收入默认已结算。
    risk_level: write_confirm
    parameters: [record_type, category, amount, record_date, cycle_id, note, counterparty, settled_amount, record_subtype, source_type, source_id]
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
  create_category:
    tool_name: create_cost_category
    description: 创建用户自定义财务分类。
    risk_level: write_confirm
    parameters: [category, record_type]
    required: [category, record_type]
  delete_category:
    tool_name: delete_cost_category
    description: 删除用户自定义分类（系统预设分类不可删除）。
    risk_level: write_high
    parameters: [category_id]
    required: [category_id]
parameters:
  type: object
  properties:
    operation:
      type: string
      enum: [query, create, summary, profit, delete, categories, create_category, delete_category]
      description: |
        根据用户意图选择：
        create=新增收支记录（买/花/支出/收入/赚→选这个），
        query=查看已有记录（查/看/搜索/最近→选这个），
        summary=年度汇总，profit=茬口利润，
        delete=删除记录，categories=查分类列表，
        create_category=创建分类，delete_category=删除分类
    record_type:
      type: string
      enum: [cost, income]
      description: 记录类型：cost=支出 / income=收入（create/create_category 必填）
    category:
      type: string
      description: 分类名（create 必填，query 可选过滤，create_category 必填）
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
    settled_amount:
      type: number
      description: 已结清金额（create 可选，默认：支出=0 未结算，收入=全额 已结算）
    record_subtype:
      type: string
      description: 子类型如"赊账"（create 可选，赊账默认 settled_amount=0）
    source_type:
      type: string
      description: 来源类型如 operation_work_order / labor_entry（create 可选，用于关联工单等系统来源）
    source_id:
      type: integer
      description: 来源 ID（create 可选，配合 source_type 关联工单等）
    record_id:
      type: integer
      description: 记录 ID（delete 必填）
    category_id:
      type: integer
      description: 分类 ID（delete_category 必填）
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

管理农场财务记账（实际收支流水），支持 8 种操作：
- `create` — 新增收支记录（write_confirm），支出默认未结算
- `query` — 查询收支记录（read）
- `summary` — 年度收支汇总（read）
- `profit` — 茬口利润分析（read）
- `delete` — 删除记录（write_high）
- `categories` — 成本分类列表（read）
- `create_category` — 创建分类（write_confirm）
- `delete_category` — 删除分类（write_high）

## 工人工资 vs 财务记账

工人工资**不走此 skill**。工人工资通过 `manage_work_orders` 管理：
- `add_labor` 记录工时（出勤/应得工资，自动生成未结算成本账单）
- `settle` 月底统一结算（自动更新成本账单为已结算）

此 skill 只管实际收支流水，如买化肥、卖农产品等。

## 何时使用

- "今天买化肥100" → create, record_type=cost, amount=100, category=肥料
- "收入500" → create, record_type=income, amount=500
- "查一下最近的账" → query
- "今年收支汇总" → summary, year=2026
- "这茬口赚了多少" → profit, cycle_id=N
- "创建一个人工分类" → create_category, category=人工, record_type=cost
- "删掉分类5" → delete_category, category_id=5

## 缺参策略

- create 缺 record_type：从上下文推断（买/花→cost，收入/赚→income），否则追问
- create 缺 amount：从文本提取数字，否则追问
- create 缺 category：默认「其他」
- create 缺 record_date：默认今天
- create 缺 settled_amount：支出默认 0（未结算），收入默认全额（已结算）
- summary 缺 year：用当前年份
- profit 缺 cycle_id：先调 get_farm_status 查活跃茬口
- create_category 缺 record_type：追问是支出分类还是收入分类

## HITL

- create / create_category 是 write_confirm，需用户确认
- delete / delete_category 是 write_high，必须用户明确确认
- query/summary/profit/categories 是 read，不闸门
