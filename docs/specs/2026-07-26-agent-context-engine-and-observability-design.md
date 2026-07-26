# Agent Context Engine 重构与 LLM Context 可观测设计

## 背景

当前 Context 能力已经覆盖 `ContextBlock`、`ContextBundle`、分区渲染、RAG 只读检索、TaskState、显式长期记忆、running summary、trace 摘要和最终 prompt 预算。但 `backend/app/context/` 的代码结构没有把这些能力串成一条清晰主线：

- `builder.py` 是事实主入口，但同时负责 selector 编排、allowlist、预算、trace、兼容旧 farm context。
- `policy.py` 同时负责层级、工具依赖、RAG 触发、selector 注册和 token 预算。
- `selectors/core.py` 命名过宽，混放 Farm、Cycle、Ledger、Conversation、Retrieval 等不同类型上下文。
- 六类 Context 已在 `03_Context工程.md` 中定义，但代码目录没有把六类作为一级概念表达。
- `allowlist.py`、`renderer.py`、trace payload 和文档分别维护 block key、section 和安全边界，事实源分散。
- Playground 已有 `LLM Context 可观测` 抽屉雏形，但依赖 trace 节点拼装，缺少稳定的后端快照契约和压缩状态解释。

本设计目标是让 Context 从“散落的 selector 集合”升级为可阅读、可扩展、可观测的 Context Engine。

## 目标

1. 建立 `ContextEngine` 作为新的唯一主入口。
2. 把六类 Context 变成代码一级概念，而不是只存在于文档。
3. 用注册表统一 block key、category、section、priority、required、allowlist、trace 安全策略。
4. 优化上下文压缩机制，从纯截断升级为分层、可解释、可追溯的预算决策。
5. 优化工具结果压缩，避免只显示 `[已执行 unknown]`，保留工具名、参数摘要、结果摘要和 trace/artifact 指针。
6. 设计 admin-web 实时 LLM Context 可观测能力，让管理员站在 LLM 视角看到本轮最终入模内容，并看到自动压缩后的变化。

## 不做

- 不改变 Agent 主流程的业务语义。
- 不把 Mongo trace 作为主决策输入。
- 不把完整 prompt、完整 context、RAG 原文、密钥或请求头落入 trace。
- 不新增 RAG ingest、embedding 或向量库管理能力。
- 不在本次设计中重写 Memory、TaskState、RAG 服务本身。

## 目标目录

```text
backend/app/context/
  __init__.py
  engine.py                 # 新主入口：ContextEngine.build()
  contracts.py              # ContextBlock/Bundle/Request/Result/Category/Section
  registry.py               # block key、六类 Context、section、预算、安全策略事实源
  planner.py                # 根据 intent/tool/dependency 选择需要的 ContextSource
  budget.py                 # token 预算、压缩、drop 决策
  compression.py            # 语义压缩/结构化压缩策略，不再只放 text 截断
  render.py                 # ContextDocument + ContextRenderer
  trace.py                  # trace 安全摘要和 LLM 视角快照
  legacy.py                 # build_farm_runtime_context 等兼容入口

  sources/
    __init__.py
    role_policy.py          # Role & Policies
    task.py                 # pending action / active task state / pending plan
    evidence.py             # RAG / retrieval / tool_result_summary
    business.py             # farm / cycle / ledger / weather / workers / work orders
    memory.py               # recent / running summary / long-term memory
    output_contract.py      # output contract / citation / clarification

  providers/
    __init__.py
    rag.py                  # QuillRAG provider
```

`ContextBuilder` 保留为兼容门面，内部委托 `ContextEngine`。新代码只依赖 `ContextEngine`、`ContextBuildRequest`、`ContextBundle` 和 `ContextRenderer`。

## 六类 Context

| 类别 | 典型 block | Prompt section | 来源 |
| --- | --- | --- | --- |
| `role_policy` | `assistant_role`、`assistant_policy`、`policy` | `Role & Policies` | 系统配置、用户助手角色设置 |
| `task` | `pending_action`、`active_task_state`、`pending_plan_pointer` | `Task` | MemoryService、TaskStateStore、pending action |
| `evidence` | `rag_knowledge`、`retrieval`、`tool_result_summary` | `Evidence` | QuillRAG、工具结果摘要、兼容检索结果 |
| `business` | `farm`、`cycle`、`ledger`、`weather`、`workers`、`operation_work_orders` | `Context` | MySQL 业务事实 |
| `memory` | `short_term_recent`、`short_term_summary`、`conversation`、`conversation_summary`、`long_term_memory` | `Context` | Conversation、MemoryService、memory_records |
| `output_contract` | `output_contract`、`citation_rule`、`clarification_rule` | `Output` | Prompt/Context 本地规则 |

每个 block key 必须在 `registry.py` 注册。未知 block 在开发环境应报警或测试失败；生产可降级丢弃并记录 `unregistered_block_keys`，避免未审查内容进入 prompt。

## 注册表设计

```python
class ContextCategory(StrEnum):
    ROLE_POLICY = "role_policy"
    TASK = "task"
    EVIDENCE = "evidence"
    BUSINESS = "business"
    MEMORY = "memory"
    OUTPUT_CONTRACT = "output_contract"


@dataclass(frozen=True)
class ContextBlockSpec:
    key: str
    category: ContextCategory
    section: str
    default_priority: int
    required: bool = False
    compressible: bool = True
    min_tokens: int = 32
    trace_preview: bool = True
    prompt_allowed: bool = True
```

注册表负责统一：

- block key 是否允许注入 prompt。
- block 归属哪一类 Context。
- block 渲染到哪个 section。
- 默认 priority、required、compressible、min_tokens。
- trace 是否允许 preview。
- block 是否属于敏感、仅 metadata、仅 trace，不进入 prompt。

`allowlist.py` 和 `renderer.KEY_TO_SECTION` 后续应逐步收敛到注册表，避免多处事实源分裂。

## 构建流水线

```text
ContextEngine.build(request)
  -> ContextPlanner.plan(request)
  -> ContextSource.collect() 按六类收集候选 blocks
  -> ContextRegistry.validate() 校验 block key 与安全策略
  -> ContextBudget.apply() 执行预算、压缩、丢弃
  -> ContextRenderer.render() 生成最终 prompt section
  -> ContextTrace.build_payload() 生成安全 trace 摘要
  -> LlmContextSnapshot.build() 生成最终入模快照
  -> ContextBundle
```

`ContextPlanner` 替代当前 `ContextPolicy` 的部分职责。它只回答“这一轮需要哪些 ContextSource 和预算 profile”，不直接实例化散落 selector。

预算 profile 建议：

| 场景 | 预算 | 特点 |
| --- | --- | --- |
| `chat_base` | 512 | farm、user_settings、task、memory、conversation |
| `business_query` | 900 | 增加 ledger、cycle、workers 等工具依赖上下文 |
| `rag_evidence` | 900-1200 | 增加 RAG evidence，业务写操作不触发 |
| `pending_confirmation` | 512 | pending action/plan 优先，压低非任务上下文 |
| `debug_full` | 1200+ | 仅 admin/dev 显式开启，用于排查 |

## 压缩机制优化

当前 Context 压缩主要是按字符截断；最终 prompt 预算对工具结果按 `tool_result_limit` 截断，对旧消息生成短摘要。优化后分三层：

### 1. ContextBlock 预算压缩

每个 block 的预算决策输出：

```json
{
  "key": "conversation_summary",
  "decision": "selected | compressed | dropped",
  "reason": "fits_budget | compressed_to_fit_budget | lower_priority | required",
  "original_tokens": 320,
  "final_tokens": 96,
  "compressor": "head_tail | structured | llm_summary | none"
}
```

压缩策略：

- `required=True`：默认不丢弃；若超预算，记录 `over_budget_required_blocks`。
- `task` 类：优先保留结构化字段，不做语义摘要。
- `business` 类：优先保留 id、名称、金额、日期、状态，长列表按 top N + count 压缩。
- `memory` 类：最近消息保真，旧消息由 running summary 和短摘要替代。
- `evidence` 类：RAG 只保留来源、分数、短摘录，不保留原始 chunk。
- `output_contract` 类：默认不压缩或只按规则条目裁剪。

### 2. 工具结果压缩

当前旧轮次工具结果会被替换为 `[已执行 unknown]`，信息量太低。目标是改为结构化摘要：

```text
[工具结果已压缩]
tool: manage_cost
args: operation=query_summary, year=2026
status: success
summary: 本月支出 320 元，最近 3 笔为肥料、人工、农药
ref: trace://request_id/node_id
```

规则：

- 压缩主体是 `ToolMessage.content`，不压缩 `AIMessage.tool_calls` 的合法结构。
- `AIMessage(tool_calls)` 与对应 `ToolMessage` 必须成对保留或成对摘要，避免破坏 LangChain/OpenAI 消息合法性。
- 最近 3-5 轮工具结果完整保留。
- 旧工具结果使用 `ToolResultCompressor` 生成结构化摘要。
- 大型 JSON 工具结果先结构化抽取，再截断 preview。
- trace 保存压缩前后 token、tool name、operation、status、result count、summary preview，不保存完整大型结果。

### 3. 最终 LLM Prompt 预算

最终入模前继续保留 `FinalPromptBudget` 兜底，但输出更详细 action：

```json
{
  "actions": [
    "compact_old_tool_results",
    "summarize_old_messages",
    "drop_low_priority_context"
  ],
  "message_count_before": 18,
  "message_count_after": 8,
  "tool_result_tokens_before": 2400,
  "tool_result_tokens_after": 520,
  "total_tokens": 3315,
  "max_tokens": 6000
}
```

如果压缩后仍超预算，必须记录 warning trace，不阻断主链路，但 admin-web 要明显展示“仍超预算”。

## LLM Context 可观测设计

### 目标

admin-web 需要提供一个“站在 LLM 视角”的实时面板，展示本轮最终送进模型的内容，而不是只展示后端内部选择了哪些 block。

管理员应该能看到：

- 本轮最终 `system prompt` 中实际包含哪些 Context section。
- 哪些 Context block 被选中、压缩、丢弃。
- 每个 block 的类别、来源、priority、token、压缩原因。
- messages 最终列表，包括 user、assistant、tool 消息。
- 工具结果是否被压缩，压缩前后 token 和摘要。
- prompt token / max token / context token / budget action。
- 自动压缩发生后，面板内容自动变化，不需要猜测模型实际看到了什么。

### 后端快照契约

新增或升级 `prompt_budget/final_llm_context` trace 节点，输出稳定结构：

```json
{
  "schema_version": 2,
  "request_id": "req-xxx",
  "session_id": "session-xxx",
  "system_prompt": "## Role & Policies\n\n### assistant_role\n温和、可靠、懂农业生产的助手\n\n## Task\n\n### active_task_state\n目标：创建虎丘新租地种植计划",
  "runtime_context": {
    "sections": [
      {
        "name": "Task",
        "token_estimate": 180,
        "blocks": [
          {
            "key": "active_task_state",
            "category": "task",
            "source": "task_state",
            "decision": "selected",
            "compressed": false,
            "dropped": false,
            "priority": 85,
            "required": false,
            "token_estimate": 120,
            "content_preview": "目标：创建虎丘新租地种植计划",
            "content": "仅 admin/debug 模式可返回，默认不返回完整正文"
          }
        ]
      }
    ]
  },
  "messages": [
    {
      "index": 0,
      "role": "human",
      "type": "HumanMessage",
      "content_preview": "帮我看一下这块地适合种什么",
      "content": "安全截断后的最终入模内容",
      "tool_calls": [],
      "tool_call_id": null,
      "compressed": false
    }
  ],
  "budget": {
    "system_tokens": 2100,
    "message_tokens": 1215,
    "tool_result_tokens": 240,
    "total_tokens": 3315,
    "max_tokens": 6000,
    "over_budget": false,
    "actions": []
  },
  "compression": {
    "context_compressed_count": 1,
    "context_dropped_count": 0,
    "message_compressed_count": 2,
    "tool_result_compressed_count": 1,
    "events": []
  }
}
```

安全边界：

- 默认 trace 只保存最终入模内容的安全截断版，单 block/content 有长度上限。
- 密钥、Authorization、token、password、Mongo URI 密码必须脱敏。
- RAG 原始 chunk 不进入快照，只进 source 摘要和短 preview。
- admin debug 模式可看更长正文，但仍不允许密钥。

### API 设计

第一阶段复用现有 timeline：

- `GET /admin/traces/{request_id}/timeline`
- 前端从最新 `node_type=prompt_budget`、`node_name=final_llm_context` 节点抽取快照。

第二阶段增加专用接口，减少前端拼装：

```text
GET /admin/traces/{request_id}/llm-context
```

返回：

```json
{
  "request_id": "req-xxx",
  "snapshot": { "schema_version": 2 },
  "source_node_id": 123,
  "updated_at": "2026-07-26T10:30:00+08:00"
}
```

如果请求还在执行中，返回 `snapshot=null` 和 `status=building | waiting_trace | unavailable`。

### admin-web 交互

在 Playground 保留右侧抽屉入口 `LLM Context`，但升级为四个区域：

1. 顶部指标栏
   - Context Blocks
   - Messages
   - Prompt Token
   - Token Budget
   - Compressed / Dropped

2. 左侧 Context Blocks 列表
   - 按六类 Context 分组。
   - 每个 block 显示 `selected/compressed/dropped/required`。
   - 点击 block 时右侧滚动到对应内容。
   - 被压缩 block 用黄色状态，被丢弃 block 用灰色状态。

3. 右侧 Runtime Context
   - 展示最终 system prompt 中的 Context section。
   - 展示的是压缩后的最终内容。
   - 支持“只看变化”：显示原 token、现 token、压缩原因。

4. Messages Timeline
   - 展示最终入模 messages。
   - ToolMessage 显示 tool name、tool_call_id、status、是否压缩。
   - tool result 被压缩时显示结构化摘要和 trace 引用。

刷新策略：

- 发送消息后，Playground 自动轮询最新 request timeline。
- 当 `final_llm_context` 节点出现时更新抽屉内容。
- 如果后端压缩机制触发，`budget.actions`、block decision、message content 会随快照自动变化。
- 手动“刷新”按钮保留，便于 trace 后写入延迟时重拉。

### TraceMonitor 集成

TraceMonitor 保留面向链路排查的视角，但在 `context_build` 和 `final_llm_context` 节点上增加跳转：

- `context_build`：展示候选 block、预算前后、compressed/dropped。
- `final_llm_context`：展示真正入模的 system prompt + messages。
- 两者之间提供 diff：`context_build.selected_blocks` 与 `final_llm_context.runtime_context.sections` 对比。

这样可以回答两个问题：

- Context 系统选中了什么。
- LLM 最终实际看到了什么。

## 迁移计划

### Phase 1：文档和契约

- 新增本设计文档。
- 在 `03_Context工程.md` 增加新 Context Engine 章节或链接本 spec。
- 定义 `LlmContextSnapshotV2` 字段，补充 admin API 类型。

### Phase 2：后端结构

- 新增 `contracts.py`、`registry.py`、`engine.py`、`planner.py`。
- `ContextBuilder` 委托 `ContextEngine`，保持旧 API 不变。
- `allowlist` 和 renderer section 映射逐步读取 registry。
- `build_farm_runtime_context()` 移到 `legacy.py`，原方法保留转发。

### Phase 3：sources 迁移

- 把 `selectors/core.py` 拆到 `sources/business.py`、`sources/memory.py`、`sources/evidence.py`。
- `selectors/*` 保留兼容 import，内部转发到 sources。
- 更新 selector relocation 测试，避免旧入口长期成为主入口。

### Phase 4：压缩机制

- 引入 `ContextCompressionDecision` 和 `CompressionEvent`。
- 实现 business list、memory summary、RAG evidence、tool result 的结构化压缩。
- 最终 prompt budget 输出 message/tool 压缩前后统计。

### Phase 5：admin-web 可观测

- 升级 `extractLatestLlmContextSnapshot()` 支持 V2。
- `LlmContextVisualView` 增加六类分组、compressed/dropped 状态、messages timeline。
- TraceMonitor 增加 final LLM context 节点专用视图。
- 增加 UI 测试：压缩前后指标变化、敏感字段脱敏、无 snapshot 空态。

## 测试策略

后端：

- `tests/context/test_registry.py`：所有已知 block key 注册完整。
- `tests/context/test_engine.py`：ContextEngine 输出与旧 ContextBuilder 兼容。
- `tests/context/test_context_compression.py`：压缩事件、压缩前后 token、drop 原因可追踪。
- `tests/context/test_tool_result_compression.py`：工具调用与工具结果成对合法，旧工具结果压缩后仍可解释。
- `tests/context/test_llm_context_snapshot.py`：final snapshot 不泄漏密钥，包含最终入模内容和 budget actions。

前端：

- `admin-web/src/pages/Playground/LlmContextInspector.test.tsx`：抽屉展示指标、分组、压缩状态和 messages。
- `admin-web/src/pages/TraceMonitor/index.test.tsx`：context_build 与 final_llm_context 节点分别渲染。
- 敏感字段测试：API key、Authorization、password 不出现在 UI。

验证命令：

```bash
ruff check . && ruff format .
poetry run pytest -v backend/tests/context
pnpm test -- --run admin-web/src/pages/Playground admin-web/src/pages/TraceMonitor
bash scripts/check-complexity-budget.sh
```

## 风险与控制

| 风险 | 控制 |
| --- | --- |
| 重构影响 Agent 主链路 | `ContextBuilder` 保持兼容门面，分阶段切换 |
| 注册表遗漏 block key | 新增 registry 测试，未知 key 在测试环境失败 |
| trace 体积膨胀 | 快照字段截断、只保存 preview、保留 trace DAO 总体积限制 |
| 敏感信息泄漏 | 统一 trace sanitizer，前后端测试覆盖 key/token/password |
| 工具消息压缩破坏消息合法性 | 工具调用和 ToolMessage 成对处理，补 LangChain/OpenAI 兼容测试 |
| admin-web 与 trace 写入延迟不同步 | 保留轮询和手动刷新，snapshot 状态明确区分 building/unavailable |

## 验收标准

- 开发者从 `context/engine.py`、`context/planner.py`、`context/registry.py` 可以理解主流程。
- 六类 Context 在代码、文档、trace、admin-web 中命名一致。
- 新增 block key 必须通过注册表测试。
- 自动压缩发生时，后端 trace 能看到压缩决策，admin-web 能看到压缩后的最终入模内容。
- 工具结果压缩不再只显示 `[已执行 unknown]`，至少保留工具名、状态、参数摘要、结果摘要和 trace 引用。
- Playground 的 LLM Context 抽屉能展示最新 request 的最终 `system prompt + messages + budget + compression`。
- TraceMonitor 能区分 `context_build` 视角和 `final_llm_context` 视角。
