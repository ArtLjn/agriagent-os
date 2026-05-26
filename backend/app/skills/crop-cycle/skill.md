---
name: get_crop_cycle_info
description: 查询种植周期（茬口）详细信息，包括阶段安排和状态。触发词: 周期、阶段、茬口、种了什么
triggers:
  - 周期
  - 阶段
  - 茬口
  - 种了什么
cache_ttl: 600
parameters:
  type: object
  properties:
    cycle_id:
      type: integer
      description: "种植周期ID"
  required:
    - cycle_id
---

# 种植周期查询

## 功能
查询种植周期的详细信息，包括名称、起止日期、地块、状态和各阶段安排。

## 参数说明
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| cycle_id | integer | 是 | 种植周期 ID |

## 示例
用户：「看一下西瓜茬口的情况」
→ get_crop_cycle_info(cycle_id=3)
