## ADDED Requirements

### Requirement: 客户端注入当前日期
移动端 SHALL 在每个 HTTP 请求头中携带 `X-Current-Date`，值为设备本地日期，格式 `YYYY-MM-DD`。后端 SHALL 读取该请求头并注入到 prompt 模板变量中。

#### Scenario: 正常请求携带日期头
- **WHEN** 移动端发送任意 API 请求
- **THEN** 请求头包含 `X-Current-Date: 2026-05-25`

#### Scenario: 后端读取日期头
- **WHEN** 后端收到含 `X-Current-Date: 2026-05-25` 的请求
- **THEN** `render_prompt()` 中 `{{ current_date }}` 被替换为 "2026-05-25"

### Requirement: 日期范围校验
后端 SHALL 对 LLM 解析出的日期字段进行范围校验。`record_date` 必须 ≥ 2020-01-01 且 ≤ 当前日期 + 1 天。不满足时自动替换为今天。

#### Scenario: 日期在正常范围内
- **WHEN** LLM 返回 `record_date: "2026-05-20"`
- **THEN** 校验通过，保留原值

#### Scenario: 日期过早
- **WHEN** LLM 返回 `record_date: "2019-12-31"`
- **THEN** 校验失败，自动替换为今天（如 "2026-05-25"）

#### Scenario: 日期过晚
- **WHEN** LLM 返回 `record_date: "2027-01-01"`
- **THEN** 校验失败，自动替换为今天

#### Scenario: 日期为空
- **WHEN** LLM 返回 `record_date: ""` 或 null
- **THEN** 自动替换为今天

### Requirement: Prompt 中明确时间规则
所有涉及日期解析的 prompt SHALL 包含明确的时间规则："今天是 {{ current_date }}，如果用户未指定日期，默认使用今天。日期格式为 YYYY-MM-DD。"

#### Scenario: 记账解析 prompt 包含时间规则
- **WHEN** 渲染 `cost_parse.j2` 模板
- **THEN** 模板内容包含 "今天是 2026-05-25，如果用户未指定日期，默认使用今天"

### Requirement: 服务端时间兜底
如果请求未携带 `X-Current-Date` 头，或服务端时间与客户端时间偏差 > 7 天，后端 SHALL 使用服务端 NTP 时间作为 `current_date`。

#### Scenario: 缺失日期头
- **WHEN** 请求不含 `X-Current-Date`
- **THEN** 后端使用 `datetime.now()` 作为当前日期

#### Scenario: 客户端时间偏差过大
- **WHEN** `X-Current-Date: 2025-01-01`（偏差 > 7 天）
- **THEN** 后端忽略客户端日期，使用服务端时间
