## MODIFIED Requirements

### Requirement: 会话摘要
系统 SHALL 为超出最近窗口的历史提供会话摘要能力。摘要 SHALL 与最近窗口分开存储或计算，并作为可压缩 block 纳入 token 预算。

当 session 累积消息数达到配置阈值时，系统 SHALL 自动生成会话摘要并持久化到 `conversations.summary` 字段（含 `summary_updated_at` 时间戳），使摘要可跨进程、跨重启保留。摘要生成 SHALL 在 Response 节点完成后异步触发，不得阻塞用户响应。

摘要 SHALL 采用 running summary 模式：以现有 `conversations.summary` + 最近被推出窗口的消息为输入，将新生成的摘要段追加或合并到 summary，已固定部分不重写。

#### Scenario: 存在旧历史摘要
- **WHEN** session 存在窗口外历史摘要
- **THEN** 系统将摘要作为低于最近窗口优先级的工作记忆 block 注入候选上下文

#### Scenario: 摘要生成失败
- **WHEN** 会话摘要生成或读取失败
- **THEN** 系统记录错误并通过熔断器累计失败次数；当次请求不更新 `conversations.summary`，降级为仅使用最近消息窗口 + 现有字符串截断兜底；熔断阈值触发后短时间内跳过摘要生成

#### Scenario: 达到阈值自动生成
- **WHEN** session 累积消息数 ≥ 配置阈值（默认 12 条）且距离上次 `summary_updated_at` 超过防抖窗口（默认 30 分钟）
- **THEN** Response 节点完成后系统异步触发摘要生成，将 running summary 写入 `conversations.summary` 与 `summary_updated_at`

#### Scenario: 进程重启后保留摘要
- **WHEN** uvicorn 进程重启或会话被重新激活
- **THEN** 短时记忆从 `conversations.summary` 字段恢复会话摘要，不依赖 in-memory 状态

#### Scenario: Feature flag 关闭
- **WHEN** 配置 `ai.enable_session_summary` 为 false
- **THEN** 系统跳过自动摘要生成，行为退回当前实现（仅字符串截断），已存在的 `conversations.summary` 仍可被读取注入

## ADDED Requirements

### Requirement: 摘要触发阈值与防抖
系统 SHALL 通过消息数阈值和时间窗口联合控制摘要触发时机，避免每轮触发或反复重写。

#### Scenario: 未达消息阈值
- **WHEN** session 消息数 < 配置阈值（默认 12）
- **THEN** 系统不触发摘要生成，仍按现有最近窗口逻辑注入

#### Scenario: 防抖窗口内重复触发
- **WHEN** session 在防抖窗口（默认 30 分钟）内已成功生成摘要且消息数再次达到阈值
- **THEN** 系统跳过本次摘要生成，避免高频对话导致 summary 反复重写

### Requirement: 摘要内容保护
摘要生成 SHALL 保留用户后续可能追问的结构化字段：金额、日期、地块或作物名、人名、pending action 类型与关键参数。摘要 prompt 模板 SHALL 明确要求保留这些字段。

#### Scenario: 用户追问摘要内字段
- **WHEN** 用户在第 13 轮追问"刚才那笔 200 块的化肥"
- **THEN** 摘要包含金额（200）、品类（化肥）、时间信息，LLM 可基于摘要正确指代

#### Scenario: 摘要质量监控
- **WHEN** 摘要生成完成
- **THEN** 系统记录 trace 事件，包含原消息关键字段、生成摘要、是否命中关键字段，供后续评测与告警使用

### Requirement: 并发写摘要的一致性
当多个请求并发触发同一 session 的摘要生成时，系统 SHALL 保证 `conversations.summary` 不被旧版本覆盖。

#### Scenario: 并发触发去重
- **WHEN** 同一 session 在防抖窗口内被多个请求触发摘要生成
- **THEN** 系统仅执行一次摘要 LLM 调用，或基于 `summary_updated_at` 时间戳做乐观锁，丢弃过期版本的写入

### Requirement: 摘要生成可观测性
系统 SHALL 通过结构化日志和 trace 记录摘要生成的关键事件，便于调试和质量监控。

#### Scenario: 摘要成功生成
- **WHEN** 摘要 LLM 调用成功并写入 DB
- **THEN** 系统记录 `session_summary_generated` 事件，包含 farm_id、session_id、消息数、输入/输出 token、耗时、生成的摘要长度

#### Scenario: 摘要触发条件不满足
- **WHEN** `maybe_summarize` 被调用但未达阈值或处于防抖窗口内
- **THEN** 系统记录 `session_summary_skipped` 事件，包含跳过原因（below_threshold / within_debounce_window / feature_disabled / circuit_open）
