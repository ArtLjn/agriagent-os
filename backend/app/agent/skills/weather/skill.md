---
name: get_weather_forecast
type: read-only
description: 获取未来 7 天天气预报和灾害预警，包括气温、降水、风速和极端天气提醒。
triggers:
  - 天气
  - 预报
  - 降雨
  - 下雨
  - 气温
  - 极端天气
  - 灾害预警
cache_ttl: 1800
parameters:
  type: object
  properties:
    location:
      type: string
      description: "地点描述，默认当前地块或用户设置城市。"
---

# 天气预报

## 何时使用
用户询问天气、未来几天是否下雨、气温、降雨、风、极端天气或农事安排受天气影响时使用本 Skill。

## 不要使用
- 用户问实时农业新闻、政策或市场价格时，应使用搜索能力。
- 用户问农场整体状态但不聚焦天气时，可使用 `get_farm_status`。
- 用户只是问种植技术且不依赖天气时，不要强行调用天气。

## 参数推断
- “明天天气怎么样” -> 不传 `location`，使用当前地块或用户设置城市。
- “杭州未来几天下雨吗” -> `location=杭州`。
- “地里这周有没有极端天气” -> 不传 `location`，使用农场位置。

## 缺参策略
- 未说明地点时使用当前农场位置、用户设置城市或默认地块。
- 如果农场位置缺失，应在回复中提示用户完善位置。

## 多工具协作
用户问“明天适合打药吗”时，可结合天气结果和农场状态给建议。用户同时问天气和账务时，可并行调用对应 Skill。

## Runtime 策略
- permission: read
- direct_call: true
- direct_return: true
- cache: none

## 失败处理
- 地点或日期范围不明确时，用中文说明默认查询范围。
- 查询失败时返回中文说明，不暴露内部异常。

## 示例
- 用户：“明天天气怎么样” -> `get_weather_forecast()`
- 用户：“杭州未来 7 天会下雨吗” -> `get_weather_forecast(location="杭州")`
