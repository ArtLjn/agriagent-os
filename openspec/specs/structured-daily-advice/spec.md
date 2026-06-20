# structured-daily-advice Specification

## Purpose

定义 structured-daily-advice 能力的行为要求。
## Requirements
### Requirement: 每日建议返回结构化 JSON
`GET /agent/daily` SHALL 返回结构化的 `DailyAdviceResponse`，包含 `preview` 字段和 `items` 数组。新版响应 SHALL 额外包含 `overview`、`generation`，并且每个 item SHALL 同时包含首页缩略用的 `compact` 和详情页展示用的 `detail_view`。旧版 `items[].detail` SHALL 保留为字符串兼容字段，值映射自 `compact.subtitle`。

#### Scenario: 正常返回
- **WHEN** 请求 `GET /agent/daily` 且生成了 3 条建议
- **THEN** 返回包含 `{preview, overview, items, generation, created_at}` 的 JSON，其中 `items[0].compact.title` 可用于首页，`items[0].detail_view.steps` 可用于详情页

#### Scenario: 无活跃茬口
- **WHEN** 请求 `GET /agent/daily` 且无活跃茬口
- **THEN** 返回 setup 类建议或 empty 模式响应，preview 不为空，items 至少包含一条可展示建议

### Requirement: AdviceItem 字段约束
每个 AdviceItem SHALL 满足：
- `id`: 稳定建议 ID，必须来自 selected candidate 或系统 fallback ID
- `category`: `weather | operation | crop_stage | finance | setup | record`
- `priority`: 1-3 整数，1 为最紧急
- `level`: `urgent | important | normal`
- `compact.title`: ≤12 字，结论性描述
- `compact.subtitle`: 15-50 字，说明原因和首页行动
- `compact.icon`: lucide 图标 key 或兼容 emoji
- `compact.icon_color`: 前端主题色 key
- `detail_view.title`: 详情页标题
- `detail_view.description`: 20-120 字，解释为什么今天要处理
- `detail_view.evidence`: 至少 1 条，empty 模式除外
- `detail_view.steps`: 至少 2 条，面向用户可执行
- `detail_view.related`: 可为空，但不得包含候选外经营状态噪音
- `detail_view.actions`: 至少包含 `ask_agent`，可按类别包含 `create_work_order`

旧版 `title/detail/icon` 字段 SHALL 保留，映射自 `compact`；其中旧版 `detail` 是字符串，不是详情对象。

#### Scenario: 首页字段可直接展示
- **WHEN** 前端读取 `items[0].compact`
- **THEN** 能获得标题、短说明、图标和颜色，无需解析长文案

#### Scenario: 详情字段可直接展示
- **WHEN** 前端导航到建议详情页
- **THEN** 能用同一个 item 的 `detail_view.evidence`、`detail_view.steps`、`detail_view.related` 和 `detail_view.actions` 渲染详情页

#### Scenario: 旧字段兼容
- **WHEN** 旧前端读取 `items[0].title`、`items[0].detail`、`items[0].icon`
- **THEN** 后端返回的值分别等于 `compact.title`、`compact.subtitle`、`compact.icon`

### Requirement: 按 priority 排序
items 数组 SHALL 按 priority 升序排列（1 最紧急在前）。

#### Scenario: 多条建议排序
- **WHEN** 返回 5 条建议，priority 分别为 3,1,2,3,1
- **THEN** 前端收到排序后的数组：1,1,2,3,3

### Requirement: 多茬口建议按 priority 混排
当存在多个活跃茬口时，所有茬口的建议 SHALL 合并后按 priority 统一排序，不按茬口分组。

#### Scenario: 2 个茬口各 2 条建议
- **WHEN** 西瓜有 2 条建议（priority 1, 3），豆角有 2 条建议（priority 2, 3）
- **THEN** 合并为 4 条，按 priority 排序：1(西瓜), 2(豆角), 3(西瓜), 3(豆角)

### Requirement: prompt 引导 LLM 输出结构化 JSON
Agent 生成每日建议时，prompt SHALL 要求 LLM 只基于后端提供的候选 skeleton 输出 v2 JSON 文案补全结果，不得新增候选、修改 source、修改 priority 或添加候选外事项。

#### Scenario: LLM 输出合法 JSON（新格式）
- **WHEN** LLM 输出包含 `items[].id`、`compact`、`detail_view.description`、`detail_view.steps` 的 v2 JSON
- **THEN** 后端解析并校验，通过后返回 `DailyAdviceResponse`

#### Scenario: LLM 输出不合法
- **WHEN** LLM 输出无法解析为 JSON、字段缺失或不满足校验
- **THEN** 后端执行 Reflection retry 或规则 fallback，不得使用原始文本构造单条空泛建议

### Requirement: DailyAdviceResponse 包含 preview 字段
`DailyAdviceResponse` SHALL 包含 `preview` 字段，长度 ≤20 字，作为首页预览卡片的主文案。

#### Scenario: 正常返回含 preview
- **WHEN** 请求 `GET /agent/daily` 且 LLM 返回含 preview 的 JSON
- **THEN** 返回 `{preview: "今日有雨，注意防涝", items: [...], created_at: "..."}`

#### Scenario: 旧格式数据兼容
- **WHEN** 缓存中存在旧格式数据（无 preview 字段）
- **THEN** `preview` 默认为空字符串，前端 fallback 处理

### Requirement: Prompt 要求 LLM 返回 preview
生成每日建议的 Prompt SHALL 要求 LLM 返回包含 `preview` 和 `items` 的 JSON 对象。

#### Scenario: LLM 返回新格式
- **WHEN** LLM 返回 `{"preview": "...", "items": [...]}`
- **THEN** 后端解析 preview 和 items，存储完整 JSON

#### Scenario: LLM 返回旧格式
- **WHEN** LLM 返回旧格式 `[...]` 或单个对象
- **THEN** 后端兼容解析，preview 设为空字符串

### Requirement: 每日建议响应必须包含首页经营态势
`DailyAdviceResponse` SHALL 包含 `overview` 字段，用于首页顶部经营态势卡展示。

#### Scenario: 返回经营态势
- **WHEN** 请求 `GET /agent/daily`
- **THEN** 响应包含 `overview.score`、`overview.subtitle` 和 `overview.metrics`

#### Scenario: 指标展示
- **WHEN** 今日存在高温、13 项作业和 1 项待处理
- **THEN** `overview.metrics` 包含 weather、work_order、pending 三类指标，每类含 label、value、level 和 icon

### Requirement: 每日建议响应必须包含生成元数据
`DailyAdviceResponse` SHALL 包含 `generation` 字段，描述生成模式、schema version、缓存命中状态和候选指纹。

#### Scenario: LLM 生成通过
- **WHEN** LLM 首次生成通过校验
- **THEN** `generation.mode` 为 `llm`，`generation.retry_count` 为 0

#### Scenario: 缓存命中
- **WHEN** 今日缓存 schema version 和 candidate fingerprint 均匹配
- **THEN** `generation.cache_hit` 为 true，服务不重新调用 LLM

#### Scenario: 规则兜底
- **WHEN** 服务使用规则 fallback
- **THEN** `generation.mode` 为 `fallback`，且响应仍包含可展示 items

