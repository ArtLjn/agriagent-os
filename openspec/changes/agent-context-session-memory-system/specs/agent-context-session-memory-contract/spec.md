## ADDED Requirements

### Requirement: Unified context session memory boundary
系统 SHALL 将 Conversation、Turn、Context、Session Memory 和 Long-term Memory 建模为不同边界。Conversation 表示用户可见对话，Turn 表示一次请求执行，Context 表示一次 LLM 调用输入投影，Session Memory 表示当前工作记忆，Long-term Memory 表示跨会话可复用事实。

#### Scenario: Build a turn context
- **WHEN** Agent 为同一 `conversation_id` 创建一个新 Turn
- **THEN** 系统 SHALL 从该 Conversation 的版本化 snapshot 构建 Session Memory，并由 Context Builder 生成本次 LLM 调用的 ContextBundle

### Requirement: Versioned conversation snapshot
Conversation snapshot SHALL 包含 `conversation_revision`、`summary_revision`、`reset_generation` 和租户范围。任何摘要或工作记忆写入 MUST 携带其读取时的 revision，并拒绝覆盖更新版本。

#### Scenario: Reject stale summary write
- **WHEN** 摘要任务基于旧 `conversation_revision` 完成
- **THEN** 系统 SHALL 拒绝该摘要覆盖新版本，并记录 `stale_context` 或 `summary_conflict`

### Requirement: Single source of conversation truth
用户和助手最终可见消息 SHALL 以 MongoDB `conversationMessages` 为事实源；Redis 只负责活动 Turn、并发协调和事件重放；Memory Service 不提供本地文件 fallback。

#### Scenario: Worker reads a conversation after restart
- **WHEN** Worker 重启后继续处理一个已有 `conversation_id` 的请求
- **THEN** Agent SHALL 从持久化 Conversation snapshot 恢复工作记忆，不依赖原 Worker 进程的内存或本地临时状态

### Requirement: Explicit session and memory storage mapping
系统 SHALL 明确区分 Session metadata、Short Memory 和 Long-term Memory 的存储位置、写入时机、读取接口和 Context 注入 Block。Session metadata 和 Short Memory SHALL 绑定 `conversation_id`；Long-term Memory SHALL 绑定 user、farm 或 domain scope，不得默认绑定单个 conversation。

#### Scenario: Resolve short and long memory
- **WHEN** Agent 为一个新 Turn 构建 Context
- **THEN** 系统 SHALL 通过 `MemoryService.get_session_view()` 读取 Short Memory，通过 ContextPolicy 判断是否调用 `MemoryService.search()` 读取 Long-term Memory，并分别生成 `recent_turns/session_summary/pending_action` 与 `memory_hits` Block

### Requirement: Memory write and injection separation
Short Memory SHALL 在用户可见消息、摘要、pending action 和临时任务状态变化时更新；Long-term Memory SHALL 只在 Turn finalization 后由 observation/事实准入流程写入。模型不得直接把任意 Context 内容写入 Long-term Memory。

#### Scenario: Completed turn memory flow
- **WHEN** 一个 Turn 生成明确终态
- **THEN** 系统 SHALL 幂等写入用户/助手消息和 Short Memory 状态，并追加 MemoryObservation；只有通过确认或业务提交校验的事实才能写入 Long-term Memory

### Requirement: Explicit reset generation
`POST /api/v2/reset` SHALL 清理当前 Session Memory、pending action 和会话摘要，并递增 `reset_generation`；除非调用硬删除能力，用户可见历史 SHALL 保留。

#### Scenario: Reset active context
- **WHEN** 用户重置一个会话后发送新消息
- **THEN** 新 Turn 不得注入 reset 前的 active summary 或 pending action，并 SHALL 携带新的 `reset_generation`

### Requirement: Tenant-scoped memory
Conversation、Session Memory 和 Long-term Memory 的读写 MUST 同时校验 `user_id` 与可信农场范围。用户输入、Tool 参数和 conversation id 不得绕过租户边界。

#### Scenario: Cross-tenant conversation access
- **WHEN** 用户使用其他租户的 `conversation_id` 请求 Context 或历史
- **THEN** 系统 SHALL 返回未找到或无权限错误，且不得读取或写入该会话记忆

### Requirement: Durable degradation status
当 Conversation、Summary 或 Memory 持久化不可用时，系统 SHALL 返回结构化 source status，并按设计的 fallback 策略继续或终止；不得把 fallback 数据伪装成已持久化事实。

#### Scenario: Conversation store unavailable
- **WHEN** Mongo 会话事实源不可用但当前 Turn 尚未执行写操作
- **THEN** 系统 SHALL 记录 `conversation_source=unavailable`，按配置决定只使用当前请求或终止 Turn，并向 Trace 暴露该状态
