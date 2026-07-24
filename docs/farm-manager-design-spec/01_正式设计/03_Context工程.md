# 03 — Context 工程

> 状态：已同步当前实现 | 维护：BlockShip | 关联：[01_Agent平台架构](./01_Agent平台架构.md)、[04_Memory工程](./04_Memory工程.md)、[05_Prompt工程](./05_Prompt工程.md)

---

## 1. 为什么需要 Context 工程

农户的对话历史长，业务数据多（茬口、账单、工人、天气、任务状态、外部知识），全量塞进 system prompt 会：

- Token 爆炸，成本飙升且容易超过上下文窗口。
- 注意力分散，模型难以稳定找到当前轮真正需要的信息。
- 延迟增加，首 token 和工具链路都会被无关上下文拖慢。
- 安全边界模糊，业务状态、外部证据、长期记忆和输出契约容易混在一起。

Context 工程的目标是：**按当前意图、工具依赖和安全边界，给 LLM 喂刚刚好的上下文，并让每个上下文块的来源、用途、预算和 trace 都可解释**。

## 2. 当前状态

| 能力 | 当前实现 | 状态 |
| --- | --- | --- |
| Context 数据模型 | `ContextBlock` 表示单个上下文块；`ContextBundle` 是 block 集合、预算结果和 metadata，已经从旧版固定字段模型切换为 block 架构 | 已落地 |
| 分区化渲染 | `ContextDocument` / `ContextRenderer` 将 bundle 映射到固定分区：`[Role & Policies]`、`[Task]`、`[Evidence]`、`[Context]`、`[Output]` | 已落地 |
| 外部知识检索 | `KnowledgeSelector` + `RAGKnowledgeProvider` 调 QuillRAG 只读 `retrieve`，生成 `rag_knowledge` block 进入 Evidence 分区 | 已落地 |
| Task Context | `agent_task_states` 保存同 farm/user/session 最近一个 active 或 waiting_user 任务，`active_task_state` 进入 Task 分区 | 已落地 |
| TaskState 写入闭环 | `task_state_updater.update_task_state_after_turn()` 在聊天轮次结束后保守更新任务状态，pending 确认链路会跳过 | 已落地 |
| 显式长期记忆 | 用户明确说“记住/以后默认/帮我记一下”时写入 MySQL `memory_records` confirmed 记忆，下一轮经 `long_term_memory` block 注入 | 已落地 |
| 会话摘要 | `conversations.summary` / `summary_updated_at` 承载 running summary；`ConversationSelector` 可注入 `conversation_summary` | 已落地 |
| Trace 摘要证据链 | `build_context_trace_payload()` 生成安全摘要，ContextBuilder 通过 TraceCollector 写 Mongo，失败静默降级 | 已落地 |
| 预算与压缩 | `TokenBudget` 按 priority、required、compressible 做预算裁剪；文本压缩仍是截断式压缩 | 已落地，压缩能力有限 |
| 旧 `RetrievalSelector` | 仅消费调用方传入的 `results`，用于兼容语义检索 block；外部 RAG 主路径由 `KnowledgeSelector` 承担 | 兼容保留 |

## 3. 六类 Context

Farm Manager 当前把上下文按用途分为六类，渲染时再映射到五个 prompt section。

| Context 类型 | 典型 block | Prompt 分区 | 说明 |
| --- | --- | --- | --- |
| Role & Policies | `assistant_role`、`assistant_policy`、`policy`、`role_policy` | `[Role & Policies]` | 助手角色、行为政策和安全约束。 |
| Task Context | `pending_action`、`active_task_state`、`pending_action_pointer`、`pending_plan_pointer`、`temporary_task_state` | `[Task]` | 当前轮必须优先遵守的任务状态、确认链路和待补充信息。 |
| Evidence / Knowledge Context | `rag_knowledge`、`retrieval`、`tool_result_summary` | `[Evidence]` | 外部 QuillRAG 只读知识、工具结果摘要或其他证据；用于回答依据，不承载系统相信的业务状态。 |
| Business Context | `farm`、`cycle`、`weather`、`ledger`、`planting_units`、`operation_work_orders`、`workers`、`unpaid_labor`、`cost_categories` | `[Context]` | MySQL 中当前系统相信的业务事实。 |
| Memory Context | `short_term_recent`、`short_term_summary`、`conversation`、`conversation_summary`、`long_term_memory` | `[Context]` | 最近对话、会话摘要和 confirmed 长期记忆。长期记忆不进入 Evidence，不触发 RAG。 |
| Output Contract | `output_contract`、`citation_rule`、`clarification_rule` | `[Output]` | 输出格式、澄清策略、引用规则等对最终回复的约束。 |

当前代码中的 `ContextRenderer.KEY_TO_SECTION` 是分区映射的事实来源。未知 block key 会 fallback 到 `[Context]`，避免因为新增 selector 未登记而丢失上下文。

## 4. 核心组件

```text
ContextBuildRequest
  - intent / query
  - selected_tool_names
  - context_dependencies / selected_skill_metadata
  - farm_id / user_id / session_id
  - include_retrieval
        ↓
ContextPolicy.resolve()
  - 选择 HOT / WORKING / RETRIEVAL 层
  - 组装 base selectors、工具依赖 selectors、RAG selector
  - 计算 max_tokens 和 dependency_map
        ↓
ContextBuilder.build_runtime_context_bundle()
        ↓
Selectors
  - 业务事实、会话摘要、TaskState、Memory、外部 RAG 等
        ↓
Allowlist + TokenBudget
  - 过滤未允许 key
  - required 优先，按 priority 裁剪/压缩/drop
        ↓
ContextBundle
  - blocks
  - token_budget / token_estimate
  - compressed_blocks / dropped_blocks
  - metadata
        ↓
ContextDocument / ContextRenderer
  - Role & Policies
  - Task
  - Evidence
  - Context
  - Output
        ↓
Runtime / Prompt
```

### 4.1 ContextBlock

`ContextBlock` 是可注入模型的最小上下文单元，字段包括：

- `key`：稳定 block 标识，用于 allowlist、分区和 trace。
- `source`：数据来源，例如 `farm`、`task_state`、`memory.long_term`、`external_rag`。
- `purpose`：面向人读的用途说明。
- `content`：可注入 prompt 的文本正文。
- `priority` / `required` / `compressible` / `min_tokens`：预算和裁剪决策字段。
- `ttl_seconds` / `metadata`：缓存、层级、scope、RAG 元数据、依赖诊断等扩展信息。

### 4.2 ContextBundle

`ContextBundle` 是预算处理后的上下文集合，当前结构是：

```python
@dataclass(slots=True)
class ContextBundle:
    blocks: list[ContextBlock]
    token_budget: int
    token_estimate: int
    compressed_blocks: list[ContextBlock] = field(default_factory=list)
    dropped_blocks: list[ContextBlock] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
```

它不是 `farm/cycle/settings/ledger/weather/...` 固定字段 Pydantic 大对象。业务域新增上下文时应新增或复用 block key，并通过 allowlist、policy 和 renderer 显式纳入。

### 4.3 ContextDocument / ContextRenderer

`ContextDocument` / `ContextSection` 只表达渲染结果，不负责选择、压缩、检索或持久化。`ContextRenderer` 按稳定顺序输出：

1. `[Role & Policies]`
2. `[Task]`
3. `[Evidence]`
4. `[Context]`
5. `[Output]`

当前 prompt 文本以 Markdown section heading 渲染，trace/debug summary 只输出 section、block key、source、token_estimate、required、is_compressed、purpose、reason 等摘要字段，不保存完整正文。

## 5. Selector 与触发策略

| Selector | 数据来源 | 典型 block | 触发条件 |
| --- | --- | --- | --- |
| `FarmSelector` | MySQL `farms` / user nickname | `farm` | base selector，总是尝试 |
| `UserSettingsSelector` | MySQL 用户设置 | `user_settings` | base selector，总是尝试 |
| `CycleSelector` | MySQL 种植周期 | `cycle` | base selector；作物/农事工具依赖也会要求 |
| `TaskStateSelector` | MySQL `agent_task_states` | `active_task_state` | base selector；同 farm/user/session 有 active 或 waiting_user 状态时注入 |
| `MemorySelector` | MemoryService / conversation summary / long-term store | `short_term_recent`、`short_term_summary`、`conversation_summary`、`long_term_memory` | base selector；有内容才注入 |
| `ConversationSelector` | MySQL conversation messages / summary | `conversation`、`conversation_summary` | base selector；当前 session 有历史时注入 |
| `LedgerSelector` | MySQL 账务 | `ledger` | 记账、查账、人工、成本分类等工具依赖触发 |
| `WeatherSelector` | 天气缓存/天气服务结果 | `weather` | 天气工具或天气相关依赖触发 |
| `PlantingUnitSelector` | MySQL 种植单元 | `planting_units` | 种植单元、工单等工具依赖触发 |
| `OperationWorkOrderSelector` | MySQL 农事工单 | `operation_work_orders` | 工单工具依赖触发 |
| `WorkerSelector` | MySQL 工人 | `workers` | 工单、人工工具依赖触发 |
| `UnpaidLaborSummarySelector` | MySQL 人工账务 | `unpaid_labor` | 人工工具依赖触发 |
| `CostCategorySelector` | MySQL 成本分类 | `cost_categories` | 成本分类工具依赖触发 |
| `KnowledgeSelector` | 外部 QuillRAG `POST /retrieve` | `rag_knowledge` | 知识、诊断、方案、种植建议等意图或 query hint 触发 |
| `RetrievalSelector` | 调用方显式传入的 `results` | `retrieval` | `include_retrieval` 或天气工具兼容路径；不是外部 RAG 主入口 |

### 5.1 RAG 只读触发

当前实现已接入外部 QuillRAG。Farm Manager 侧只做只读检索，`RetrievalSelector` 仅作为兼容入口，外部 RAG 主路径由 `KnowledgeSelector` / `RAGKnowledgeProvider` 承担：

- 只调用 QuillRAG 的 `GET /health` 和 `POST /retrieve`。
- `rag_knowledge` 进入 `[Evidence]` 分区，source 为 `external_rag`。
- Prompt 只注入来源、分数和片段摘要，不注入原始大 JSON。
- 配置入口是 `rag_service`，密钥只能通过环境变量或私密配置注入，例如 `RAG_SERVICE__API_KEY`。
- Farm Manager 不配置、不调用、不保存 embedding provider 或 embedding key；embedding 在 RAG 服务侧完成。
- 检索失败按配置降级为空 knowledge block 或抛出标准化 RAG 不可用错误。

### 5.2 RAG 不触发场景

`ContextPolicy` 会阻止以下场景触发 RAG：

- 记账、查账、欠款、人工、工资等业务数据库查询。
- pending action / pending plan 的确认或取消。
- 写操作确认链路。
- 空 query 或未启用/未配置 RAG 服务。

## 6. 存储边界

| 存储 | 保存内容 | 是否参与主问答决策 | 边界 |
| --- | --- | --- | --- |
| MySQL | 业务事实、Farm/Cycle/Ledger/Worker/WorkOrder 等业务表、`agent_task_states`、`memory_records` confirmed 长期记忆、`conversations.summary` 会话摘要 | 是 | 系统相信的当前状态以 MySQL 为准；写入必须走对应 store/service，不从 trace 或 RAG 反写。 |
| Mongo | context/rag/tool trace 摘要证据链 | 否 | 只用于调试、回放和质量定位；不作为 prompt 输入、工具输入或状态恢复来源。 |
| RAG | 外部知识语义召回结果 | 只读证据 | Farm Manager 只调用 retrieve，不做普通问答 ingest，不保存 embedding key，不把未确认记忆同步到 RAG。 |

### 6.1 MySQL

MySQL 承载 Farm Manager 当前相信的状态：

- 业务事实：农场、茬口、账务、工人、工单、成本分类、用户设置等。
- Task Context：`agent_task_states` 保存每个 farm/user/session 最近一个未过期 active 或 waiting_user 任务状态。
- Memory Context：`memory_records` 保存用户显式确认的长期记忆；当前只写 confirmed，读取时按 farm/user 隔离。
- 会话摘要：`conversations.summary` 与 `summary_updated_at` 保存 running summary。

### 6.2 Mongo

Mongo trace 是旁路证据链：

- 可保存 token budget、selected/compressed/dropped block 摘要、selector error、policy 摘要、section 摘要、RAG source 摘要。
- TraceCollector 或 Mongo 写入失败时静默降级，不影响 `ContextBuilder.build()` 返回。
- Mongo trace 不参与主问答决策，不作为状态恢复来源。

### 6.3 RAG

RAG 是外部知识服务，不是 Farm Manager 的状态库：

- 第一版只读检索，不调用 `/ingest`。
- 普通问答不触发 ingest。
- 显式长期记忆不自动同步到 RAG。
- 未确认 memory candidate 不进入 RAG；当前显式长期记忆第一版也不做 candidate 升级规则。
- embedding provider、embedding key、向量索引生命周期都在 QuillRAG 服务侧管理。

## 7. Token Budget 与压缩

当前预算策略由 `TokenBudget` 执行：

- `ContextPolicy` 根据意图、工具和依赖选择 `max_tokens`；base 场景较小，工具依赖或 RAG 场景会提高预算。
- `required=True` block 优先保留，例如 `farm`、`pending_action`。
- 非 required block 按 `priority` 和预算情况选择保留、截断压缩或 drop。
- 压缩器当前主要是文本截断，不是 LLM 语义摘要。
- `compressed_blocks` 和 `dropped_blocks` 会进入 bundle metadata/trace 摘要，方便定位上下文缺失。

预算优先级的实际含义：

- Task 和必需业务身份信息优先保留。
- 业务上下文、会话摘要、长期记忆按 priority 进入。
- RAG 证据可压缩，失败或为空时不能阻断非 RAG 主问答。

## 8. Task Context 生命周期

Task Context 解决“多轮任务在同一 session 内可恢复”的问题。

读路径：

- `TaskStateSelector` 默认随 base selectors 执行。
- 只读取同 `farm_id`、`user_id`、`session_id` 下最近一个未过期 `active` 或 `waiting_user` 状态。
- 输出 `active_task_state` block，进入 `[Task]` 分区。

写路径：

- 非流式和流式聊天在回复生成后调用 `update_task_state_after_turn()`。
- updater 不调用 LLM，不访问 Runtime 内部节点，只消费本轮用户输入、助手回复、farm/user/session 和 pending 状态。
- 有 pending action、pending plan，或本轮已经处理 pending 确认/取消时跳过，避免覆盖确认链路。
- 计划、诊断、方案等任务且助手明确追问缺失信息时，创建或更新 waiting_user task。
- 用户补充信息后更新 observations/entities/missing_information；取消时标记 cancelled；完成时标记 completed。

当前明确不做：

- 不做多任务调度。
- 不做复杂多任务 planner；当前仅与 Router/PlanDraft 的轻量计划状态协作。
- 不把普通账务查询或记账确认流程升级为 TaskState。
- 不把 TaskState 自动写入长期记忆或 RAG。

## 9. Memory Context 生命周期

Memory Context 分为短时、会话摘要和显式长期记忆。

短时与摘要：

- `short_term_recent` 来自 MemoryService 的最近消息窗口。
- `short_term_summary` / `conversation_summary` 来自会话摘要。
- 会话摘要写入 `conversations.summary`，并可同步到短时 memory store。

显式长期记忆：

- 用户明确说“记住”“记一下”“以后默认”“以后都这样”等时，`record_explicit_memory_after_turn()` 尝试写入。
- 写入表为 MySQL `memory_records`，当前只创建 `confirmed` 记录，source 为 `user_explicit`。
- 读取时 `SQLLongTermMemoryStore` 按 farm/user 读取 confirmed 记忆并构造 `LongTermMemoryContext`。
- `MemorySelector` 输出 `long_term_memory` block，进入 `[Context]` 分区。

当前明确不做：

- 不做 LLM 隐式抽取。
- 不做 candidate 升级规则。
- 不做跨 farm/user 检索。
- 不执行 RAG ingest、embedding 或向量库同步。
- 不把 pending action / pending plan 确认流程升级为长期记忆。

## 10. Trace 摘要证据链

`build_context_trace_payload()` 是 Context trace 的事实入口，输出可落 Mongo 的安全摘要。

可保存：

- `token_budget` / `token_estimate`。
- selected、compressed、dropped block 的摘要。
- selector errors、allowlist filtered keys、context dependency diagnostics。
- policy 摘要：intent、selected tool names、enabled layers、dependency keys。
- section 摘要：分区名、token 估算、block key/source/purpose/required/compressed/reason。
- 每个 block 的短 preview，经过截断和敏感信息脱敏。
- RAG 摘要：collection、requested/actual mode、warning、source_count、top_score、前 5 条安全 source metadata。

禁止保存：

- 完整 `ContextBundle` 正文。
- 完整 prompt 正文。
- RAG 原始 chunk 全文、原始请求头、原始大 JSON。
- API key、Authorization、token、secret、password。
- 带明文密码的 Mongo URI。

Trace 写入失败不能影响主链路。Mongo trace 只能服务调试、质量定位和证据链摘要，不进入 prompt 或工具调用输入。

## 11. 缓存、预加载与兼容入口

### 11.1 缓存

`context/cache.py` 和 `context/invalidation.py` 保留 Farm Context Cache 抽象：

- ContextBundle 可按 farm/session 等 scope 缓存。
- 写操作 Skill 成功后必须触发失效。
- 缓存不能绕过 ContextBuilder、allowlist 或 TokenBudget。

### 11.2 预加载

`context/preload.py` 保留高频知识预加载能力，用于作物物候期、记账分类、单位换算等无需 LLM 推理即可决定的本地知识。它不是外部 RAG ingest，也不负责长期记忆同步。

### 11.3 兼容入口

`RetrievalSelector` 和 `ContextBuilder.build_farm_runtime_context()` 属于兼容入口：

- `RetrievalSelector` 只把调用方已提供的 `results` 转成 `retrieval` block。
- 外部 RAG 主入口是 `KnowledgeSelector` / `RAGKnowledgeProvider`。
- `build_farm_runtime_context()` 仍返回旧 runtime 需要的 farm context 字典形状，不能作为新 Context 架构的扩展点。

## 12. 边界与禁止

- Runtime 不能直接调用 selector，只能消费 `ContextBundle` 或 `ContextRenderer` 渲染结果。
- Selector 不能调用 LLM、Prompt Composer 或 Runtime 节点。
- Context 层不直接修改 Memory/Task/业务状态；写入必须走对应 service/store/updater。
- 普通问答不调用 RAG ingest；Farm Manager 当前不调用 QuillRAG `/ingest`。
- 未确认 memory candidate 不进入 RAG；当前长期记忆第一版只写用户显式 confirmed 记忆。
- Trace 不保存完整 prompt、完整 context、RAG 原文、请求头或任何密钥。
- Mongo trace 不参与主问答决策，也不作为状态恢复来源。
- Farm Manager 不保存 embedding key，不管理向量索引生命周期。
- Pending action / pending plan 确认链路优先级高于 TaskState 和长期记忆写入。
- 新增 block key 必须同步 allowlist、renderer 分区和必要测试，不能靠未知 key fallback 长期运行。

## 13. 相关实现与文档

实现入口：

- [context/models.py](../../../backend/app/context/models.py)
- [context/builder.py](../../../backend/app/context/builder.py)
- [context/policy.py](../../../backend/app/context/policy.py)
- [context/document.py](../../../backend/app/context/document.py)
- [context/renderer.py](../../../backend/app/context/renderer.py)
- [context/trace.py](../../../backend/app/context/trace.py)
- [context/rag_provider.py](../../../backend/app/context/rag_provider.py)
- [context/selectors/knowledge.py](../../../backend/app/context/selectors/knowledge.py)
- [context/selectors/task_state.py](../../../backend/app/context/selectors/task_state.py)
- [context/selectors/memory.py](../../../backend/app/context/selectors/memory.py)
- [application/chat/task_state_updater.py](../../../backend/app/application/chat/task_state_updater.py)
- [memory/explicit.py](../../../backend/app/memory/explicit.py)
- [memory/long_term/store.py](../../../backend/app/memory/long_term/store.py)

相关 specs：

- [Agent Context 分区渲染 Phase 1](../../specs/2026-07-21-agent-context-sectioned-renderer.md)
- [Agent Context 外部 RAG 只读接入 Round 1](../../specs/2026-07-21-agent-context-rag-readonly.md)
- [Agent Context Task State 最小持久化](../../specs/2026-07-22-agent-context-task-state-minimal.md)
- [Agent Context 显式长期记忆最小版](../../specs/2026-07-22-agent-context-explicit-long-term-memory.md)
- [Agent Context Trace 摘要证据链](../../specs/2026-07-22-agent-context-trace-payload.md)
- [01_Agent平台架构](./01_Agent平台架构.md)
- [04_Memory工程](./04_Memory工程.md)
- [05_Prompt工程](./05_Prompt工程.md)
- [03_接口协议/02_Agent内部接口](../03_接口协议/02_Agent内部接口.md)
