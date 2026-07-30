## Why

农户在多轮对话中频繁遇到 Agent "失忆"：超过 5-6 轮就忘记前面提到的金额、地块、作物、人名和待办动作。当前会话压缩机制全部基于**字符串截断**，没有真正的 LLM 语义摘要；`short-term-memory-policy` 与 `conversation-management` spec 早已声明"会话摘要"要求，但代码侧 `MemoryService.set_session_summary()` 是死接口（无任何调用方），`conversations.summary` 字段已存在却从未被写入。

本提案只落地 **同一 session 内的 running summary compaction**，先解决"聊着聊着忘了前文"这个高频终端用户痛点。

长期记忆抽取、`memory_records`、用户偏好沉淀、candidate→confirmed 流转不在本提案范围内，后续由 [add-long-term-memory-observations](../add-long-term-memory-observations/proposal.md) 单独承接。

参考：[docs/superpowers/specs/2026-06-19-knowledge-and-memory-architecture-design.md](../../../docs/superpowers/specs/2026-06-19-knowledge-and-memory-architecture-design.md) § 3-4。

## What Changes

- **新增**：异步触发阈值（messages ≥ 12）的会话摘要生成任务，写入 `conversations.summary` + `summary_updated_at`
- **新增**：摘要 prompt 模板（强制保留金额 / 日期 / 地块 / 作物 / 人名 / pending action 等结构化字段）
- **新增**：`backend/app/memory/summarizer.py` 封装 LLM 摘要调用，失败返回 `None` 并通过熔断器降级
- **修改**：`MemoryService` 暴露 `maybe_summarize()` 入口，由 Runtime Response 节点异步调用
- **修改**：ConversationSelector 在查询时把 `conversations.summary` 注入为独立 `conversation_summary` ContextBlock
- **修改**：摘要失败时降级到现有字符串截断逻辑，保持主流程可用

## Capabilities

### New Capabilities

<!-- 无新增 capability。本提案只落地既有短时记忆、会话管理、上下文工程能力中的会话摘要部分。 -->

### Modified Capabilities

- `short-term-memory-policy`: 落地"会话摘要"requirement —— 当前 `set_session_summary()` 死接口接通生产，提供基于阈值的自动摘要生成、持久化、降级路径
- `conversation-management`: 落地"历史超过窗口时摘要替代"requirement —— ConversationSelector 在查询最近窗口时同时把已生成的 `conversations.summary` 注入到 ContextBundle
- `context-engineering`: 补充"会话摘要 block"作为可压缩工作记忆 block，明确优先级低于最近窗口

## Impact

**新增文件**：
- `backend/app/memory/summarizer.py` — LLM 摘要封装
- `backend/app/memory/prompts/summary.md` — 摘要 prompt 模板
- `backend/tests/memory/test_summarizer.py` — summarizer 单测
- `backend/tests/memory/test_maybe_summarize.py` — MemoryService 摘要触发单测

**修改文件**：
- `backend/app/core/config.py` — 新增 summary 相关配置
- `backend/config.yaml` / `backend/config.yaml.example` — 新增 summary 配置项
- `backend/app/api/admin_config.py` — 暴露 `enable_session_summary`
- `backend/app/memory/service.py` — 新增 `maybe_summarize()` 方法
- `backend/app/memory/short_term/store.py` — `set_session_summary` 接通持久化层
- `backend/app/agent/runtime/nodes.py` — Response 节点末尾挂异步摘要任务
- `backend/app/context/selectors/conversation.py` — 注入 `conversation_summary` block
- `backend/app/observability/metrics.py` — 增加 summary 相关计数器

**Schema 迁移**：无新增迁移。`conversations.summary` / `summary_updated_at` 字段已存在。

**外部依赖**：无新增。

**生产成本**：单户月增 < ¥2（每 12 条消息触发 1 次，qwen3.6 单次约 ¥0.005）。

**回滚**：关闭 feature flag `ai.enable_session_summary` 即可；已写入的 `conversations.summary` 字段可保留，不影响现有流程。

**关联文档**：
- [docs/farm-manager-design-spec/01_正式设计/03_Context工程 § 6](../../../docs/farm-manager-design-spec/01_正式设计/03_Context工程.md)
- [docs/farm-manager-design-spec/01_正式设计/04_Memory工程 § 7.2 / § 12](../../../docs/farm-manager-design-spec/01_正式设计/04_Memory工程.md)
- [docs/superpowers/specs/2026-06-19-knowledge-and-memory-architecture-design.md](../../../docs/superpowers/specs/2026-06-19-knowledge-and-memory-architecture-design.md)
