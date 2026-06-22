## Context

### 现状

当前会话压缩是 5 道关卡串行的"截断 / 丢弃"，没有 LLM 语义摘要（详见 [farm-manager-design-spec/01_正式设计/03_Context工程 § 6.1](../../../farm-manager-design-spec/01_正式设计/03_Context工程.md#61-实际实现5-道关卡串行过滤)）：

1. `ContextBuilder` 预算默认 1200 token，policy 模式仅 512-900
2. `compressors/text.py` 只有 `text[:max_chars-1] + "…"` 截断
3. `ConversationSelector` 仅取最近 6 条 message
4. `sliding_window_compact` 把旧 ToolMessage 替换为 `[已执行 xxx]` placeholder
5. `FinalPromptBudget` 的 `summarize_old_messages` 也是截断拼接，不是真摘要

更严重：`MemoryService.set_session_summary()` 在 [backend/app/memory/short_term/store.py:44](../../../backend/app/memory/short_term/store.py#L44) 定义但**全代码无调用方**；`conversations.summary` / `summary_updated_at` 字段已存在却从未被写入。spec 层（`short-term-memory-policy` § 会话摘要、`conversation-management` § 历史超过窗口时摘要替代）早已声明该能力，代码层是空白。

### 约束

- 生产环境 2C4G 单机，systemd 单 uvicorn 进程
- 生产 LLM：qwen3.6-35b-a3b（DashScope，OpenAI 兼容），无便宜模型分支
- 单户月成本预算 ≤ ¥30（spec [02_非功能性需求](../../../farm-manager-design-spec/02_产品需求/02_非功能性需求.md)）
- 现有 LLM 抽象 + 熔断器（`backend/app/agent/runtime/llm_support.py`）必须复用
- 零 schema 迁移（`conversations.summary` 字段已存在）

## Goals / Non-Goals

**Goals**：

- 接通 `set_session_summary` 自动生成，按阈值异步触发
- 摘要写入 `conversations.summary`，重启不丢
- ConversationSelector 注入 summary，让 LLM 在第 13+ 轮仍能回忆前 12 轮
- 摘要失败有降级路径，不影响主流程
- 单户月增成本 < ¥2

**Non-Goals**：

- 不上 Redis / 向量库（spec 已声明，详见 [04_Memory工程 § 13](../../../farm-manager-design-spec/01_正式设计/04_Memory工程.md)）
- 不上 MemGPT / Letta 自治 memory 模型
- 不引入新 LLM provider（如 Haiku），复用现有 qwen
- 不改 LangGraph 拓扑（保持现有 Response 节点不变，仅在末尾挂异步任务）
- 不做跨 session 长期记忆（由 `add-long-term-memory-observations` 单独承接）
- 不做 prompt-level 摘要缓存（成本敏感场景再考虑）
- 不扩 ConversationSelector 默认窗口

## Decisions

### D1：阈值触发，不每轮触发

**选择**：messages ≥ 12 时异步触发，且距离上次 summary 更新 > 阈值（默认 30 分钟）才再次触发。

**理由**：
- 每轮触发成本爆炸（单户月成本将达 ¥30+，超预算）
- 12 条对应大约 6 轮（user + assistant 各 1 条），是用户感知失忆的临界点
- 时间窗口防抖避免高频对话反复重写摘要

**Alternatives**：
- 每 N 轮触发（rejected：N 难调）
- 按 token 阈值触发（rejected：需要每次重算 token，浪费 CPU）
- 手动触发（rejected：用户不会主动调）

### D2：Running Summary 模式（追加而非重写）

**选择**：摘要输入 = `current_summary + 最近被推出窗口的 N 条 message`，输出追加到 summary 末尾。已固定部分不重写。

**理由**：
- 重写整段 summary 每次都要喂全部历史，token 成本线性增长
- Running summary 摘要输入恒定（旧 summary + 新一段），成本稳定
- 已固定部分被"封存"不会被新 LLM 调用意外改写

**Alternatives**：
- 全量重写（rejected：成本高、不稳定）
- 多个分片摘要（rejected：复杂度过高）

### D3：复用 qwen3.6-35b-a3b，不引入便宜模型

**选择**：摘要调用走主模型 qwen3.6-35b-a3b。

**理由**：
- qwen 单价已经很低（输入 ¥0.5/M token、输出 ¥1/M token），单次摘要 ~¥0.005
- 引入新 provider 需要：新建 client、配额管理、监控、熔断——收益不抵成本
- 摘要 prompt 简单，35B 足够

**Alternatives**：
- 引入 Qwen-Turbo 或国内更便宜模型（rejected：运维负担）
- 等待 Anthropic Haiku 国内可用（rejected：不可控时间）

### D4：异步触发，挂载在 Response 节点之后

**选择**：在 `_llm_node` 完成 LLM 响应后，`asyncio.create_task(memory_service.maybe_summarize(...))` 异步触发。

**理由**：
- 同步触发会让用户多等 1-3s（不可接受）
- 异步任务的失败不影响主流程（已 catch all）
- 用户感知不到摘要生成，下一轮才用上

**Alternatives**：
- 在 Advisor 入口同步触发（rejected：增加首 token 延迟）
- 后台 cron 任务批量跑（rejected：用户等不及时）

### D5：摘要失败降级到现有截断逻辑

**选择**：摘要 LLM 调用失败 / 超时 / 内容为空 → 不更新 `conversations.summary`，让现有 `FinalPromptBudget.summarize_old_messages` 字符串截断兜底。

**理由**：
- 不能因摘要失败导致主流程崩溃
- 现有截断虽然丢信息但能用
- 通过熔断器（`_record_llm_failure`）记录失败，超阈值自动降级一段时间

### D6：ConversationSelector 注入位置

**选择**：在 selector 查询时 LEFT JOIN `conversations` 表取 `summary`，作为单独 ContextBlock（key=`conversation_summary`，priority=50，compressible=True，min_tokens=64），插在最近窗口之前。

**理由**：
- 与最近窗口（priority=55）分开，便于独立压缩 / 丢弃
- 优先级低于 pending_action（95）、最近窗口（55），保证近期信息不被挤掉
- 高于 ledger / weather，因为摘要是"工作记忆"层

### D7：State Protect —— 强制保留结构化字段

**选择**：摘要 prompt 模板**强制要求**保留：金额、日期、地块/作物名、人名、pending action 类型与关键参数。

**理由**：
- 借鉴 Claude Code "protect context" 思路（[DecodeClaude Deep Dive](https://decodeclaude.com/compaction-deep-dive/)）
- 这些字段是用户最常追问的"指代对象"，丢了就完全失忆
- 通过 trace 监控关键字段命中率，量化摘要质量

### D8：feature flag 控制

**选择**：新增 `ai.enable_session_summary`（默认 true），可热关闭。

**理由**：
- 上线初期可以快速回滚而不重新部署
- A/B 测试时可以对照效果

## Risks / Trade-offs

| Risk | Mitigation |
| --- | --- |
| 摘要 LLM 调用增加 DashScope 配额压力 | 阈值触发 + 时间窗口防抖，单户日均 ≤ 10 次；监控 429/超时率 |
| 摘要丢关键信息（金额/日期） | D7 强制 prompt + trace 监控关键字段命中率 < 90% 触发告警 |
| 异步任务异常拖累 event loop | `asyncio.create_task` 内全 catch，任务长度限制 30s 超时 |
| 并发写 `conversations.summary`（多请求同 session） | `summary_updated_at` 时间戳乐观锁；版本旧的不覆盖新的 |
| 摘要 prompt 与人设/语言不一致 | prompt 模板走 PromptComposer，复用人设变量 |
| 用户跨 session 仍失忆 | 本提案只解决同 session 工作记忆；跨 session 偏好由 `add-long-term-memory-observations` 后续解决 |
| 摘要生成延迟，用户感知 | 异步触发，下一轮才生效；首启可接受 1-2 轮"过渡期" |
| 历史数据未回填 | 明确不回填，从接入日起向前生成；老 session 仍走截断 |

## Migration Plan

### 部署步骤

1. 合并 PR → CI 跑仿真 smoke 集（5 条核心用例）
2. 部署到 staging，feature flag 默认 false，跑 2 小时观察
3. staging 开启 feature flag，跑 24 小时观察 trace：
   - 摘要触发频率
   - LLM 调用成功率
   - 关键字段命中率（人工抽检 20 条）
4. 部署生产，feature flag 默认 false
5. 生产开启 feature flag（5 个内测农户），观察 1 周
6. 全量开启

### Rollback

- 关闭 `ai.enable_session_summary` 即可
- `conversations.summary` 字段允许保留（不影响功能）
- 不需要回滚 DB schema

## Open Questions

1. **摘要触发阈值最终值**：默认 12 条是否合适？需要 staging 数据验证。备选 8 / 15。
2. **时间窗口防抖最终值**：30 分钟是否过长？备选 10 / 60。
3. **ConversationSelector 注入 priority**：50 vs 55 vs 45，需要 trace A/B 后定。
4. **摘要最大长度**：默认 500 token 是否够？可能需要根据真实样本调整。
5. **是否记 trace 单独的 `summary_generated` event**：便于评测，但增加 trace 体积。
