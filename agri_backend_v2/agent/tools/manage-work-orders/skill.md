---
schema_version: 1
name: manage_work_orders
kind: mcp
mcp_tool: business.manage_work_orders
risk_level: mixed
description: |
  管理农事作业单、工时记录和工人工资查询。根据用户意图选择 operation：
  - create: 创建作业单/安排农事活动（如「创建播种作业单」「安排今天施肥」）
  - add_labor: 给已有作业单添加工时记录（如「朱哥今天育苗」「记一下朱哥的工」）
  - wages: 查询工人工资（如「本月未结款」「8月工资账单」「张三6-8月工资明细」）
  - settle: 月底统一结算工人工资（如「结算本月工人工资」「算算人工费用」）
  - query: 查看作业单列表
  - detail: 查看某个作业单详情
  - update: 修改作业单
  注意：工人工资和财务记账是分开的概念。
  create 只记录农事活动，add_labor 只记录工人出勤和应得工资（未支付），
  settle 是月底统一结算支付。都不走 manage_cost 手动记账。
triggers:
  - 作业单
  - 派工
  - 安排
  - 工时
  - 出勤
  - 工资
  - 薪资
  - 结算
  - 人工费
  - 未结
  - 未付
  - 账单
operations:
  query: {tool_name: query_work_orders, description: 查询农事作业单列表，可按茬口筛选。, risk_level: read, parameters: [cycle_id, skip, limit], required: []}
  detail: {tool_name: get_work_order_detail, description: 查询指定农事作业单的详细信息。, risk_level: read, parameters: [work_order_id], required: [work_order_id]}
  create:
    tool_name: create_work_order
    description: 创建农事作业单（纯农事记录，不记录工人工资）。
    risk_level: write_confirm
    parameters: [operation_type, operation_date, cycle_id, scope_type, note]
    required: [operation_type, operation_date]
  add_labor:
    tool_name: add_labor_to_work_order
    description: 给已有作业单添加工时记录（工人出勤/应得工资，未支付）。后端自动生成未结算人工成本账单。不传 unit_price/pay_type 时自动从工人档案读取。
    risk_level: write_confirm
    parameters: [work_order_id, worker_name, pay_type, unit_price, quantity]
    required: [work_order_id, worker_name]
  wages:
    tool_name: query_wages
    description: 查询工人工资汇总，三种模式：unpaid=查未结款汇总 / monthly=按月查历史 / worker=按工人查明细。
    risk_level: read
    parameters: [query_mode, worker_name, month, start_date, end_date]
    required: [query_mode]
  update: {tool_name: update_work_order, description: 修改指定作业单的作业内容、日期、茬口、范围或备注。, risk_level: write_confirm, parameters: [work_order_id, operation_type, operation_date, cycle_id, scope_type, note], required: [work_order_id]}
  settle: {tool_name: settle_work_orders, description: 月底按工人或日期范围统一结算未付人工工资。, risk_level: write_confirm, parameters: [amount, worker_name, start_date, end_date], required: []}
parameters:
  type: object
  properties:
    operation:
      type: string
      enum: [query, detail, create, add_labor, wages, update, settle]
      description: |
        根据用户意图选择：
        create=创建作业单/安排农事活动（创建/安排/派工→选这个），
        add_labor=记录工时/工人出勤（记工时/今天干了→选这个），
        wages=查工资/账单/未结款（工资/账单/未结/欠多少→选这个），
        settle=月底结算工资（结算/算工资/发工资→选这个），
        query=查列表，detail=查详情，update=修改
    work_order_id:
      type: integer
      description: 作业单 ID（detail/add_labor/update 必填，settle 可选筛选）
    operation_type:
      type: string
      description: 作业类型，如"播种"、"采摘"（create 必填，update 可选）
    operation_date:
      type: string
      description: YYYY-MM-DD 作业日期（create 必填，update 可选）
    cycle_id:
      type: integer
      description: 茬口 ID（query 可选过滤，create 可选关联，settle 可选筛选）
    scope_type:
      type: string
      description: 作业范围：cycle=茬口 / unit=单株（create 可选）
    note:
      type: string
      description: 备注（create/update 可选）
    worker_name:
      type: string
      description: 工人姓名（add_labor 必填，wages worker 模式必填，settle 可选筛选）
    pay_type:
      type: string
      enum: [daily, hourly, piece]
      description: 计薪方式（add_labor 可选，默认从工人档案读取）
    unit_price:
      type: number
      description: 单价即日薪/时薪/件薪（add_labor 可选，默认从工人档案读取）
    quantity:
      type: number
      description: 工时数量即天数/小时数/件数（add_labor 可选，默认 1）
    query_mode:
      type: string
      enum: [unpaid, monthly, worker]
      description: |
        工资查询模式（wages 必填）：
        unpaid=查所有工人未结款汇总（如"谁还欠多少""本月未结"）
        monthly=按月份查历史账单（如"8月工资""上个月工资"），需配合 month
        worker=按工人查明细（如"张三6-8月工资""朱哥的工资明细"），需配合 worker_name
    month:
      type: string
      description: YYYY-MM 月份（wages monthly 模式必填）
    amount:
      type: number
      description: 结算金额（settle 可选，不传全额结算）
    start_date:
      type: string
      description: YYYY-MM-DD 起始日期（wages worker 模式可选，settle 可选）
    end_date:
      type: string
      description: YYYY-MM-DD 结束日期（wages worker 模式可选，settle 可选）
    skip:
      type: integer
      description: 分页偏移（query，默认 0）
    limit:
      type: integer
      description: 分页大小（query，默认 20）
  required: [operation]
---

# manage_work_orders

管理农事作业单、工时记录和工人工资查询，支持 7 种操作：
- `create` — 创建作业单（write_confirm），纯农事记录
- `add_labor` — 添加工时记录（write_confirm），记录工人出勤和应得工资（未支付）
- `wages` — 查询工人工资（read），三种模式：未结款/月度账单/工人明细
- `settle` — 月底统一结算工资（write_confirm），实际支付
- `query` — 查列表（read）
- `detail` — 查详情（read）
- `update` — 修改（write_confirm）

## 工人工资 vs 财务记账

工人工资和财务记账是**分开的两个概念**：
- **工时记录（add_labor）**：日结工今天干活了就记一条，不来干就不记。只记录出勤和应得金额，不涉及实际支付。后端自动生成未结算（unpaid）成本账单。不传 unit_price 时自动从工人档案读取日薪/时薪。
- **月底结算（settle）**：月底汇总每个工人当月所有工时，统一支付。结算后成本账单变为已结算（settled）。
- **工资查询（wages）**：查未结款汇总、按月查历史账单、按工人查明细。
- **财务记账（manage_cost）**：是实际收支流水。工人工资不通过 manage_cost 手动记账，而是通过 add_labor → settle 自动管理。

## 何时使用

- "创建一条浇水作业单" → create, operation_type=浇水, operation_date=2026-03-01
- "安排朱哥今天到草莓地育苗" → 两步：
  1. create, operation_type=育苗, operation_date=2026-08-10, cycle_id=27
  2. add_labor, work_order_id=<上一步返回的id>, worker_name=朱哥
- "记一下朱哥今天在作业单21上的工时" → add_labor, work_order_id=21, worker_name=朱哥
- "查询本月未结款" → wages, query_mode=unpaid
- "8月工资账单" → wages, query_mode=monthly, month=2026-08
- "张三6-8月工资明细" → wages, query_mode=worker, worker_name=张三, start_date=2026-06-01, end_date=2026-08-31
- "月底结算张三的工资" → settle, worker_name=张三, start_date=2026-08-01, end_date=2026-08-31
- "最近有哪些作业单" → query
- "作业单 5 的详情" → detail, work_order_id=5

## 安排工人干活的两步 HITL 流程

用户说"安排朱哥今天到草莓地育苗"时，需要两步独立审批：

1. **第一步 HITL（农事记录）**：调 create 创建作业单
   - 用户确认"朱哥今天到草莓地育苗"
   - 成功后获得 work_order_id

2. **第二步 HITL（工时记录）**：调 add_labor 记录工时
   - work_order_id=<第一步返回的id>, worker_name=朱哥
   - pay_type/unit_price 不传时自动从工人档案读取（如 daily/100）
   - quantity 默认 1
   - 用户确认"朱哥今天干活1天，应得100元"
   - 后端自动生成未结算（unpaid）成本账单

两步各自独立审批。月底用 settle 统一结算支付。

## 缺参策略

- create 缺 operation_type：从上下文推断（育苗/浇水/施肥/采摘等），否则追问
- create 缺 operation_date：默认今天
- create 缺 cycle_id：先调 query_crop_cycles 查活跃茬口
- add_labor 缺 work_order_id：先调 query 查最近作业单
- add_labor 缺 unit_price：不追问，自动从工人档案 default_unit_price 读取
- add_labor 缺 pay_type：不追问，自动从工人档案 default_pay_type 读取
- add_labor 缺 quantity：默认 1
- wages 缺 query_mode：追问是查未结款/月度账单/工人明细
- wages monthly 缺 month：默认当月
- wages worker 缺 worker_name：追问查哪个工人
- wages worker 缺 start_date/end_date：默认当月
- settle 缺 amount：全额结算
- settle 缺 start_date/end_date：默认当月

## HITL

- create/add_labor/update/settle 是 write_confirm，需用户确认
- wages/query/detail 是 read，不闸门
