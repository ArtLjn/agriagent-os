---
name: manage_farm_logs
type: write
description: 管理农事日志，支持记录、查询、更新和删除农事操作。
triggers:
  - 记录农事操作
  - 查询农事日志
  - 修改农事记录
  - 删除农事记录
  - 更正农事日志
parameters:
  type: object
  properties:
    operation:
      type: string
      description: 操作类型：create_log/query_logs/manage_log。
    action:
      type: string
      description: manage_log 下的操作：update/delete。
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
    days:
      type: integer
      description: 查询最近天数，默认 7。
  required:
    - operation
---

# manage_farm_logs

管理农事日志，聚合新增记录、最近查询、更新和删除。

## 何时使用

用户要记录浇水、施肥、打药、除草、翻地等农事操作，查询最近农事日志，或明确要修改、更正、删除已有农事记录时使用。

## 不要使用

用户要创建农事作业单、安排工人干活或结算人工时不要使用，应使用作业单或人工相关 Skill。

## 参数推断

- “今天浇水了” -> `operation=create_log`, `operation_type=浇水`。
- “昨天给 3 号棚打药防蚜虫” -> `operation=create_log`, `cycle_id=3`, `operation_type=打药`, `operation_date=昨天`, `note=防蚜虫`。
- “最近 7 天农事日志” -> `operation=query_logs`, `days=7`。
- “3 号茬口最近一周干了什么” -> `operation=query_logs`, `cycle_id=3`, `days=7`。
- “把农事日志 8 改成施肥” -> `operation=manage_log`, `action=update`, `log_id=8`, `operation_type=施肥`。
- “删除农事记录 8” -> `operation=manage_log`, `action=delete`, `log_id=8`。

## 缺参策略

缺少 `operation` 时追问要记录、查询、更新还是删除。`create_log` 缺少 `operation_type` 时提示补充；`manage_log` 缺少 `log_id` 时追问，不要猜测最近一条。

## Runtime 策略

- permission: operation-aware
- direct_call: false
- direct_return: false
- cache: create_log/manage_log 写入成功后刷新农事和农场状态缓存；query_logs 为 read。

## 失败处理

找不到日志或茬口时返回中文说明。

## 示例

- 用户：“今天浇水了” -> `manage_farm_logs(operation="create_log", operation_type="浇水")`
- 用户：“最近 7 天农事日志” -> `manage_farm_logs(operation="query_logs", days=7)`
- 用户：“删除 8 号农事日志” -> 待确认后删除。
