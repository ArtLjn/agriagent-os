## MODIFIED Requirements

### Requirement: Memory 独立边界
系统 SHALL 提供独立 Memory Service，覆盖短时记忆读取、会话摘要、长期事实接口、检索和 observation 沉淀。Agent Runtime SHALL 通过 Memory Service 读取或写入 Memory，不得直接访问本地文件、记忆存储表或向量索引。

#### Scenario: Agent 读取记忆上下文
- **WHEN** Agent 构建上下文
- **THEN** Agent 通过 Memory Service 获取当前用户、农场和会话范围的记忆视图，并得到 source status 和 revision

### Requirement: 短时记忆接口
Memory 模块 SHALL 支持基于 conversation/session view 的短时记忆，包括最近完整 Turn 窗口、会话摘要、当前 pending action、临时任务状态和 token-aware projection。

#### Scenario: 多轮追问
- **WHEN** 用户在同一 session 中追问“那后天呢”
- **THEN** 短时记忆向 Context Builder 提供最近对话或摘要，帮助 Agent 理解追问对象，且不依赖重新注入完整 Tool payload

### Requirement: 长时记忆预留
Memory 模块 SHALL 预留用户偏好、农场画像、关键事实、周期摘要和账务摘要的数据模型或接口。长期事实 MUST 带 scope、来源、置信状态、created_at 和 expires_at；第一阶段可以只实现接口和空结果，但调用方 SHALL 不依赖具体存储实现。

#### Scenario: 长时记忆尚未启用
- **WHEN** Agent 请求长期记忆上下文但没有任何记忆数据
- **THEN** Memory Service 返回空上下文而不是抛出错误

#### Scenario: 未确认事实不沉淀
- **WHEN** 本轮只有模型推测、审批前参数或工具失败结果
- **THEN** Memory Service SHALL 拒绝将其写入长期事实

### Requirement: 记忆观察事件
Agent 完成一次交互后 SHALL 向 Memory 模块提交 observation event，包含 user_id、farm scope、conversation_id、turn_id、用户输入摘要、助手回复摘要、调用的 skills、提交状态和可选 metadata。原始敏感 payload SHALL 受控或脱敏。

#### Scenario: 对话结束后提交观察
- **WHEN** 用户消息和助手终态已经确定
- **THEN** 系统创建幂等 Memory observation event，供后续摘要、事实抽取或检索索引使用

## ADDED Requirements

### Requirement: Memory persistence failure semantics
Memory 读取或写入失败 SHALL 分类为 `unavailable`、`stale`、`conflict` 或 `invalid`，并按调用场景降级；Memory 失败不得被转换成空的“最新记忆”事实。

#### Scenario: Memory write unavailable
- **WHEN** Turn 已生成最终回复但 Memory observation 写入失败
- **THEN** Turn 可以完成，但 Trace 和 summary SHALL 标记 `memory_observation_persisted=false`，并支持后续重试

### Requirement: Long-term memory scope isolation
长期记忆 SHALL 按用户、农场或明确领域 scope 隔离；conversation-scoped summary 不得自动升级为 user/farm long-term fact。

#### Scenario: Conversation summary isolation
- **WHEN** 一个 conversation 生成会话摘要
- **THEN** 该摘要只能作为该 conversation 的 Session Memory 使用，除非经过事实提取和确认流程，不得直接注入其他 conversation

### Requirement: Separate storage and injection contract
Memory Service SHALL 将 Short Memory 和 Long-term Memory 暴露为不同接口与不同 Context Block。Short Memory SHALL 通过 `get_session_view()` 返回最近 Turn、summary、pending action 和临时状态；Long-term Memory SHALL 通过带 scope 和 query 的 `search()` 返回 `MemoryHit`，仅在 ContextPolicy/Skill dependency 触发时注入 `memory_hits`。

#### Scenario: No long-term dependency
- **WHEN** 当前请求是闲聊或不需要历史事实的简单查询
- **THEN** 系统 SHALL 只读取必要的 Short Memory，不调用 Long-term Memory search，也不注入 `memory_hits`

#### Scenario: Long-term dependency selected
- **WHEN** 当前意图或 Skill metadata 声明需要用户/农场长期事实
- **THEN** 系统 SHALL 按可信 scope 查询 Long-term Memory，并将带来源、时间和过期状态的结果作为低优先级 `memory_hits` Block 注入
