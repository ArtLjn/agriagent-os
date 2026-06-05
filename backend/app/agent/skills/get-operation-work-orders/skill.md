---
name: get_operation_work_orders
type: read-only
description: 查询农事作业单，支持按茬口、种植单元、作业类型、工人、日期范围和付款状态筛选。
triggers:
  - 查询作业单
  - 作业记录
  - 农事作业
  - 工人参与记录
parameters:
  type: object
  properties:
    cycle_id:
      type: integer
      description: 茬口 ID。
    cycle_name:
      type: string
      description: 茬口名称。
    unit_id:
      type: integer
      description: 种植单元 ID。
    unit_name:
      type: string
      description: 棚或地块名称。
    operation_type:
      type: string
      description: 作业类型。
    worker:
      type: string
      description: 工人姓名。
    start_date:
      type: string
      description: 开始日期 YYYY-MM-DD。
    end_date:
      type: string
      description: 结束日期 YYYY-MM-DD。
    payment_status:
      type: string
      description: 付款状态：unpaid、partial、settled、has_unpaid。
    limit:
      type: integer
      description: 最多返回条数。
  required: []
---

# get_operation_work_orders

查询农事作业单，支持按茬口、种植单元、作业类型、工人、日期范围和付款状态筛选。

## 何时使用

用户询问最近、某个茬口、某个棚、某类作业或某个工人参与过哪些农事作业时使用。

## 不要使用

- 用户要新增作业单时使用 `create_operation_work_order`。
- 用户要纠正已有作业单时使用 `update_operation_work_order`。
- 用户只问未付人工总额时优先使用 `get_labor_payables`。

## 参数推断

- “最近玉米授粉作业有哪些” -> `operation_type=授粉`, `cycle_name=玉米`。
- “老王参与的压蔓记录” -> `worker=老王`, `operation_type=压蔓`。
- “上周东棚作业” -> 推断 `unit_name=东棚` 和日期范围。

## 缺参策略

- 缺少日期范围时按服务默认排序返回最近记录。
- 茬口、棚和工人名称可用模糊匹配。
- 用户表达付款状态时映射为 `unpaid`、`partial`、`settled` 或 `has_unpaid`。

## Runtime 策略
- permission: read
- direct_call: false
- direct_return: false
- cache: none

## 失败处理
- 筛选条件不完整时，用中文说明已采用的默认查询范围。
- 查询失败时返回中文说明，不暴露内部异常。

## 示例

- 用户：“最近玉米授粉作业有哪些” -> 返回日期、范围、工人和付款摘要。
- 用户：“东棚还有哪些未结清的作业单” -> 按棚和未结清状态查询。
