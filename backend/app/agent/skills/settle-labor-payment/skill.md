---
name: settle_labor_payment
type: write
description: 结算或部分支付未付人工，需要确认并展示受影响人工条目。
triggers:
  - 支付人工
  - 结清人工
  - 补付工资
  - 工人工资结算
parameters:
  type: object
  properties:
    worker:
      type: string
      description: 工人姓名。
    scope:
      type: string
      description: 结算范围；all_unpaid_labor 表示全部未付人工。
    amount:
      type: number
      description: 本次支付金额，不传表示全额结清。
    cycle_id:
      type: integer
      description: 茬口 ID。
    work_order_id:
      type: integer
      description: 作业单 ID。
    start_date:
      type: string
      description: 开始日期 YYYY-MM-DD。
    end_date:
      type: string
      description: 结束日期 YYYY-MM-DD。
  required: []
---

# settle_labor_payment

结算或部分支付未付人工。此 Skill 为写操作，需要确认并展示受影响人工条目。

## 何时使用

用户明确要给工人补付、结清、部分支付人工工资时使用。

## 不要使用

- 用户只是查询欠款时使用 `get_labor_payables`。
- 用户要改作业单里的工人、单价或应付金额时使用 `manage_work_orders(operation=update_work_order)`。
- 用户要记普通成本或债务还款时不要使用本 Skill。

## 参数推断

- “给老王补付 300 人工” -> `worker=老王`, `amount=300`。
- “把作业单 12 的人工结清” -> `work_order_id=12`, 不传 `amount` 表示全额。
- “把所有员工工资结了” -> `scope=all_unpaid_labor`，不要填单个工人。
- “这批玉米的人工先付 500” -> 推断茬口并设置 `amount=500`。

## 缺参策略

- 缺少金额时按全额结清处理。
- 缺少工人、茬口或作业单时，可按当前上下文筛选；无法确定影响范围时先追问。
- 确认前必须展示受影响未付人工条目。

## Runtime 策略
- permission: write_confirm
- direct_call: false
- direct_return: false
- cache: none；写入成功后使人工应付、作业单和账务相关查询缓存失效。

## 失败处理
- 无法唯一确定结算范围时，用中文追问必要信息。
- 结算失败时返回中文说明和可重试建议，不暴露内部异常。

## 示例

- 用户：“给老王补付 300 人工” -> 生成待确认结算动作并展示受影响条目。
- 用户：“老王人工结清” -> 按老王全部未付人工结清。
