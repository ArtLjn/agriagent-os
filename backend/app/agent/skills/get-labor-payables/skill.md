---
name: get_labor_payables
type: read-only
description: 查询未付人工明细和汇总，支持按工人、茬口、作业单与日期范围过滤。
triggers:
  - 人工欠款
  - 未付人工
  - 工资未付
  - 欠工人多少钱
parameters:
  type: object
  properties:
    worker:
      type: string
      description: 工人姓名。
    cycle_id:
      type: integer
      description: 茬口 ID。
    cycle_name:
      type: string
      description: 茬口名称。
    work_order_id:
      type: integer
      description: 作业单 ID。
    start_date:
      type: string
      description: 开始日期 YYYY-MM-DD。
    end_date:
      type: string
      description: 结束日期 YYYY-MM-DD。
    limit:
      type: integer
      description: 最多返回条数。
  required: []
---

# get_labor_payables

查询未付人工明细和汇总，支持按工人、茬口、作业单与日期范围过滤。

## 何时使用

用户询问欠某个工人多少钱、某个作业单还有多少人工未付、某段时间人工欠款时使用。

## 不要使用

- 用户要实际付款或补付人工时使用 `settle_labor_payment`。
- 用户要查询所有作业单详情时使用 `get_operation_work_orders`。
- 用户要修改作业单工人或金额时使用 `update_operation_work_order`。

## 参数推断

- “老王还欠多少人工钱” -> `worker=老王`。
- “6 月授粉还欠哪些人工” -> 推断日期范围和作业类型相关上下文。
- “作业单 12 还有未付人工吗” -> `work_order_id=12`。

## 缺参策略

- 缺少工人时返回当前筛选条件下所有未付人工。
- 缺少日期时不限制日期。
- 若没有未付条目，直接说明未找到未付人工。

## Runtime 策略
- permission: read
- direct_call: false
- direct_return: false
- cache: none

## 失败处理
- 筛选条件不明确时，用中文说明当前查询范围或追问必要信息。
- 查询失败时返回中文说明，不暴露内部异常。

## 示例

- 用户：“老王还欠多少人工钱” -> 返回应付、已付、未付和关联作业单。
- 用户：“这批玉米还有未付人工吗” -> 按茬口查询未付人工。
