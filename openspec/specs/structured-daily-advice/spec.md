## Purpose

定义 structured-daily-advice 能力的行为要求。
## Requirements
### Requirement: 每日建议返回结构化 JSON
`GET /agent/daily` SHALL 返回结构化的 `DailyAdviceResponse`，包含 `preview` 字段和 `items` 数组。

#### Scenario: 正常返回
- **WHEN** 请求 `GET /agent/daily` 且 LLM 生成了 3 条建议
- **THEN** 返回 `{preview: "今日有雨，注意防涝", items: [{title: "明天降温关风口", detail: "12°低温，西瓜伸蔓期怕冻", priority: 1, icon: "🌡️"}, ...]}`

#### Scenario: 无活跃茬口
- **WHEN** 请求 `GET /agent/daily` 且无活跃茬口
- **THEN** 返回通用建议（如天气提醒），preview 为天气总结，items ≤3 条

### Requirement: AdviceItem 字段约束
每个 AdviceItem SHALL 满足：
- `title`: ≤10 字，结论性描述
- `detail`: ≤40 字，原因/操作细节
- `priority`: 1-3 整数，1 为最紧急
- `icon`: emoji 字符

#### Scenario: title 超长
- **WHEN** LLM 生成的 title 超过 10 字
- **THEN** 后端截断为 10 字并加省略号

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
Agent 生成每日建议时，prompt SHALL 要求 LLM 以 JSON 格式输出 `{"preview": "...", "items": [...]}`，后端解析并校验。

#### Scenario: LLM 输出合法 JSON（新格式）
- **WHEN** LLM 输出 `{"preview":"...","items":[{"title":"...","detail":"...","priority":1,"icon":"🌡️"}]}`
- **THEN** 后端解析为 `DailyAdviceResponse`（含 preview 和 items）返回

#### Scenario: LLM 输出不合法
- **WHEN** LLM 输出无法解析为 JSON 或字段缺失
- **THEN** 后端 fallback 为单条 AdviceItem（title="今日农事建议", detail=原始文本前 40 字），preview 为空字符串

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

