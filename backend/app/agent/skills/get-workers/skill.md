---
name: get_workers
type: read
description: 查询工人档案，默认只返回活跃工人，可按需包含已停用/离职工人。
triggers:
  - 我的工人
  - 当前工人
  - 活跃工人
  - 离职工人
parameters:
  type: object
  properties:
    active_only:
      type: boolean
      description: 是否只返回活跃工人，默认 true。
  required: []
---

# get_workers

查询工人档案，默认只返回当前活跃工人。用户明确要查看离职、停用或历史工人时才包含非活跃工人。

## 何时使用

用户询问当前工人、我的工人、有哪些工人、离职工人或已停用工人时使用。

## 不要使用

- 用户要新增、修改、停用或恢复工人时，使用 `manage_workers`。
- 用户要查询未付工资时，使用 `get_labor_payables`。
- 用户要查询作业单中的用工记录时，使用 `manage_work_orders(operation=query_work_orders)`。

## 参数推断

- “我的工人” -> `active_only=true`。
- “当前工人” -> `active_only=true`。
- “离职工人/已停用工人/历史工人” -> `active_only=false`。

## 缺参策略

无必填参数。未说明范围时默认只显示活跃工人。

## Runtime 策略

- permission: read
- direct_call: false
- direct_return: false
- cache: 使用工人上下文缓存。

## 失败处理

- 查询失败时返回中文说明，不暴露内部异常。
- 没有活跃工人时明确说明“当前没有活跃工人”。

## 示例

- 用户：“我的工人” -> 返回活跃工人列表。
- 用户：“看看离职工人” -> 返回活跃和已停用工人，并标注状态。
