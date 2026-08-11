---
schema_version: 1
name: get_weather
kind: mcp
mcp_tool: business.get_weather
risk_level: read
description: 查询指定位置未来 1-7 天的天气预报、官方气象预警和高温大雨大风霜冻等农事风险。
triggers:
  - 天气
  - 下雨
  - 温度
  - 预报
  - 极端天气
  - 灾害预警
operations: {}
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

查询指定位置的天气预报和天气风险。结果包含未来预报、官方气象预警，以及根据温度、降水和风速推导的农事风险。
如果城市未知，工具会返回 error=unknown_location；Skill 会调用 `search_cities` 查找支持的城市，
并用返回的 `full_name` 自动重试一次。

## 何时使用

- "明天苏州什么天气"
- "最近有雨吗"
- "宁德的天气"
- "这周有没有极端天气"
- "苏州有没有灾害预警"
- "农场这边天气怎么样"（不传 location，用默认）

## error=unknown_location 处理流程

1. get_weather 返回 `{"error": "unknown_location", "hint": "call search_cities first"}`
2. 用原始地点调用 `search_cities(keyword=原 location)`
3. 如果返回非空，取第一条的 `full_name` 自动重新调用 get_weather
4. 如果返回为空，告诉用户该城市不在系统支持范围内，不要伪造天气结果

## 结果使用

- `warnings` 中的官方预警优先展示；同时保留基于预报阈值推导的高温、霜冻、大雨和大风风险。
- 未指定地点时由 Business 使用当前农场默认位置。
- 预警源暂时不可用时仍返回天气预报，不阻断主链路；此时 `warnings` 可能只包含阈值推导风险。

## 不要使用

- 用户问"农场整体情况" → 用 `get_farm_status`（已包含今日天气）
- 用户问历史天气 → 不支持，告诉用户只能查询未来预报和当前预警
- 不确定城市名是否支持时 → 先用 `search_cities` 查询
