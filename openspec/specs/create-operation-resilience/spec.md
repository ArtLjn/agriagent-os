## ADDED Requirements

### Requirement: Pydantic 输出校验
AI 解析记账描述后，后端 SHALL 使用 Pydantic 模型对 LLM 输出进行结构化校验。字段包括：record_type（枚举 cost/income）、category（str，最大 50 字）、amount（数字字符串）、record_date（YYYY-MM-DD）、note（可选 str）。

#### Scenario: LLM 输出完整且合法
- **WHEN** LLM 返回 `{record_type: "cost", category: "人工", amount: "300", record_date: "2026-05-25"}`
- **THEN** Pydantic 校验通过，返回 CostParseResponse

#### Scenario: LLM 输出缺少必需字段
- **WHEN** LLM 返回 `{category: "人工", amount: "300"}`（缺少 record_type 和 record_date）
- **THEN** Pydantic 校验失败，使用默认值：record_type="cost", record_date=今天

#### Scenario: LLM 输出非法 record_type
- **WHEN** LLM 返回 `{record_type: "支出", category: "人工", amount: "300"}`
- **THEN** Pydantic 校验失败，record_type 替换为 "cost"

### Requirement: 幂等键去重
客户端 SHALL 在 `/costs/parse` 请求中携带 `X-Idempotency-Key` 请求头（UUID v4）。服务端 SHALL 使用 SQLite 唯一索引确保同一幂等键 24 小时内只执行一次解析，重复请求直接返回缓存结果。

#### Scenario: 首次请求
- **WHEN** 客户端发送 `X-Idempotency-Key: abc-123`，服务端未见过该 key
- **THEN** 正常调用 LLM 解析，结果入库，返回 CostParseResponse

#### Scenario: 重复请求
- **WHEN** 客户端在 1 小时内再次发送相同的 `X-Idempotency-Key: abc-123`
- **THEN** 不调用 LLM，直接返回上次缓存的结果

#### Scenario: 过期后重复
- **WHEN** 客户端在 25 小时后发送相同的 `X-Idempotency-Key: abc-123`
- **THEN** 视为新请求，重新调用 LLM 解析

### Requirement: 事务回滚保护
所有涉及数据库写入的创建操作 SHALL 在 `try/except/finally` 块中执行，异常时回滚事务，不留下脏数据。

#### Scenario: 创建记录时数据库异常
- **WHEN** `cost_service.create_record()` 执行中数据库连接断开
- **THEN** 捕获异常，调用 `db.rollback()`，抛出 HTTP 500 错误，不写入任何数据

#### Scenario: 解析成功后保存失败
- **WHEN** LLM 解析成功，但写入 `CostRecord` 时主键冲突
- **THEN** 回滚事务，返回 409 Conflict 或重试

### Requirement: JSON 解析容错
LLM 输出可能包裹在 Markdown 代码块中。后端 SHALL 支持自动提取 ```json 代码块内的 JSON 内容，并对常见格式错误做容错处理。

#### Scenario: Markdown 代码块包裹
- **WHEN** LLM 返回 "```json\n{...}\n```"
- **THEN** 正确提取并解析内部 JSON

#### Scenario: 纯文本 JSON
- **WHEN** LLM 返回 "{...}"（无代码块）
- **THEN** 正确解析

#### Scenario: JSON 解析失败
- **WHEN** LLM 返回非 JSON 内容
- **THEN** 返回 422 Unprocessable Entity，提示 "AI 返回格式异常"
