---
name: get_weather
kind: mcp
mcp_tool: business.get_weather
risk_level: read
description: 查询指定位置的天气预报（最多 7 天）。
triggers:
  - 天气
  - 下雨
  - 温度
  - 预报
parameters:
  type: object
  properties:
    location:
      type: string
      description: 城市名如"苏州"、"北京"。留空则用农场默认位置。
    days:
      type: integer
      description: 预报天数（1-7，默认 3）。
---

# get_weather

查询指定位置的天气预报。如果城市未知，工具会返回 error=unknown_location，
此时**必须调用 search_cities 工具**查找支持的城市，再用返回的 full_name 重新调用本工具。

## 何时使用

- "明天苏州什么天气"
- "最近有雨吗"
- "宁德的天气"
- "农场这边天气怎么样"（不传 location，用默认）

## error=unknown_location 处理流程

1. get_weather 返回 `{"error": "unknown_location", "hint": "call search_cities first"}`
2. 调用 `search_cities(keyword=原 location)` 查找相似城市
3. 如果 search_cities 返回非空，取第一条的 `full_name` 重新调 get_weather
4. 如果 search_cities 返回空，告诉用户该城市不在系统支持范围内

## 不要使用

- 用户问"农场整体情况" → 用 `get_farm_status`（已包含今日天气）
- 用户问历史天气 → 不支持，告诉用户只能预报
- 不确定城市名是否支持时 → 先用 `search_cities` 查询
