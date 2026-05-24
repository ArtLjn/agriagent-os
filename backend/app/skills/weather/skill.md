---
name: get_weather_forecast
description: 获取未来7天天气预报和灾害预警
triggers:
  - 天气
  - 预报
  - 降雨
cache_ttl: 1800
---

# 天气预报 Skill

## 功能
获取未来7天天气预报，包含每日气温、降水、风速数据，以及灾害预警检查。

## 参数
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| location | string | 否 | 地点描述（默认"当前地块"） |

## 缓存策略
- TTL: 1800s (30分钟)
- Key: skill_name + params hash

## 数据源
- Open-Meteo API (通过 app.services.weather_service)
