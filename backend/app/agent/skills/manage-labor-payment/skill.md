---
name: manage_labor_payment
type: write
description: 管理人工付款，支持查询未付人工、结算或补付工资、保存或更新独立工资记录。
domain: labor
capability: manage_labor_payment
triggers:
  - 未付人工
  - 人工欠款
  - 补付工资
  - 工资结清
  - 记录工资
  - 修改工资
parameters:
  type: object
  properties:
    operation:
      type: string
      description: 操作：query_payables、settle_payment 或 manage_wage。
      enum:
        - query_payables
        - settle_payment
        - manage_wage
    action:
      type: string
      description: 工资记录操作：save/update。
    worker:
      type: string
      description: 工人姓名。
    worker_id:
      type: integer
      description: 工人 ID。
    worker_name:
      type: string
      description: 工人姓名。
    labor_entry_id:
      type: integer
      description: 工资记录 ID，更新工资时必填。
    scope:
      type: string
      description: 结算范围；all_unpaid_labor 表示全部未付人工。
    amount:
      type: number
      description: 本次结算金额，不传表示全额结清。
    cycle_id:
      type: integer
      description: 茬口 ID。
    cycle_name:
      type: string
      description: 茬口名称。
    work_order_id:
      type: integer
      description: 作业单 ID。
    operation_type:
      type: string
      description: 工资作业类型，如采收、装车、整枝打杈。
    pay_type:
      type: string
      description: 计薪方式，如 daily、hourly、piece。
    quantity:
      type: number
      description: 工资数量，如天数/小时/件数。
    unit_price:
      type: number
      description: 工资单价。
    paid_amount:
      type: number
      description: 工资记录已付金额。
    note:
      type: string
      description: 工资记录备注。
    work_date:
      type: string
      description: 作业/工资日期 YYYY-MM-DD；新增工资必填。
    start_date:
      type: string
      description: 查询开始日期 YYYY-MM-DD。
    end_date:
      type: string
      description: 查询结束日期 YYYY-MM-DD。
    limit:
      type: integer
      description: 查询最多返回条数。
    client_request_id:
      type: string
      description: 工资记录幂等键。
  required: []
---

# manage_labor_payment

管理人工付款业务能力。一个物理 Skill 覆盖查询未付人工、结算或补付人工工资、保存或更新独立工资记录。

## 何时使用

用户询问人工欠款、未付工资、工钱未付时，使用 `operation=query_payables`。用户明确要补付、支付、结清或结算人工工资时，使用 `operation=settle_payment`。用户明确要新增、保存、记录或修改某条工资记录时，使用 `operation=manage_wage`。

## 不要使用

- 用户要新增、修改、停用工人档案时，使用 `manage_workers`。
- 用户是在创建农事作业单并同时记录多个工人时，使用 `manage_work_orders(operation=create_work_order)`。
- 用户查询或结清农资赊账、普通欠款时，使用 `manage_cost`。
- 无法判断是结算工资还是新增工资记录时，不要猜测写入，先追问。

## 参数推断

- “还欠多少人工钱/未付工资” -> `operation=query_payables`。
- “老王还欠多少人工钱” -> `operation=query_payables`, `worker=老王`。
- “给老王补付 300 人工” -> `operation=settle_payment`, `worker=老王`, `amount=300`。
- “把作业单 12 的人工结清” -> `operation=settle_payment`, `work_order_id=12`。
- “把所有员工工资结了” -> `operation=settle_payment`, `scope=all_unpaid_labor`。
- “给李海记 15 天压瓜工资每天 180” -> `operation=manage_wage`, `action=save`, `worker_name=李海`, `quantity=15`, `operation_type=压瓜`, `unit_price=180`。
- “把工资记录 12 的日薪改成 200” -> `operation=manage_wage`, `action=update`, `labor_entry_id=12`, `unit_price=200`。

## 缺参策略

- 空参数、纯查询筛选参数或只带 `worker/cycle_id/cycle_name/work_order_id/start_date/end_date/limit` 时，默认按 `query_payables` 查询，不进入写确认。
- `settle_payment` 缺少金额时按全额结清处理；缺少明确范围且上下文无法确定时先追问。
- `manage_wage` 新增工资必须有 `cycle_id`、工人、`operation_type`、`unit_price` 和 `work_date`。
- `manage_wage` 更新工资必须有 `labor_entry_id`。
- 同时出现结算字段和工资记录字段且没有显式 `operation` 时，返回澄清，不能随便创建或结算。

## Runtime 策略

- permission: operation-aware
- direct_call: 查询可直接执行；结算和工资记录写入必须进入确认。
- direct_return: false
- cache: 写入成功后清理人工、账务汇总、收支分析和农场状态缓存。

## 失败处理

- 参数缺失时用中文追问必要字段。
- 找不到工资记录、工人、茬口或未付人工时返回中文说明。
- 数据库或业务服务失败时返回中文说明，不暴露内部异常。

## 示例

- 用户：“还欠多少人工钱” -> 查询未付人工汇总。
- 用户：“给老王补付 300 人工” -> 待确认后结算人工付款。
- 用户：“给李海记 15 天压瓜工资每天 180” -> 待确认后保存工资记录并同步成本。
