---
name: delete_cost_record
type: write
description: 删除或撤销一条账务记录，执行软删除并刷新账务统计。
triggers:
  - 删除账务
  - 撤销账单
  - 删除记录
parameters:
  type: object
  properties:
    record_id:
      type: integer
      description: 账务记录 ID。
  required:
    - record_id
---

# delete_cost_record

删除或撤销一条账务记录。底层执行软删除，保留审计痕迹。

## 何时使用

用户明确要删除、撤销某条账务、账单、流水或收支记录时使用。

## 不要使用

- 用户要新增账务时使用 `create_cost_record`。
- 用户只是查询账务时使用 `get_cost_summary`。

## 参数推断

- “删除账务记录 12” -> `record_id=12`。

## 缺参策略

缺少 `record_id` 时必须追问，不要猜测最近一条。

## Runtime 策略

- permission: write_confirm
- direct_call: false
- direct_return: false
- cache: 删除成功后清理账务和农场状态缓存。

## 失败处理

找不到记录时返回中文说明。

## 示例

- 用户：“删除账务记录 12” -> 待确认后软删除记录。
