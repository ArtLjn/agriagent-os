---
name: manage_wages
type: write
description: 保存或更新独立工资记录，并同步人工成本账单。
triggers:
  - 记工资
  - 记录工资
  - 更新工资
  - 修改工资
  - 日薪
  - 工钱改成
parameters:
  type: object
  properties:
    action:
      type: string
      description: 操作：save/update。
    labor_entry_id:
      type: integer
      description: 工资记录 ID，更新时必填。
    cycle_id:
      type: integer
      description: 茬口 ID，新增时必填。
    operation_type:
      type: string
      description: 作业类型，如采收、装车、整枝打杈。
    worker_id:
      type: integer
      description: 工人 ID。
    worker_name:
      type: string
      description: 工人姓名。
    pay_type:
      type: string
      description: 计薪方式，如 daily、hourly、piece。
    quantity:
      type: number
      description: 数量，如天数/小时/件数。
    unit_price:
      type: number
      description: 单价。
    paid_amount:
      type: number
      description: 已付金额。
    note:
      type: string
      description: 备注。
    work_date:
      type: string
      description: 作业/工资日期 YYYY-MM-DD；新增工资必填。
    client_request_id:
      type: string
      description: 幂等键；不传时由参数生成稳定键。
  required:
    - action
---

# manage_wages

保存或更新独立工资记录，并同步人工成本账单。

## 何时使用

用户明确要记录某个工人的工资，或修改已有工资记录的金额、已付金额、日期、工人、作业类型或备注时使用。

- “给老王记一笔 6 月 4 日采收工资，两天每天 180，已付 100”
- “把工资记录 12 的日薪改成 200”
- “更新老王那条工资，已付改成 150”

## 不要使用

- 用户只是查询未付工资时，使用 `get_labor_payables`。
- 用户只是结算/补付工资时，使用 `settle_labor_payment`。
- 用户是在创建农事作业单并带多个工人时，使用 `create_operation_work_order`。
- 用户只是修改工人档案默认日薪时，使用 `manage_workers`。

## 参数推断

- “记工资” -> `action=save`。
- “修改工资/更新工资/改工资” -> `action=update`。
- “日薪 180” -> `pay_type=daily`, `unit_price=180`。
- “两天” -> `quantity=2`。
- “已付 100” -> `paid_amount=100`。

## 缺参策略

- 新增工资必须有 `cycle_id`、工人、`operation_type`、`unit_price` 和 `work_date`。
- 缺少日期时必须追问，不要默认今天。
- 更新工资必须有 `labor_entry_id`；如果用户只说“老王那条”，需要先查询或追问具体记录。
- 缺少 `paid_amount` 时默认 0，缺少 `quantity` 时默认 1。

## Runtime 策略

- permission: write_confirm
- direct_call: false
- direct_return: false
- cache: 写入成功后使人工、账务和农场状态缓存失效。

## 失败处理

- 参数缺失时用中文追问必要字段。
- 找不到工资记录、工人或茬口时返回中文说明。
- 写入失败时不暴露内部异常。

## 示例

- 用户：“给老王记 2026-06-04 采收工资，两天每天 180，已付 100” -> 待确认后保存工资。
- 用户：“把工资记录 12 的日薪改成 200” -> 待确认后更新工资记录并同步人工成本。
