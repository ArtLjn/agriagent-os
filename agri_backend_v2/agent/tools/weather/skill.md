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
      description: 要查询的城市或区县，如"苏州"、"北京"。用户明确指定时必须按指定地点查询；留空时由 Skill 先读取当前用户设置中的 default_city，再将该城市传给 Business；用户未配置默认城市时才回退农场位置。
    days:
      type: integer
      description: 预报天数（1-7，默认 3）。
---

# get_weather

查询指定位置的天气预报和天气风险。结果包含未来预报、官方气象预警，以及根据温度、降水和风速推导的农事风险。
未指定地点时，Skill 会先从用户原话解析并确认明确城市；没有明确城市时再读取当前用户设置中的默认城市；如果没有默认城市，
才允许 Business 使用农场位置兼容兜底。用户明确指定城市时不得读取默认位置替换它。

如果城市未知，工具会返回 error=unknown_location；Skill 会调用 `search_cities` 查找支持的城市，
并用返回的 `full_name` 自动重试一次。

## 何时使用

- "明天苏州什么天气"
- "最近有雨吗"
- "宁德的天气"
- "这周有没有极端天气"
- "苏州有没有灾害预警"
- "农场这边天气怎么样"（不传 location，由 Skill 先读取当前用户设置的默认位置）
- "北京明天什么天气"（传 `location="北京"`，查询用户指定地点，不使用默认位置）

## error=unknown_location 处理流程

1. get_weather 返回 `{"error": "unknown_location", "hint": "call search_cities first"}`
2. 用原始地点调用 `search_cities(keyword=原 location)`
3. 如果返回非空，取第一条的 `full_name` 自动重新调用 get_weather
4. 如果返回为空，告诉用户该城市不在系统支持范围内，不要伪造天气结果

## 地点解析流程

1. 用户明确说出城市或区县时，直接使用该地点查询，不调用默认位置覆盖。
2. 模型漏传 `location` 时，先用用户原话调用 location Skill；查到明确城市就用返回的 `full_name` 查询。
3. 用户原话没有明确城市时，再查询当前用户设置；若存在 `default_city`，调用天气工具时必须传 `location=default_city`。
4. 用户没有默认城市时，才允许传空地点让 Business 回退农场位置。
5. 默认位置只影响本次未指定地点的查询，不限制用户查询其他城市，也不会修改用户设置。

## 结果使用

- `warnings` 中的官方预警优先展示；同时保留基于预报阈值推导的高温、霜冻、大雨和大风风险。
- 未指定地点时由 Skill 先读取当前用户设置中的 `default_city` 并显式传给 Business；用户设置未配置时才回退当前农场位置和系统默认坐标。
- 用户明确指定 `location` 时，始终查询用户指定的城市或区县，不被用户默认位置覆盖，也不修改用户默认位置。
- 默认位置只用于补全未提供的 `location`，不是查询范围限制；用户可以随时查询其他城市天气。
- 预警源暂时不可用时仍返回天气预报，不阻断主链路；此时 `warnings` 可能只包含阈值推导风险。

## 不要使用

- 用户问"农场整体情况" → 用 `get_farm_status`（已包含今日天气）
- 用户问历史天气 → 不支持，告诉用户只能查询未来预报和当前预警
- 不确定城市名是否支持时 → 先用 `search_cities` 查询
- 用户明确指定其他城市时 → 按指定城市查询，不要强行改用默认位置
