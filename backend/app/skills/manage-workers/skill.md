---
name: manage_workers
type: write
description: 查询、创建、更新、停用或恢复工人档案；删除语义为停用/离职并保留历史用工。
triggers:
  - 我的工人
  - 创建工人
  - 招工人
  - 修改工人
  - 停用工人
  - 离职工人
parameters:
  type: object
  properties:
    action:
      type: string
      description: 操作：query/create/update/deactivate/restore。
    operation:
      type: string
      description: 能力操作：query_workers 或 manage_worker。
    active_only:
      type: boolean
      description: 查询时是否只返回活跃工人，默认 true。
    worker_id:
      type: integer
      description: 工人 ID。
    name:
      type: string
      description: 工人姓名。
    phone:
      type: string
      description: 手机号。
    default_pay_type:
      type: string
      description: 默认计薪方式，如 daily、hourly、piece。
    default_unit_price:
      type: number
      description: 默认单价，如日薪 150。
    note:
      type: string
      description: 备注。
    status:
      type: string
      description: 状态 active 或 inactive。
  required: []
---

# manage_workers

查询、创建、更新、停用或恢复工人档案。工人删除统一按停用/离职处理，保留历史用工、作业单和账务。

## 何时使用

用户查询当前工人、离职工人，或明确要创建、修改、停用、恢复工人档案时使用。

- “我的工人” -> 查询活跃工人。
- “看看离职工人” -> 查询活跃和已停用工人。
- “招了李四，日薪 150” -> 创建工人。
- “把李四日薪改成 180” -> 更新工人。
- “李四不用了/离职了/删除李四” -> 停用工人。
- “李四又回来了” -> 恢复工人。

## 不要使用

- 用户记录一次具体农事作业和用工时，优先使用 `manage_work_orders(operation=create_work_order)`。
- 用户查询未付工资或结算工资时，使用 `manage_labor_payment`。
- 用户只是在普通对话中提到人名，但没有工人档案意图时，不要创建工人。

## 参数推断

- “我的工人” -> `operation=query_workers`, `active_only=true`。
- “当前工人” -> `operation=query_workers`, `active_only=true`。
- “离职工人/已停用工人/历史工人” -> `operation=query_workers`, `active_only=false`。
- “招了李四，日薪 150” -> `action=create`, `name=李四`, `default_pay_type=daily`, `default_unit_price=150`。
- “删除李四” -> `action=deactivate`, `name=李四`，确认文案必须说“停用/离职”，不要说数据库删除。
- “恢复李四” -> `action=restore`, `name=李四`。
- 修改已有工人时，优先使用上下文工人档案中的 `worker_id`；如果只传姓名，必须传完整姓名。
- 工人姓名必须按用户原话和工人档案完整保留，不要把“刘俊男”截成“刘俊”，也不要把姓名末尾的“男/女/师傅/姐/哥”等字符当成描述词删除。

## 缺参策略

- 查询无必填参数。没有 `operation/action` 且没有写字段时，默认按 `query_workers` 查询活跃工人。
- 写操作缺少工人姓名和 `worker_id` 时必须追问。
- 创建工人缺少工资时可以创建，但确认文案必须展示“默认单价未设置”。
- 遇到已停用同名工人时，先追问恢复还是新建同名工人。
- 不要把入职时间、负责茬口或地块当作已存在字段写入备注，除非用户明确要求写入备注。

## Runtime 策略

- permission: write_confirm；单次调用如果是 `operation=query_workers` 或 `action=query`，按 read 风险处理。
- direct_call: false
- direct_return: false
- cache: 写入成功后使工人、人工和农场状态上下文失效。

## 失败处理

- 找不到工人时，用中文提示用户提供姓名或 ID。
- 参数非法时返回中文说明，不暴露内部异常。
- 停用工人时说明历史用工和账务会保留。

## 示例

- 用户：“我的工人” -> 返回活跃工人列表。
- 用户：“看看离职工人” -> 返回活跃和已停用工人，并标注状态。
- 用户：“我招了李四，日薪 150” -> 待确认后创建李四。
- 用户：“删除李四” -> 待确认后停用李四并保留历史记录。
