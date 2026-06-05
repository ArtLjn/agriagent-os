---
name: get_recent_farm_logs
type: read-only
description: 查询指定种植周期最近 N 天的农事操作记录。
triggers:
  - 农事记录
  - 日志
  - 最近干了什么
  - 最近操作
  - 农活记录
cache_ttl: 60
parameters:
  type: object
  properties:
    cycle_id:
      type: integer
      description: "种植周期 ID。当前实现需要明确 ID。"
    days:
      type: integer
      description: "查询天数，默认 7 天。"
      default: 7
  required:
    - cycle_id
---

# 农事记录查询

## 何时使用
用户查询最近农事、操作日志、某个周期最近几天做了什么时使用本 Skill。

## 不要使用
- 用户要新增农事记录时，应使用 `log_farm_activity`。
- 用户问农场整体状态时，可使用 `get_farm_status`。
- 用户没有指定周期且上下文中无法确定周期时，不要编造 `cycle_id`。

## 参数推断
- “3 号茬口最近一周干了什么” -> `cycle_id=3`, `days=7`。
- “周期 2 最近 3 天操作” -> `cycle_id=2`, `days=3`。

## 缺参策略
- 未说明天数时默认 7 天。
- 缺少 `cycle_id` 时，可先用 `get_farm_status` 获取活跃茬口，仍不确定则追问。

## 多工具协作
当用户问“最近农场整体做了什么”，可先用 `get_farm_status`；当用户指定具体周期，再用本 Skill 返回明细。

## Runtime 策略
- permission: read
- direct_call: false
- direct_return: false
- cache: none

## 失败处理
- 无法确定茬口或时间范围时，用中文说明默认范围或追问。
- 查询失败时返回中文说明，不暴露内部异常。

## 示例
- 用户：“3 号茬口最近一周干了什么” -> `get_recent_farm_logs(cycle_id=3, days=7)`
