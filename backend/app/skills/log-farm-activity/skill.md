---
name: log_farm_activity
description: 记录农事操作（浇水、施肥、打药等），自动关联活跃茬口。触发词: 农活、浇水、施肥、打药、追肥、记录农事
triggers:
  - 农活
  - 浇水
  - 施肥
  - 打药
  - 追肥
  - 记录农事
parameters:
  type: object
  properties:
    operation_type:
      type: string
      description: "农事操作类型，如'浇水'、'施肥'、'打药'"
    operation_date:
      type: string
      description: "操作日期 YYYY-MM-DD，默认今天"
    note:
      type: string
      description: "备注详情"
    cycle_id:
      type: integer
      description: "关联的茬口ID（可选，不传则自动关联第一个活跃茬口）"
  required:
    - operation_type
---

# 记录农事

## 功能
记录农事操作（浇水、施肥、打药等），不传茬口 ID 时自动关联第一个活跃茬口。

## 参数说明
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| operation_type | string | 是 | 农事操作类型，如'浇水'、'施肥'、'打药' |
| operation_date | string | 否 | 操作日期 YYYY-MM-DD，默认今天 |
| note | string | 否 | 备注详情 |
| cycle_id | integer | 否 | 关联茬口ID，不传则自动关联第一个活跃茬口 |

## 示例
用户：「今天浇了水」
→ log_farm_activity(operation_type="浇水")
返回：「已记录：浇水（2026-05-26，关联西瓜茬口）」
