---
name: get_weather_forecast
description: 获取未来7天天气预报和灾害预警。触发词: 天气、预报、降雨、下雨、气温
triggers:
  - 天气
  - 预报
  - 降雨
  - 下雨
  - 气温
cache_ttl: 1800
parameters:
  type: object
  properties:
    location:
      type: string
      description: "地点描述（默认'当前地块'）"
---

# 天气预报

## 功能
获取未来7天天气预报，包含每日气温、降水、风速数据，以及灾害预警检查。

## 参数说明
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| location | string | 否 | 地点描述，默认"当前地块" |

## 示例
用户：「明天天气怎么样」
→ get_weather_forecast()
