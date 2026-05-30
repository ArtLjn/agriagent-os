## Context

当前天气请求链路：前端/Agent → 后端 API → strategy.fetch() → QWeather/Open-Meteo（日预报+实时温度并行） + 气象局预警（并行）。刚完成并行优化后单次请求 ~1-3s，但每次都打外部 API，高频场景下仍有延迟和配额浪费。

现有一个 `skill_cache.py` 用于 Skill 层结果缓存（30 分钟 TTL），但 API 层和 Strategy 层无缓存。

## Goals / Non-Goals

**Goals:**
- 后端 `/weather/forecast` 响应级缓存，同一城市 10 分钟内直接返回
- 预警数据独立缓存 30 分钟（预警变化频率低）
- 前端 AsyncStorage 缓存天气数据，App 打开秒出
- 缓存对上层透明，无 API 接口变化

**Non-Goals:**
- 不做分布式缓存（Redis 等），项目规模不需要
- 不做缓存预热，首次请求仍走外部 API
- 不改缓存失效策略（纯 TTL 过期）

## Decisions

### 1. 缓存层级：Strategy 层而非 API 层

**选择**：在 `strategy.fetch()` 返回后、`_to_legacy_format()` 前缓存 `WeatherData` 对象。

**理由**：
- 缓存原始数据（WeatherData），多个消费者（API、Skill）都可复用
- 避免 API 层缓存 dict 格式与 Skill 层缓存 SkillResult 格式不一致
- 与现有 `skill_cache.py` 解耦，各管各的

### 2. 缓存实现：进程内 dict + TTL

**选择**：用简单的 `{key: (value, expire_at)}` 字典，和 `skill_cache.py` 同模式。

**替代方案**：`cachetools.TTLCache` — 引入额外依赖，项目规模不需要。

### 3. 缓存 Key：`(location, days)`

**选择**：以城市名 + 天数组合作为缓存 key。有坐标时也包含坐标，确保精度。

### 4. 前端缓存：AsyncStorage + 后台刷新

**选择**：`useAgentStore` 中 weather 数据写入 AsyncStorage，打开 App 时先读缓存立即渲染，同时发起网络请求刷新。

**理由**：用户体验优先 — 秒出内容，后台更新后静默替换。

## Risks / Trade-offs

- **[缓存数据过期]** → TTL 设置保守（预报 10min、预警 30min），天气变化频率远低于此
- **[内存占用]** → 每条缓存 ~2KB，100 个城市也只占 200KB，进程重启自动清理
- **[前端展示过期数据]** → 缓存时间戳展示在 UI 上，用户可感知数据新鲜度；后台静默刷新保证最终一致
