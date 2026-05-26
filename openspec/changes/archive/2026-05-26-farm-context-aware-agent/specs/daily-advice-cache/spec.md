## MODIFIED Requirements

### Requirement: 每日建议按天缓存
后端 SHALL 在处理 `GET /agent/daily` 请求时，先查询 `advice_cache` 表。当存在 farm_id + 日期 + 城市匹配的缓存记录时，直接返回缓存内容，不调用 LLM。

#### Scenario: 缓存命中（多茬口模式）
- **WHEN** 请求 `GET /agent/daily` 且 farm_id=1，城市=苏州，日期=2026-05-25，且该组合已有缓存
- **THEN** 直接返回缓存内容，HTTP 响应包含 `X-Cache: HIT` 头，LLM 调用次数为 0，返回内容包含所有 active 茬口的建议

#### Scenario: 缓存未命中（多茬口模式）
- **WHEN** 请求 `GET /agent/daily` 且 farm_id=1，城市=苏州，日期=2026-05-25，且该组合无缓存
- **THEN** 查询农场所有 active 茬口，组装上下文摘要，调用 LLM 生成多作物建议，将结果存入 advice_cache 表

### Requirement: 城市切换触发缓存失效
当请求的城市与缓存记录的城市不同时，SHALL 视为缓存未命中，重新生成。

#### Scenario: 不同城市无缓存（多茬口）
- **WHEN** 用户从苏州切换到睢宁，请求 `GET /agent/daily?city=睢宁`
- **THEN** 查询 advice_cache 中 farm_id + 日期 + 睢宁 的记录，无匹配则重新生成（生成时基于当前 active 茬口）

## ADDED Requirements

### Requirement: 每日建议支持无 cycle_id 模式
`GET /agent/daily` SHALL 支持不传 `cycle_id`，此时自动查询农场的所有 active 茬口并生成汇总建议。

#### Scenario: 无 cycle_id 请求
- **WHEN** 请求 `GET /agent/daily` 不带 cycle_id 参数
- **THEN** 后端查询该农场所有 `status=active` 的茬口，为每个茬口生成建议，合并为一份多作物建议返回

#### Scenario: 有 cycle_id 请求（保持兼容）
- **WHEN** 请求 `GET /agent/daily?cycle_id=123`
- **THEN** 按原有逻辑为该单个茬口生成建议，保持向后兼容

### Requirement: 缓存键包含活跃茬口列表
缓存键 SHALL 包含当前活跃茬口 ID 列表，确保茬口变化时缓存自动失效。

#### Scenario: 新增茬口后缓存失效
- **WHEN** 用户新建了一个 active 茬口后请求每日建议
- **THEN** 活跃茬口列表变化，视为缓存未命中，重新生成建议
