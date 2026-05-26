## ADDED Requirements

### Requirement: 每日建议返回结构化 JSON
`GET /agent/daily` SHALL 返回结构化的 `DailyAdviceResponse`，包含 `items` 数组，每项为 `{title, detail, priority, icon}`。

#### Scenario: 正常返回
- **WHEN** 请求 `GET /agent/daily` 且 LLM 生成了 3 条建议
- **THEN** 返回 `{items: [{title: "明天降温关风口", detail: "12°低温，西瓜伸蔓期怕冻", priority: 1, icon: "🌡️"}, ...]}`

#### Scenario: 无活跃茬口
- **WHEN** 请求 `GET /agent/daily` 且无活跃茬口
- **THEN** 返回通用建议（如天气提醒），items ≤3 条

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
Agent 生成每日建议时，prompt SHALL 要求 LLM 以 JSON 格式输出 items 数组，后端解析并校验。

#### Scenario: LLM 输出合法 JSON
- **WHEN** LLM 输出 `[{"title":"...","detail":"...","priority":1,"icon":"🌡️"}]`
- **THEN** 后端解析为 `list[AdviceItem]` 返回

#### Scenario: LLM 输出不合法
- **WHEN** LLM 输出无法解析为 JSON 或字段缺失
- **THEN** 后端 fallback 为单条 AdviceItem（title="今日农事建议", detail=原始文本前 40 字）
