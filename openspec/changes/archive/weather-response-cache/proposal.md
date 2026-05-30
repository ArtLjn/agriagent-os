## Why

每次打开 App 或 Agent 聊天触发天气查询时，后端都会实时请求外部 API（和风天气 / Open-Meteo / 气象局预警），平均耗时 2-4 秒。用户频繁操作时体验卡顿，且浪费 API 配额。天气数据更新频率低（预报 10-30 分钟才变化），预警更新更慢，适合缓存。

## What Changes

- 后端 `/weather/forecast` API 增加内存级 TTL 缓存，按 `(city, days)` 维度缓存完整响应，10 分钟内命中缓存直接返回
- 后端预警数据独立缓存（30 分钟 TTL），与预报缓存解耦
- Skill 层已有的 30 分钟缓存保留，但复用底层预报缓存避免重复外部请求
- 前端打开 App 时先展示 AsyncStorage 缓存的天气数据，后台静默刷新

## Capabilities

### New Capabilities
- `weather-response-cache`: 后端天气 API 响应级缓存 + 前端天气数据持久化缓存

### Modified Capabilities
- `agent-weather-context`: Agent 上下文注入天气时优先走缓存，减少延迟

## Impact

- 后端：`weather_service.py`、`strategy.py` 增加缓存层，无 API 接口变化
- 前端：`agentStore.ts` 增加 AsyncStorage 缓存逻辑，无 UI 变化
- 无 breaking change，缓存对上层透明
