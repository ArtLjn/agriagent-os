## ADDED Requirements

### Requirement: Memory 独立边界
系统 SHALL 提供独立 Memory 模块，覆盖短时记忆、长时记忆、检索和沉淀能力。Agent SHALL 通过 Memory Service 接口读取或写入记忆，不得直接访问记忆存储表或向量索引。

#### Scenario: Agent 读取记忆上下文
- **WHEN** Agent 构建上下文
- **THEN** Agent 通过 Memory Service 获取当前用户和农场的记忆上下文

### Requirement: 短时记忆接口
Memory 模块 SHALL 支持基于 session 的短时记忆，包括最近消息窗口、会话摘要、当前 pending action 和临时任务状态。

#### Scenario: 多轮追问
- **WHEN** 用户在同一 session 中追问“那后天呢”
- **THEN** 短时记忆向 Context Builder 提供最近对话或摘要，帮助 Agent 理解追问对象

### Requirement: 长时记忆预留
Memory 模块 SHALL 预留用户偏好、农场画像、关键事实、周期摘要和账务摘要的数据模型或接口。第一阶段可以只实现接口和空结果，但调用方 SHALL 不依赖具体存储实现。

#### Scenario: 长时记忆尚未启用
- **WHEN** Agent 请求长期记忆上下文但没有任何记忆数据
- **THEN** Memory Service 返回空上下文而不是抛出错误

### Requirement: 记忆观察事件
Agent 完成一次交互后 SHALL 向 Memory 模块提交 observation event，包含 user_id、farm_id、session_id、用户输入、助手回复、调用的 skills 和可选 metadata。

#### Scenario: 对话结束后提交观察
- **WHEN** Agent 完成一次聊天请求
- **THEN** 系统创建 Memory observation event，供后续摘要、事实抽取或检索索引使用

### Requirement: 检索能力预留
Memory 模块 SHALL 提供统一 search 接口，支持后续关键词检索、语义检索或混合检索。调用方 SHALL 只依赖 MemoryHit 结构，不依赖具体向量数据库。

#### Scenario: 检索实现未接入
- **WHEN** Agent 调用 memory.search 查询历史记录
- **THEN** 系统返回空列表或当前已支持的检索结果，调用方无需知道底层存储类型
