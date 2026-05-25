## ADDED Requirements

### Requirement: Agent 步数上限
系统 SHALL 在 LangGraph 编译时设置 `recursion_limit=15`，当 Agent 迭代步数超过此限制时，SHALL 抛出 `GraphRecursionError` 并终止执行。

#### Scenario: 正常请求不触发限制
- **WHEN** 用户发送农事问答，Agent 在 15 步内完成
- **THEN** 正常返回结果，无错误

#### Scenario: 超限请求被终止
- **WHEN** Agent 因工具调用失败等原因循环超过 15 步
- **THEN** 抛出 GraphRecursionError，API 返回 429 状态码，消息为"Agent 思考步数超限，请简化问题后重试"

### Requirement: Agent 输入注入检测
系统 SHALL 在将用户输入传给 LLM 之前，检测提示词注入攻击模式。匹配到注入模式时，SHALL 拒绝请求并返回 400 错误。

#### Scenario: 检测到注入攻击
- **WHEN** 用户输入包含"忽略之前的指令"、"ignore previous instructions"、"you are now"、"system:"等注入模式
- **THEN** API 返回 400，消息为"输入包含不安全内容"

#### Scenario: 正常输入通过检测
- **WHEN** 用户输入为正常农事问题
- **THEN** 请求正常传递给 Agent

### Requirement: Agent 输出 PII 过滤
系统 SHALL 对 Agent 最终回复进行 PII（个人身份信息）正则过滤，匹配到的内容 SHALL 替换为 `[REDACTED]`。

#### Scenario: 输出包含手机号
- **WHEN** Agent 回复中包含 11 位手机号
- **THEN** 手机号替换为 `[REDACTED]`

#### Scenario: 输出包含 API Key 格式
- **WHEN** Agent 回复中包含 `sk-` 开头的 API Key 格式
- **THEN** API Key 替换为 `[REDACTED]`

#### Scenario: 正常回复无变化
- **WHEN** Agent 回复不包含任何 PII 模式
- **THEN** 回复原样返回

### Requirement: LLM 输出 JSON 解析保护
cost_service.parse_record SHALL 对 LLM 返回的文本进行安全的 JSON 解析。解析失败时 SHALL 返回明确的错误提示而非 500 崩溃。

#### Scenario: LLM 输出合法 JSON
- **WHEN** LLM 返回可解析的 JSON，字段合法
- **THEN** 正常创建成本记录

#### Scenario: LLM 输出非 JSON
- **WHEN** LLM 返回的不是合法 JSON
- **THEN** 返回错误提示"无法解析 AI 输出，请手动填写"，不创建记录

#### Scenario: LLM 输出 JSON 但字段非法
- **WHEN** LLM 返回 JSON 但 record_type 不在 ["cost", "income"] 中，或 amount 为负数
- **THEN** 返回错误提示"AI 解析结果校验失败"，列出非法字段

### Requirement: ChatRequest 消息长度限制
ChatRequest.message SHALL 限制最大长度为 2000 字符。超过限制时 SHALL 返回 422 验证错误。

#### Scenario: 消息过长被拒绝
- **WHEN** 用户发送超过 2000 字符的消息
- **THEN** 返回 422，提示"消息长度不能超过 2000 字符"

#### Scenario: 正常长度消息通过
- **WHEN** 用户发送 2000 字符以内的消息
- **THEN** 请求正常处理

### Requirement: CostRecord 字段校验强化
CostRecordBase 的 record_type SHALL 使用枚举校验（只允许 "cost"/"income"），amount SHALL 限制为正数且不超过 10,000,000。

#### Scenario: 非法 record_type 被拒绝
- **WHEN** 提交 record_type 为 "other"
- **THEN** 返回 422 验证错误

#### Scenario: 负数金额被拒绝
- **WHEN** 提交 amount 为 -100
- **THEN** 返回 422 验证错误

#### Scenario: 超大金额被拒绝
- **WHEN** 提交 amount 为 100,000,000
- **THEN** 返回 422 验证错误
