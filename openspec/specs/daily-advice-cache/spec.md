## Requirements

### Requirement: 每日建议按天缓存
后端 SHALL 在处理 `GET /agent/daily` 请求时，先查询 `advice_cache` 表。当存在 farm_id + 日期 + 城市 + 活跃茬口ID列表 匹配的缓存记录时，直接返回缓存内容，不调用 LLM。

#### Scenario: 缓存命中（茬口不变）
- **WHEN** 请求 `GET /agent/daily` 且 farm_id=1，城市=苏州，日期=2026-05-25，活跃茬口为 [1,2]，且该组合已有缓存
- **THEN** 直接返回缓存内容，HTTP 响应包含 `X-Cache: HIT` 头，LLM 调用次数为 0

#### Scenario: 缓存未命中（茬口变化）
- **WHEN** 请求 `GET /agent/daily` 且 farm_id=1，城市=苏州，日期=2026-05-25，但活跃茬口从 [1,2] 变为 [1,2,3]
- **THEN** 视为缓存未命中，重新生成建议

#### Scenario: 缓存未命中（日期变化）
- **WHEN** 请求 `GET /agent/daily` 且 farm_id=1，城市=苏州，日期=2026-05-26（新的一天）
- **THEN** 视为缓存未命中，重新生成建议

#### Scenario: 缓存未命中
- **WHEN** 请求 `GET /agent/daily` 且 farm_id=1，城市=苏州，日期=2026-05-25，且该组合无缓存
- **THEN** 调用 LLM 生成建议，将结果存入 advice_cache 表，返回内容，HTTP 响应包含 `X-Cache: MISS` 头

### Requirement: 缓存内容改为结构化 JSON
advice_cache 表中存储的内容 SHALL 从纯文本 Markdown 改为 `DailyAdviceResponse` 的 JSON 序列化。

#### Scenario: 写入缓存
- **WHEN** LLM 生成结构化建议后存入缓存
- **THEN** 缓存内容为 `{"items": [{"title":"...","detail":"...","priority":1,"icon":"🌡️"}]}` 格式

#### Scenario: 读取旧格式缓存
- **WHEN** 缓存中存在旧的纯文本格式内容
- **THEN** 后端 fallback 将纯文本包装为单条 AdviceItem 返回
