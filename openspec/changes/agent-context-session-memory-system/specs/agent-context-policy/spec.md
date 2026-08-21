## MODIFIED Requirements

### Requirement: Agent 上下文分层策略
系统 SHALL 将 Agent 上下文分为热上下文、工作记忆和按需检索上下文三层，并在每次 LLM 调用前基于请求、Skill Router 选中的能力、会话 snapshot 和 token budget 构建最终 `ContextBundle`。ContextBundle MUST 区分 required、priority、compressible 和 source。

#### Scenario: 构建三层上下文
- **WHEN** Agent 处理一次聊天请求
- **THEN** 系统 SHALL 生成包含热上下文、Session Memory、长期记忆检索决策和预算结果的 ContextBundle

#### Scenario: 闲聊请求使用最小上下文
- **WHEN** intent 为闲聊且未选择业务 tool
- **THEN** 系统只注入热上下文和必要的短时记忆，不默认注入账务、天气、日志或长期检索结果

#### Scenario: ReAct step rebuilds context
- **WHEN** 当前 Turn 完成一次工具调用并进入下一次 LLM 调用
- **THEN** 系统 SHALL 保留不可变的 Turn 起始 snapshot，并将新的 tool observation 作为动态 Block 重新构建 Context，不得继续使用过期的初始消息列表

### Requirement: 最终 token 预算控制
Context 工程 MUST 在调用 LLM 前对最终上下文执行 token 预算控制，并同时计算消息、Tool Schema、工具结果、结构化开销、模型输出预留和安全余量。预算决策 SHALL 按 required、priority、可压缩性和 min_tokens 决定保留、压缩或丢弃 Block。

#### Scenario: 上下文低于预算
- **WHEN** 候选上下文和工具 Schema token 估算低于 usable budget
- **THEN** 系统保留候选 Block，并记录每个 Block 与整体预算的 token estimate

#### Scenario: 上下文超过预算
- **WHEN** 候选上下文超过 usable budget
- **THEN** 系统保留 required 和高优先级 Block，压缩可压缩 Block，丢弃低优先级 Block，并为每个丢弃项记录 reason

#### Scenario: required block 超预算
- **WHEN** required Block 本身导致预算超限
- **THEN** 系统仍保留 required Block，停止继续注入低优先级内容，并在 Trace 和 Turn 结果中标记预算超限风险

### Requirement: 上下文可观测性
系统 SHALL 为每次 Context 构建记录选中的 selector、候选 Block、保留 Block、压缩 Block、丢弃 Block、token 估算、来源版本、耗时和 selector 错误。

#### Scenario: 调试上下文缺失
- **WHEN** Agent 回复缺少某项业务背景
- **THEN** 开发者可以通过 Trace 判断该 Block 是否未被选择、被压缩、被预算丢弃、读取失败或来自 fallback

### Requirement: LLM Skill Router
系统 SHALL 在 ContextBuilder 之前提供 LLM-based Skill Router。Router SHALL 只接收当前用户请求和轻量 Skill Metadata，输出候选 Skill/Capability，不得执行 Tool、生成最终 Tool 参数或接收完整 Tool Schema、完整 Memory 和隐藏执行轨迹。

#### Scenario: 选择单一业务能力
- **WHEN** 用户请求只涉及天气只读查询
- **THEN** Router SHALL 从 Skill Metadata 中选择天气及必要位置能力，并输出结构化 Skill ID 集合，而不是直接选择或执行具体 Tool

#### Scenario: 组合能力
- **WHEN** 用户请求同时需要位置解析和天气查询
- **THEN** Router SHALL 返回位置与天气 Skill，SkillRegistry 再展开对应 Tool Schema，ContextBuilder 再根据这些 Skill 的 Context dependency 构建 ContextBundle

#### Scenario: Router 不可用
- **WHEN** Router 超时、返回非法 Skill ID 或无法完成路由
- **THEN** 系统 SHALL 返回结构化 Router failure，并按配置回退全量 Tool Schema；回退必须记录 `skill_router_status=fallback`

#### Scenario: Main Agent 负责路由
- **WHEN** `skill_router_mode=main_agent`
- **THEN** 系统 SHALL 不调用前置 Skill Router，直接向 Main Agent 暴露全量 exposed Tool Schema，并记录 `skill_router_status=disabled`、`decision_source=main_agent`

#### Scenario: 可替换 Router Backend
- **WHEN** 系统替换 SkillRouter Backend
- **THEN** Backend 只能改变 Skill 选择实现，不得改变 SkillRegistry 展开、ContextBuilder 注入、HITL 和 Tool Executor 契约

### Requirement: 活跃工具 Schema 选择
SkillRegistry SHALL 将 Router 选中的 Skill IDs 展开为活跃 Tool Schema；全量暴露模式只能作为兼容或灰度模式，并必须被观测。Tool Schema 的最终注入仍 SHALL 受 Context budget、风险策略、HITL 后继动作和 dependency 约束。

#### Scenario: Candidate tool schema
- **WHEN** Router 选择天气与位置 Skill
- **THEN** 系统 SHALL 只展开对应 Skill 的 Tool Schema，并记录 `tool_schema_mode`、Router 选中 Skill、候选数量和被排除原因
