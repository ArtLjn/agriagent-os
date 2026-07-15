---
name: manage_work_orders
type: write
description: 管理农事作业单，支持创建、查询和修改作业单。
triggers:
  - 创建农事作业单
  - 查询农事作业单
  - 修改农事作业单
parameters:
  type: object
  properties:
    operation:
      type: string
      description: 操作：create_work_order/query_work_orders/update_work_order。
    work_order_id:
      type: integer
      description: 作业单 ID。
    operation_type:
      type: string
      description: 作业类型。
    operation_date:
      type: string
      description: 作业日期，YYYY-MM-DD。
    cycle_id:
      type: integer
      description: 茬口 ID。
    crop_cycle_name:
      type: string
      description: 茬口名称。
    unit_names:
      type: string
      description: 棚、地块或种植单元名称，多个用逗号分隔。
    unit_name:
      type: string
      description: 查询用棚、地块或种植单元名称。
    worker:
      type: string
      description: 查询用工人姓名。
    workers:
      type: string
      description: 作业工人姓名，多个用逗号分隔。
    start_date:
      type: string
      description: 查询开始日期，YYYY-MM-DD。
    end_date:
      type: string
      description: 查询结束日期，YYYY-MM-DD。
    payment_status:
      type: string
      description: 付款状态。
    limit:
      type: integer
      description: 最多返回条数。
    unit_price:
      type: number
      description: 每名工人单价。
    quantity:
      type: number
      description: 计薪数量。
    paid_worker:
      type: string
      description: 已付款工人姓名。
    paid_amount:
      type: number
      description: 已付金额。
    payable_amount:
      type: number
      description: 应付金额。
    note:
      type: string
      description: 备注。
  required:
    - operation
---

# manage_work_orders

管理农事作业单，覆盖创建、查询和修改。

## 何时使用

用户要记录一次采收、授粉、压蔓、装车等农事作业时，使用 `operation=create_work_order`。
用户要查看最近或指定条件下的作业单时，使用 `operation=query_work_orders`。
用户要更正已有作业单的日期、范围、备注、工人或金额时，使用 `operation=update_work_order`。

## 不要使用

用户只是在记录普通农事日志时使用 `log_farm_activity`。用户要管理工人档案时使用 `manage_workers`。用户要结清人工工资时使用 `manage_labor_payment(operation=settle_payment)`。

## 参数推断

- “今天李树去6号棚收水稻” -> `operation=create_work_order`, `operation_type=采收`, `workers=李树`, `unit_names=6号棚`。
- “最近玉米授粉作业有哪些” -> `operation=query_work_orders`, `operation_type=授粉`, `cycle_name=玉米`。
- “修改昨天的作业单备注” -> `operation=update_work_order`, 需要先定位 `work_order_id`，再传 `note`。
- “把5号棚采收作业改到明天” -> `operation=update_work_order`, 需要定位 `work_order_id`，再传 `operation_date` 和 `unit_names=5号棚`。

## 缺参策略

创建作业单缺少 `operation_type` 时追问。创建作业单带工人但没有工资，且工人档案也没有默认工资时追问；不要默认记为 0。修改作业单缺少 `work_order_id` 或无法唯一定位时追问。查询条件不足时可以返回最近匹配记录。

## Runtime 策略

- permission: `operation=query_work_orders` 为 read；`operation=create_work_order/update_work_order` 为 write_confirm
- direct_call: false
- direct_return: false
- cache: 创建或修改成功后刷新农事、成本和农场状态缓存。

## 失败处理

找不到茬口、棚区、作业单或工人信息不足时返回中文说明。内部异常只返回可理解的失败原因，不暴露堆栈。

## 示例

- 用户：“今天李树去6号棚收水稻” -> 待确认后创建采收作业单。
- 用户：“最近玉米授粉作业有哪些” -> 直接查询授粉作业单。
- 用户：“修改昨天的作业单备注” -> 定位作业单后待确认修改备注。
- 用户：“把5号棚采收作业改到明天” -> 定位作业单后待确认修改日期。
