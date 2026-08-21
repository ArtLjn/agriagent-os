## Why

`../../../agri_backend_v2/agent` 已分别实现了 Prompt Cache、短时消息、Mongo 对话历史、Redis Turn 和 Trace，但这些能力没有统一的 Context、Session、Memory 生命周期与事实源契约。当前 Agent 实际从本地 JSON 读取模型历史、从 MongoDB 提供用户可见历史，摘要还可能在序列化时丢失，导致多 Worker、重启、长会话和上下文超预算场景出现失忆或不可解释行为。

现在需要把这些零散机制收敛为一套可实施、可迁移、可观测的设计体系，再据此分阶段修改代码，避免继续在 `react.py` 和 `memory.py` 中堆叠局部修复。

## What Changes

- 建立统一的 `Conversation -> Turn -> Context -> Memory` 四层模型和边界契约。
- 将 `conversationMessages` 作为用户可见会话事实源；Redis 负责 Turn 状态、并发协调和短期事件重放；Trace 负责执行诊断；Memory 通过服务接口向 Context 提供投影。
- 为每次 LLM 调用定义结构化 `ContextBundle`/`ContextBlock`，包含来源、优先级、token 预算、压缩策略、过期策略和丢弃原因。
- 将当前固定消息数截断升级为“最近完整 Turn + 滚动会话摘要 + pending action + 临时任务状态”的短时记忆策略。
- 修复摘要生命周期：摘要独立存储、版本化、可重建、原子更新，并能稳定回注到下一轮 Context。
- 引入完整 token 预算：同时计算消息、Tool Schema、工具结果和输出预留空间；支持 required、priority、compressible、min_tokens 决策。
- 引入位于 ContextBuilder 之前的 LLM-based Skill Router：Router 只读取轻量 Skill Metadata，输出候选 Skill/Capability；Registry 再展开相关 Tool Schema，不默认把全部 Skill Schema 注入每个请求。
- 明确长期 Memory 与会话短时记忆的隔离、租户范围、写入资格和 observation 事件契约；未确认业务事实不得沉淀。
- 扩展 Trace 以记录 Context Block、摘要版本、预算决策、事实源版本、缓存命中和存储一致性状态。
- 定义 reset、过期、重启、Worker 切换、摘要失败、持久化失败和回放场景的降级行为。
- 提供从当前本地 JSON + Mongo 双写状态迁移到统一 Memory/Conversation 读模型的分阶段方案与验收门禁。

## Capabilities

### New Capabilities

- `agent-context-session-memory-contract`: 统一 Conversation、Turn、Context、Session Memory、Long-term Memory 的数据模型、生命周期、事实源和一致性契约。

### Modified Capabilities

- `agent-context-policy`: 增加 LLM Skill Router、Context dependency、ContextBundle、分层预算、活跃工具 Schema、压缩和缓存边界要求。
- `context-engineering`: 将现有 Context 设计细化为可执行的 Block、Budget、Selector、Compaction 和 trace 协议。
- `short-term-memory-policy`: 将固定消息窗口升级为按完整 Turn、token、摘要和 pending action 组成的工作记忆视图。
- `agent-memory-foundation`: 增加 Memory Service、摘要版本、observation、租户范围和持久化失败降级要求。
- `conversation-management`: 明确 Mongo 会话事实源、Session 生命周期、reset/过期/重启恢复及消息与摘要一致性。
- `agent-trace`: 增加 Context 构建、Memory 读取、摘要生成和事实源漂移的可观测字段。

## Impact

- Agent Runtime：`../../../agri_backend_v2/agent/domains/harness/runtime/engine.py`、`context.py`、`memory.py`、`summarizer.py`、`turn.py`。
- 持久化与协调：`../../../agri_backend_v2/agent/platforms/persistence/mongo/chat_store.py`、`turn_store.py`、`worker.py`、Redis/Mongo 配置及索引。
- API：`/api/v2/chat`、`/api/v2/conversations`、`/api/v2/reset`、Turn/SSE replay 和 Trace 查询接口。
- Prompt/Tool：`../../../agri_backend_v2/agent/prompts/`、Skill Router、Skill Registry 的候选能力展开、Skill Metadata 与 Context dependency 元数据。
- 观测：`../../../agri_backend_v2/agent/domains/harness/observability/trace/`、Context Usage SSE、Trace summary 和一致性告警。
- 测试：多轮上下文、摘要回注、租户隔离、Worker 重启、Mongo/Redis 降级、预算裁剪、SSE 回放和 reset 语义。
- 本次阶段只产出设计与实现边界，不直接修改运行时代码；后续实现必须按 tasks 分阶段提交并分别验证。
