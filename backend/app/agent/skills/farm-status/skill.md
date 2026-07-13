---
name: get_farm_status
type: read-only
description: 获取当前农场综合状态摘要，包括活跃茬口、近期农事、欠账、月度花费和天气。
triggers:
  - 农场
  - 茬口状态
  - 种植情况
  - 农事
  - 综合状态
  - 整体情况
  - 建议
cache_ttl: 300
parameters:
  type: object
  properties: {}
---

# 农场状态查询

## 何时使用
用户问农场整体情况、当前种植状态、最近农事、活跃茬口、综合建议或需要上下文概览时使用本 Skill。

## 不要使用
- 用户只问精确账单或流水时，应使用 `manage_cost(operation="query_summary")`。
- 用户只问天气时，应使用 `get_weather_forecast`。
- 用户要新增记录或创建茬口时，不要使用本 Skill 代替写入 Skill。

## 参数推断
本 Skill 无参数。用户说“我的农场现在怎么样”“当前茬口状态”“整体情况”时直接调用。

## 缺参策略
无参数。如果缺少可信农场上下文，执行结果应提示无法获取农场信息。

## 多工具协作
本 Skill 适合作为上下文补充。账单、天气、农事明细等精确问题，应结合对应专用 Skill。

## Runtime 策略
- permission: read
- direct_call: true
- direct_return: false
- cache: none

## 失败处理
- 缺少可信农场上下文时，用中文说明无法获取当前农场信息。
- 查询失败时返回中文说明，不暴露内部异常。

## 示例
- 用户：“我的农场现在怎么样” -> `get_farm_status()`
- 用户：“给我看看整体种植情况” -> `get_farm_status()`
