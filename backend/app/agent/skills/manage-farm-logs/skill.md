---
name: manage_farm_logs
type: write
description: 更新或删除已有农事日志。
triggers:
  - 修改农事记录
  - 删除农事记录
  - 更正农事日志
parameters:
  type: object
  properties:
    action:
      type: string
      description: 操作：update/delete。
    log_id:
      type: integer
      description: 农事日志 ID。
    cycle_id:
      type: integer
      description: 茬口 ID。
    operation_type:
      type: string
      description: 操作类型。
    operation_date:
      type: string
      description: 操作日期，YYYY-MM-DD。
    operation_time:
      type: string
      description: 操作时间。
    note:
      type: string
      description: 备注。
    photo_urls:
      type: string
      description: 图片 URL 列表字符串。
  required:
    - action
---

# manage_farm_logs

更新或删除已有农事日志。

## 何时使用

用户明确要修改、更正或删除已有农事记录、农事日志、操作记录时使用。

## 不要使用

用户要新增农事记录时使用 `log_farm_activity`；用户只是查询最近记录时使用 `get_recent_farm_logs`。

## 参数推断

- “把农事日志 8 改成施肥” -> `action=update`, `log_id=8`, `operation_type=施肥`。
- “删除农事记录 8” -> `action=delete`, `log_id=8`。

## 缺参策略

缺少 `log_id` 时追问，不要猜测最近一条。

## Runtime 策略

- permission: write_confirm
- direct_call: false
- direct_return: false
- cache: 写入成功后刷新农事和农场状态缓存。

## 失败处理

找不到日志或茬口时返回中文说明。

## 示例

- 用户：“删除 8 号农事日志” -> 待确认后删除。
