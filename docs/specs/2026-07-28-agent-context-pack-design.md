# Agent Context Pack 稳定多轮上下文设计

## 1. 背景

当前 farm-manager 已经具备多轮 Agent 所需的大部分基础能力：

- `conversationMessages` 保存完整会话消息，当前配置可走 Mongo。
- `conversations.summary` 保存会话 running summary。
- `MemoryService` 能构建 `MemoryContext`，包含最近消息、会话摘要、pending action、临时任务状态和长期记忆。
- `ContextBuilder` / `MemorySelector` / `ConversationSelector` 能把记忆和业务事实注入 prompt。
- `FinalPromptBudget` 能对过长消息和工具结果做兜底压缩。

但多轮对话稳定性仍存在结构性风险。主要原因不是某一个摘要 prompt 不够好，而是上下文事实源、压缩边界和最终入模形态不统一：

1. `conversation_summary`、`short_term_summary`、`conversation`、`short_term_recent` 和 Advisor 历史 `messages` 可能同时存在，内容来源和窗口不同。
2. `MemoryService.maybe_summarize()` 的 prompt 要求输出“新增摘要段落”，但 service 实际覆盖写入 `conversation.summary`，契约不一致。
3. 会话摘要没有稳定的 `summarized_until_message_id` 边界，系统无法判断哪些消息已被摘要覆盖。
4. running summary 当前会读取整个 session 消息，容易反复总结、重复、漂移或改写旧事实。
5. 最终 prompt 预算压缩与会话摘要压缩是两套机制，缺少统一诊断视图。

本设计提出 `Context Pack` 作为 Agent 入模上下文的稳定契约：存储层保真，压缩层有边界，入模层只有一种历史形态。

## 2. 目标

1. 为多轮对话建立唯一、可解释、可恢复的上下文入模结构。
2. 明确完整消息、会话摘要、最近原文、pending 状态和长期记忆的边界。
3. 引入压缩游标，避免重复总结全量历史。
4. 收敛重复注入路径，避免同一段会话以多种形式进入 prompt。
5. 让压缩行为可观测：每轮能知道 summary 覆盖到哪里、最近原文用了哪些消息、哪些 block 被压缩或丢弃。
6. 保持渐进式落地，不一次性重写 Agent Runtime、Context Engine 和 Memory 全部实现。

## 3. 不做

- 不引入 Redis 作为短时记忆主存。
- 不把 Mongo trace 作为 Agent 决策输入。
- 不把完整历史会话全部塞进 prompt。
- 不把所有旧消息写入 RAG。
- 不重写所有 selector。
- 不在本设计中实现完整 Claude Code 式五层压缩状态机。
- 不改变 pending action 的业务执行语义。

## 4. 一句话架构

```text
conversationMessages / conversations.summary / pending state / memory_records
  -> ContextLedger 读取事实源
  -> CompactionCursor 标记摘要边界
  -> CompactionPolicy 决定是否更新摘要
  -> ContextPack 组装唯一入模上下文
  -> ContextRenderer 渲染给 Agent
```

核心原则：

```text
完整历史保存在存储层。
模型只看：唯一会话摘要 + 最近 N 条原文 + 当前结构化状态 + 必要业务事实。
```

## 5. 设计原则

### 5.1 事实源唯一

| 数据 | 事实源 | 说明 |
| --- | --- | --- |
| 完整会话消息 | `conversationMessages` | 当前可按配置走 Mongo，是会话历史事实源。 |
| 会话摘要 | `conversations.summary` | 是 session 级压缩事实源。 |
| 摘要边界 | 新增 `conversation_context_cursors` 或 `conversations.meta_json` | 记录摘要覆盖到哪条消息。 |
| 待确认动作 | `pending_actions` 表或现有 pending store | 必须是结构化状态，不依赖自然语言摘要恢复。 |
| 临时任务状态 | `agent_task_states` 或现有 task state store | 任务进度以结构化状态为准。 |
| 长期记忆 | `memory_records` | 只存 confirmed 偏好和关键事实。 |
| in-memory short_term | 缓存层 | 不作为事实源。重启或多 worker 时可丢。 |

### 5.2 入模形态唯一

最终 prompt 中，历史对话只允许以下组合：

```text
conversation_summary
recent_messages
```

不再同时注入：

```text
conversation + short_term_recent + conversation_summary + short_term_summary
```

其中：

- `conversation_summary` 来自 `conversations.summary`。
- `recent_messages` 来自 `conversationMessages`，按摘要边界之后和最近窗口选择。
- `short_term_recent` 仅保留兼容或缓存用途，不作为聊天主链路的入模 block。
- `short_term_summary` 不再独立注入，避免与 `conversation_summary` 双写双读。

### 5.3 摘要是可替换快照，不是追加流水账

摘要 prompt 应输出“完整新版摘要”，而不是“追加段落”。

原因：

- 追加式容易重复膨胀。
- 追加式难以修正旧事实。
- 追加式会让“已确认”“待确认”“被用户纠正”的状态混在一起。
- 完整新版摘要更容易控制长度和结构。

### 5.4 压缩必须有边界

每次摘要成功后必须记录：

```text
summarized_until_message_id
summarized_until_created_at
summary_version
summary_hash
```

下一次摘要只处理边界之后的新消息。

### 5.5 结构化状态优先于自然语言摘要

pending action、pending plan、task state 不能只依赖 summary 保存。它们应以结构化 block 进入 prompt，且优先级高于 conversation summary。

## 6. 核心概念

### 6.1 ContextLedger

`ContextLedger` 是上下文事实读取层。它不做 prompt 拼接，也不做 LLM 摘要，只负责从可信事实源构建原始上下文账本。

建议职责：

```python
class ContextLedger:
    async def load_conversation(self, farm_id: int, session_id: str) -> ConversationSnapshot:
        pass

    async def load_cursor(self, conversation_id: int) -> CompactionCursor | None:
        pass

    async def load_recent_messages(self, conversation_id: int, limit: int) -> list[MessageSnapshot]:
        pass

    async def load_messages_after(
        self,
        conversation_id: int,
        message_id: int | None,
        limit: int,
    ) -> list[MessageSnapshot]:
        pass

    async def load_pending_state(self, farm_id: int, session_id: str) -> PendingStateSnapshot:
        pass

    async def load_long_term_memory(self, user_id: str, farm_id: int) -> LongTermMemorySnapshot:
        pass
```

边界：

- 可以依赖 conversation repository、pending store、task state store、long-term memory store。
- 不依赖 Agent Runtime。
- 不渲染 prompt 文本。
- 不调用 LLM。

### 6.2 CompactionCursor

`CompactionCursor` 记录会话摘要覆盖边界。

建议字段：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `conversation_id` | int | 会话 ID。 |
| `session_id` | str | 会话外部 ID，便于排查。 |
| `farm_id` | int | 农场隔离。 |
| `summary_version` | int | 摘要版本，乐观锁和诊断用。 |
| `summarized_until_message_id` | int \| null | 摘要覆盖到的最后一条消息。 |
| `summarized_until_created_at` | datetime \| null | 辅助诊断和边界校验。 |
| `summary_hash` | str | 当前摘要 hash，检测重复或异常覆盖。 |
| `updated_at` | datetime | 更新时间。 |

存储选择：

| 方案 | 做法 | 优点 | 缺点 |
| --- | --- | --- | --- |
| A | 新表 `conversation_context_cursors` | 结构清晰，可扩展 | 需要迁移 |
| B | 放入 `conversations.meta_json.context_cursor` | 改动小 | 查询和约束弱 |

推荐：先用 B 验证链路，稳定后如字段增多再迁到独立表。

### 6.3 ContextPack

`ContextPack` 是最终给 `ContextBuilder` 或 Agent Runtime 消费的稳定结构。

```python
@dataclass(frozen=True)
class ContextPack:
    conversation_id: int | None
    session_id: str | None
    farm_id: int
    user_id: str | None
    summary: ConversationSummaryBlock | None
    recent_messages: list[MessageSnapshot]
    active_state: ActiveStateSnapshot
    long_term_memory: LongTermMemorySnapshot
    business_blocks: list[ContextBlock]
    diagnostics: ContextPackDiagnostics
```

其中 `summary` 应包含：

```python
@dataclass(frozen=True)
class ConversationSummaryBlock:
    content: str
    version: int
    summarized_until_message_id: int | None
    summarized_until_created_at: datetime | None
```

`diagnostics` 应包含：

```python
@dataclass(frozen=True)
class ContextPackDiagnostics:
    recent_message_ids: list[int]
    summary_version: int | None
    summary_hash: str | None
    token_estimate: int
    selected_blocks: list[str]
    compressed_blocks: list[str]
    dropped_blocks: list[str]
    compaction_reason: str | None
```

## 7. 数据流

### 7.1 一轮普通聊天

```text
POST /agent/chat
  -> 创建 conversation / turn
  -> 保存 user message 到 conversationMessages
  -> pending 优先判断
  -> ContextPackService.build()
       -> load conversation
       -> load summary + cursor
       -> load recent messages
       -> load active state
       -> load business context
       -> load long-term memory
       -> render stable ContextPack
  -> Agent Runtime
  -> 工具调用 / LLM 回复
  -> 保存 assistant message
  -> 后台 maybe_compact_session()
```

### 7.2 会话压缩

```text
maybe_compact_session(conversation_id)
  -> 读取 conversation.summary + cursor
  -> 查询 cursor 后的新消息
  -> 判断是否达到压缩条件
  -> 调用 summary LLM 生成完整新版摘要
  -> 乐观锁写入 conversations.summary
  -> 更新 cursor 到最新 message_id
  -> 记录 compaction trace
```

### 7.3 Prompt 入模

```text
System Prompt
  + [Session Summary]    # 唯一会话摘要
  + [Recent Messages]    # 最近 N 条原文
  + [Active State]       # pending action / task state
  + [Business Context]   # farm / cycle / ledger / weather
  + [Long Term Memory]   # confirmed preferences / key facts
  + [Output Contract]
```

## 8. 摘要设计

### 8.1 触发条件

建议从固定条数升级为多条件：

| 条件 | 建议阈值 | 说明 |
| --- | --- | --- |
| cursor 后新增消息数 | >= 8 | 约 4 轮对话。 |
| recent message token | >= 1200 | 避免长消息挤占 prompt。 |
| conversation summary 为空且消息数 | >= 6 | 首次摘要可更早建立上下文。 |
| 任务阶段变化 | 可选 | 例如 pending plan 完成、创建茬口流程结束。 |
| prompt 接近水位线 | 可选 | 作为响应式压缩。 |

初期推荐只实现前 3 个，避免过度复杂。

### 8.2 摘要输入

摘要 LLM 输入必须明确区分：

```text
【现有摘要】
【当前目标】
- 用户正在规划西棚黄瓜种植和成本记录。

【新增消息】
仅包含 summarized_until_message_id 之后的消息

【当前结构化状态】
pending_action / task_state 的安全摘要
```

禁止把整个 session 消息伪装成“新增消息”。

### 8.3 摘要输出

摘要 LLM 输出完整新版摘要，格式固定：

```text
【当前目标】
- 用户正在确认西棚黄瓜的浇水安排和成本记录。

【稳定事实】
- 西棚当前作物为黄瓜，用户提到预算金额为 200 元。

【用户偏好】
- 用户偏好用简体中文、直接给出可执行建议。

【已确认事项】
- 已确认需要记录与西棚黄瓜相关的农事成本。

【待确认/待办】
- 待确认是否创建一笔 200 元的成本记录。

【更正记录】
- 用户曾将金额从 250 元更正为 200 元，以 200 元为准。

【最近话题】
- 最近在讨论明天是否浇水以及如何记录成本。
```

规则：

- 必须保留金额、日期、地块、作物、人员、数量、状态和 pending 参数。
- 用户纠正过的信息必须进入“更正记录”，并以最后一次纠正为准。
- 待确认事项不能写成已完成。
- 已完成事项不能继续写成待确认。
- 不写寒暄。
- 不输出 Markdown 表格，避免长宽不可控。
- 总长度目标 300-600 tokens。

### 8.4 摘要失败降级

| 场景 | 行为 |
| --- | --- |
| LLM 调用失败 | 保留旧 summary，不更新 cursor。 |
| 输出为空 | 保留旧 summary，不更新 cursor。 |
| 输出超长 | 先 deterministic trim，再写入。 |
| 乐观锁冲突 | 重新读取 summary 和 cursor，下一轮重试。 |
| Mongo 读取失败 | 降级使用旧 summary + 当前请求，不阻断主链路。 |

## 9. 最近消息窗口

### 9.1 选择规则

`recent_messages` 应来自 `conversationMessages`，而不是 in-memory deque。

建议：

```text
默认保留最近 8 条消息，最多 12 条。
如果 summary 为空，可保留最近 12 条。
如果 summary 存在且有 summarized_until_message_id，只保留该边界之后的新消息，不回填已被 summary 覆盖的旧消息。
当前用户消息如果已在 DB 中，构建 LLM messages 时去重，避免重复出现。
```

### 9.2 与 Advisor messages 的关系

当前 Advisor 会单独构建 LangChain `messages`。新设计下应收敛为：

```text
ContextPack.recent_messages -> LangChain messages
ContextPack.summary -> system context section
```

也就是说，Advisor 不再直接调用 `async_get_recent_messages()` 自行决定窗口；它消费 `ContextPack` 给出的 recent messages。

### 9.3 与 ConversationSelector 的关系

`ConversationSelector` 不再独立注入 `conversation` block。它的职责迁移到 `ContextPackService`。

兼容期可以保留 `ConversationSelector`，但必须通过策略关闭其中一个入口：

```text
chat runtime 使用 ContextPack.recent_messages
legacy ContextBuilder 使用 ConversationSelector
二者不能同时进入同一轮最终 prompt
```

## 10. Active State 设计

`ActiveState` 是会话中不能被自然语言摘要替代的结构化状态。

包含：

- `pending_action`
- `pending_plan`
- `temporary_task_state`
- `active_agent_task_state`

入模规则：

| block | 优先级 | 是否可压缩 | 说明 |
| --- | --- | --- | --- |
| `pending_action` | 最高 | 否 | 用户确认流必须准确。 |
| `pending_plan` | 最高 | 否 | 多步计划确认必须准确。 |
| `temporary_task_state` | 高 | 可结构化裁剪 | 保留 task_id、status、关键 data。 |
| `active_agent_task_state` | 高 | 可结构化裁剪 | 保留任务阶段、完成/待办步骤。 |

摘要可以引用 active state，但不能成为 active state 的唯一来源。

## 11. Long-Term Memory 设计

长期记忆只放 confirmed 信息：

- 用户明确偏好。
- 农场稳定画像。
- 关键事实。
- 周期摘要。
- 账务摘要。

不放：

- 临时计划。
- 待确认动作。
- 未验证推测。
- 工具 trace。
- 整段对话摘要。

入模时只取与当前用户、农场和意图相关的少量条目。长期记忆优先级低于 active state 和业务事实。

## 12. ContextPack 渲染

建议最终 prompt section：

```text
[Role & Policies]
助手角色、写操作确认规则、输出约束

[Task]
pending_action / task_state

[Conversation]
session_summary
recent_messages

[Business Context]
farm / cycle / ledger / weather / workers

[Long Term Memory]
confirmed preferences / key facts

[Output]
response contract / clarification rules
```

渲染约束：

- 每个 section 有固定顺序。
- 每个 block 有来源和边界 metadata。
- `recent_messages` 保留 role、message_id、created_at。
- summary 标明覆盖边界。

示例：

```text
[Conversation]
session_summary(version=4, summarized_until_message_id=1234):
【当前目标】
- 用户正在规划西棚黄瓜种植和成本记录。

recent_messages:
- #1235 user: 明天要浇水吗？
- #1236 assistant: 建议结合天气和土壤湿度判断，若土壤偏干可在早晨少量浇水。
```

## 13. 预算与压缩

### 13.1 预算优先级

```text
required active state
  > 当前用户消息
  > 最近消息
  > 业务事实
  > 会话摘要
  > 长期记忆
  > RAG evidence
  > 低优先级列表类上下文
```

说明：

- pending action 即使超预算也不能丢。
- 当前用户消息不能压缩。
- 最近消息优先保真。
- 摘要可裁剪，但不能裁掉字段标题和关键数字。
- 长期记忆可少取，不应挤掉当前任务状态。

### 13.2 Micro Compact

工具结果和旧中间消息做 micro compact：

```text
最近 2-3 轮工具结果保留完整。
更早工具结果替换为结构化摘要。
大 JSON 工具结果保留 count、status、关键字段、trace ref。
```

结构：

```text
[工具结果已压缩]
tool: manage_cost
status: success
summary: 查询到 3 条成本记录，总额 320 元。
ref: request_id=req_20260728_001, node_id=tool_manage_cost_01
```

### 13.3 仍超预算时

如果压缩后仍超预算：

1. 丢弃低优先级长期记忆。
2. 裁剪业务长列表。
3. 裁剪 summary 的低价值条目。
4. recent messages 从 12 条降到 8 条。
5. 仍超预算则记录 warning trace，但不阻断主链路。

## 14. 可观测性

每轮 Agent 请求应记录 `context_pack` trace：

```json
{
  "context_pack_id": "ctx_20260728_001",
  "conversation_id": 12,
  "session_id": "s1",
  "summary_version": 4,
  "summarized_until_message_id": 1234,
  "recent_message_ids": [1235, 1236, 1237],
  "selected_blocks": ["pending_action", "conversation_summary", "recent_messages", "farm"],
  "compressed_blocks": ["ledger"],
  "dropped_blocks": ["long_term_memory"],
  "token_estimate_before": 1800,
  "token_estimate_after": 950,
  "compaction_reason": "new_messages_threshold"
}
```

会话压缩应记录 `context_compaction` trace：

```json
{
  "conversation_id": 12,
  "previous_summary_version": 3,
  "next_summary_version": 4,
  "input_message_ids": [1228, 1229, 1230, 1231, 1232, 1233, 1234],
  "summarized_until_message_id": 1234,
  "summary_length": 620,
  "summary_hash": "sha256:7f2c4b0c8f9a1d23",
  "status": "success"
}
```

trace 只能保存安全摘要，不保存完整 prompt、密钥、请求头或大段 RAG 原文。

## 15. 兼容迁移

### Phase 1：修正摘要契约

- 修改 summary prompt：输出完整新版摘要。
- `maybe_summarize()` 覆盖写入变得契约一致。
- 新增测试覆盖旧摘要 + 新消息 -> 完整新版摘要。

### Phase 2：引入 cursor

- 在 `conversations.meta_json.context_cursor` 中记录摘要边界。
- `maybe_summarize()` 只读取 cursor 后的新消息。
- 摘要成功后更新 cursor。

### Phase 3：引入 ContextPackService

- 新增 `ContextPackService.build()`。
- Advisor 主链路改为消费 `ContextPack.recent_messages`。
- ContextBuilder 兼容消费 ContextPack。

### Phase 4：关闭重复注入

- 聊天主链路关闭 `ConversationSelector` 的 `conversation` block 或关闭 Advisor 自建 history，两者保留一个。
- `short_term_recent` 不再进入聊天主链路 prompt。
- `short_term_summary` 不再独立注入。

### Phase 5：完善可观测

- 增加 `context_pack` trace。
- admin 调试页展示 summary boundary、recent message ids、压缩/丢弃 blocks。

## 16. 测试策略

### 16.1 单元测试

- summary prompt 输出完整新版摘要。
- cursor 后新消息为空时跳过压缩。
- cursor 后新消息达到阈值时触发压缩。
- 压缩成功后更新 `summarized_until_message_id`。
- 压缩失败时旧 summary 和 cursor 不变。
- recent messages 来自 conversation repository。
- `pending_action` 不被 summary 替代，也不被预算丢弃。

### 16.2 集成测试

- 多轮对话 20 条消息后，最终 prompt 只包含一份 summary 和最近原文。
- 用户纠正事实后，新 summary 以最后纠正为准。
- 服务重启后仍能从 Mongo + `conversations.summary` 恢复上下文。
- 多 worker 场景不依赖 in-memory short_term 恢复 recent messages。
- summary 生成失败时主聊天仍可返回。

### 16.3 回归测试

- pending confirmation 不被普通对话流程吞掉。
- 显式长期记忆仍能写入 `memory_records`。
- RAG evidence 不被写入 session summary。
- Mongo 不可用时按现有 repository fallback 策略降级。

## 17. 风险与取舍

| 风险 | 影响 | 缓解 |
| --- | --- | --- |
| cursor 放在 `meta_json` 查询弱 | 后续诊断不如独立表方便 | Phase 1 先小步验证，后续迁表。 |
| summary 输出完整新版摘要成本略高 | LLM token 成本上升 | 只总结 cursor 后新消息，整体成本可控。 |
| 关闭重复注入可能影响短期效果 | 某些场景少了一份上下文 | 用 trace 对比，保留 feature flag 灰度。 |
| prompt 格式变更影响模型行为 | 回答风格可能变化 | 增加多轮稳定性测试和灰度配置。 |
| Advisor 与 ContextBuilder 改造有交叉 | 容易改出重复入口 | 先引入 ContextPack，再逐步切消费者。 |

## 18. 验收标准

1. 一轮最终 prompt 中，历史对话只出现 `conversation_summary + recent_messages` 一套结构。
2. `conversation.summary` 与 summary prompt 契约一致，输出完整新版摘要。
3. 每次摘要成功后有明确 `summarized_until_message_id`。
4. 下一次摘要只处理 cursor 后的新消息。
5. 服务重启后，recent messages 能从 `conversationMessages` 恢复。
6. pending action 和 task state 以结构化 block 进入 prompt，不依赖 summary 恢复。
7. trace 能展示 summary version、boundary、recent message ids、压缩和丢弃决策。
8. 多轮回归测试能覆盖至少 20 条消息的稳定上下文恢复。

## 19. 推荐结论

farm-manager 不需要立即引入 Redis 或完整复制 Claude Code 的多层压缩状态机。当前更值得优先做的是：

```text
ContextPack + summarized_until_message_id + 唯一 summary + 最近原文窗口
```

这套设计能解决当前最影响多轮稳定性的三个问题：

1. 摘要没有边界。
2. 历史上下文重复注入。
3. summary 契约与写入语义不一致。

完成这三个收束后，再考虑更高级的 prompt-too-long recovery、工具结果分层压缩和 admin-web LLM Context 可视化。
