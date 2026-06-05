---
name: update_operation_work_order
type: write
description: 修改或纠正农事作业单的日期、类型、范围、备注和用工付款信息。
triggers:
  - 修改作业单
  - 纠正作业记录
  - 改作业日期
  - 改工人付款
parameters:
  type: object
  properties:
    work_order_id:
      type: integer
      description: 作业单 ID。
    operation_date:
      type: string
      description: 新日期 YYYY-MM-DD。
    operation_type:
      type: string
      description: 新作业类型。
    scope_type:
      type: string
      description: 范围类型 cycle、unit 或 farm。
    unit_names:
      type: string
      description: 棚或地块名称，多个用逗号分隔。
    note:
      type: string
      description: 备注。
    workers:
      type: string
      description: 工人姓名，多个用逗号分隔。
    unit_price:
      type: number
      description: 每人单价。
    payable_amount:
      type: number
      description: 每人应付金额。
    paid_amount:
      type: number
      description: 每人已付金额。
  required:
    - work_order_id
---

# update_operation_work_order

修改或纠正农事作业单的日期、类型、范围、备注和用工付款信息。此 Skill 为写操作，需要确认。

## 何时使用

用户明确要纠正、修改、补充已有农事作业单时使用，例如改日期、改作业类型、改棚号、改工人或改付款金额。

## 不要使用

- 用户要新增作业单时使用 `create_operation_work_order`。
- 用户只是查询作业单时使用 `get_operation_work_orders`。
- 用户只是支付未付人工且不改作业单内容时使用 `settle_labor_payment`。

## 参数推断

- “刚才那条授粉记录不是付老王，是付老李 200” -> 定位最近授粉作业单，改工人和已付金额。
- “把 6 月 4 的授粉改成 6 月 5” -> 修改 `operation_date`。
- “东棚改成西棚” -> 修改 `unit_names` 和 `scope_type=unit`。

## 缺参策略

- 必须有 `work_order_id` 或上游已唯一定位目标作业单。
- 无法唯一定位目标作业单时先追问，不要猜测修改。
- 金额、工人或范围表达不完整时生成待确认动作，允许用户修正。

## Runtime 策略
- permission: write_confirm
- direct_call: false
- direct_return: false
- cache: none；写入成功后使作业单、人工应付和账务相关查询缓存失效。

## 失败处理
- 无法定位唯一作业单时，用中文追问或提示用户先查询候选记录。
- 更新失败时返回中文说明和可重试建议，不暴露内部异常。

## 示例

- 用户：“刚才那条授粉记录不是付老王，是付老李 200” -> 更新作业单用工和已付金额。
- 用户：“把 12 号作业单日期改到 6 月 5 日” -> 修改作业日期。
