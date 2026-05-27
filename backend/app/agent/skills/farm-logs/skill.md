---
name: get_recent_farm_logs
description: 查询指定周期最近N天的农事操作记录。触发词: 农事记录、日志、最近干了什么、最近操作
triggers:
  - 农事记录
  - 日志
  - 最近干了什么
  - 最近操作
cache_ttl: 60
parameters:
  type: object
  properties:
    cycle_id:
      type: integer
      description: "种植周期ID"
    days:
      type: integer
      description: "查询天数，默认7天"
      default: 7
  required:
    - cycle_id
---

# 农事记录查询

## 功能
查询指定种植周期最近N天的农事操作记录，按日期倒序排列。

## 参数说明
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| cycle_id | integer | 是 | 种植周期 ID |
| days | integer | 否 | 查询天数，默认 7 天 |

## 示例
用户：「最近一周干了什么农活」
→ get_recent_farm_logs(cycle_id=3, days=7)
