## ADDED Requirements

### Requirement: 每日建议按天缓存
后端 SHALL 在处理 `GET /agent/daily` 请求时，先查询 `advice_cache` 表。当存在 farm_id + 日期 + 城市匹配的缓存记录时，直接返回缓存内容，不调用 LLM。

#### Scenario: 缓存命中
- **WHEN** 请求 `GET /agent/daily` 且 farm_id=1，城市=苏州，日期=2026-05-25，且该组合已有缓存
- **THEN** 直接返回缓存内容，HTTP 响应包含 `X-Cache: HIT` 头，LLM 调用次数为 0

#### Scenario: 缓存未命中
- **WHEN** 请求 `GET /agent/daily` 且 farm_id=1，城市=苏州，日期=2026-05-25，且该组合无缓存
- **THEN** 调用 LLM 生成建议，将结果存入 advice_cache 表，返回内容，HTTP 响应包含 `X-Cache: MISS` 头

### Requirement: 城市切换触发缓存失效
当请求的城市与缓存记录的城市不同时，SHALL 视为缓存未命中，重新生成。

#### Scenario: 不同城市无缓存
- **WHEN** 用户从苏州切换到睢宁，请求 `GET /agent/daily?city=睢宁`
- **THEN** 查询 advice_cache 中 farm_id + 日期 + 睢宁 的记录，无匹配则重新生成

#### Scenario: 不同城市有缓存
- **WHEN** 用户从苏州切换到睢宁，且睢宁今天已有缓存
- **THEN** 直接返回睢宁的缓存内容，不重新生成

### Requirement: 手动刷新缓存
后端 SHALL 提供 `POST /agent/daily/refresh` 接口，删除当天当城市的缓存并重新生成。

#### Scenario: 用户主动刷新
- **WHEN** 用户点击刷新按钮，调用 `POST /agent/daily/refresh`
- **THEN** 删除旧缓存记录，调用 LLM 生成新建议，存入缓存并返回

### Requirement: 移动端建议卡片显示刷新按钮
首页 AdviceCard 组件 SHALL 在建议内容右上角显示一个刷新图标按钮。缓存命中时建议即时显示，刷新按钮允许用户重新获取。

#### Scenario: 首次打开 app（有缓存）
- **WHEN** 用户打开 app，当天该城市已有缓存
- **THEN** 建议即时显示（无 loading），刷新按钮可点击

#### Scenario: 首次打开 app（无缓存）
- **WHEN** 用户打开 app，当天该城市无缓存
- **THEN** 显示 loading 状态，LLM 生成后显示内容

#### Scenario: 点击刷新
- **WHEN** 用户点击刷新按钮
- **THEN** 显示 loading，重新获取后更新内容

### Requirement: 缓存自动过期
advice_cache 中超过 30 天的记录 SHALL 被自动清理。

#### Scenario: 定期清理
- **WHEN** advice_cache 中存在 created_at 超过 30 天的记录
- **THEN** 下次查询时自动清理过期记录
