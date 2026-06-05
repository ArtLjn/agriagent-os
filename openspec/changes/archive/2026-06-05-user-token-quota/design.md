## Context

当前 token 统计系统按 farm_id 聚合，配额以全局日限额控制（100k/天）。系统已具备：
- `TokenDailyStats` 模型按 (farm_id, date, model, call_type) 聚合
- `quota_service.py` 实现日限额检查
- `graph.py` 在 LLM 调用前拦截超限请求
- Admin Token Dashboard 展示汇总统计
- Agent 请求链路已经在部分入口接收 `user_id`，但 `invoke_advisor` / `stream_advisor` / `TraceInfo` 尚未透传
- Agent Runtime 已有 `FinalPromptBudget` 做调用前 token 估算，但该估算不能作为真实扣量账本

需要扩展为：用户级统计 + 月/周双周期配额 + 超限拒绝 + VIP 差异化基础设施。

## Goals / Non-Goals

**Goals:**
- Token 统计细化到用户维度（user_id）
- 保留 farm_id 统计维度，避免未来一用户多农场时丢失农场级分析能力
- 支持月限额 + 周限额双周期检查
- 明确 token 统计准确性策略：真实账本只记录 provider 返回的 usage，估算值只用于预算和 trace
- 超限时直接拒绝，Agent 返回周期感知提示
- 全局默认限额，User 模型支持按用户自定义（VIP 预留）
- 管理员可查看/编辑每个用户的配额
- 前端展示月/周配额进度

**Non-Goals:**
- VIP 付费系统（仅预留配额字段，不实现计费流程）
- Token 用量通知/告警机制
- 按模型差异化计费
- 实时 WebSocket 配额推送

## Decisions

### 1. user_id 加到 TokenDailyStats，且保留 farm_id

**选择**: 在现有 `TokenDailyStats` 表新增 `user_id` 列，唯一约束调整为 `(user_id, farm_id, date, model, call_type)`。

**替代方案**: 创建独立 `UserTokenStats` 表。
**理由**: 单一数据源避免双写和数据不一致。保留 farm_id 可以继续支持农场级看板，也避免未来一用户多农场时不同农场的数据被合并到同一行。用户级统计通过按 user_id 聚合获得。

### 2. 周期范围纯计算，不存储周期记录

**选择**: `_get_month_range()` / `_get_week_range()` 纯函数计算日期范围，SQL `BETWEEN` 过滤。

**替代方案**: 创建 quota_periods 表存储每个周期的起止时间。
**理由**: 无额外表、无定时任务重置周期。日期是确定性的，纯计算更简单可靠。

### 3. 配额字段放 User 模型

**选择**: User 表新增 `token_monthly_limit` / `token_weekly_limit` 两个 nullable Integer 列。NULL = 使用全局默认。

**替代方案**: 独立 UserQuota 表。
**理由**: 仅两列，独立表增加 JOIN 开销和维护成本。未来如果配额维度增多再考虑拆分。

### 4. 配额检查以 user_id 为权威输入

**选择**: 新主链路从认证上下文取得 `current_user.id`，经 `chat_with_agent` / `stream_chat_with_agent` 传入 `invoke_advisor` / `stream_advisor`，再传入 `init_trace(user_id=...)` 和 LangGraph state。`check_user_quota(user_id, db)` 返回结构化 `QuotaCheckResult`。

**兼容**: `check_quota(farm_id)` 可临时保留为包装器，内部通过 Farm.user_id 反查后委托 `check_user_quota`，但不作为新代码入口。

**理由**: user_id 来自认证上下文更可信，也避免在 LLM 节点或 token 写入阶段反复通过 farm_id 反查。

### 5. TraceInfo 直接携带 user_id 和 call_type

**选择**: `TraceInfo` 新增 `user_id` 和 `call_type` 字段。`TraceCollector.record()` 在记录 `llm_call` token 用量时，将 `trace.user_id`、`trace.farm_id`、`trace.call_type` 一起传给 `TraceDAO.accumulate_token_stats()`。

**替代方案**: 在 `accumulate_token_stats` 中从 farm_id 反查 user_id，并固定 `call_type=chat`。
**理由**: user_id 和调用类型应该在请求入口确定。这样 chat、stream_chat、daily_advice、report 等调用可以进入同一统计表但保持可区分。

### 6. 配额动作统一为 warn / reject

**选择**: `TokenQuotaConfig.over_quota_action` 仅支持 `warn` 和 `reject`，默认 `reject`。历史前端中出现的 `block` 文案应改为 `reject` 或做兼容显示。

**理由**: Runtime 当前已按 `reject` 判断，配置页仍判断 `block`。统一枚举可以减少前后端分叉。

### 7. Admin stats 改造时补齐管理员鉴权

**选择**: 修改 `/admin/stats/tokens` 和 `/admin/stats/tokens/daily` 时同时加入 `require_admin` 依赖。

**理由**: 用户级 token 用量属于运营和隐私数据，不能在扩展 user_id 过滤时继续保持无管理员鉴权。

### 8. Token 真实账本以 provider usage 为准

**选择**: `TokenDailyStats` 只累计 LLM provider 响应中的真实 usage。优先读取 LangChain 标准 `AIMessage.usage_metadata`，再兼容 provider-specific `response_metadata.token_usage`，字段归一化为 `prompt_tokens`、`completion_tokens`、`total_tokens`。本地 `FinalPromptBudget` 和 `estimate_tokens()` 的结果只写入 trace，用于预算保护和调试，不进入配额账本。

**理由**: OpenAI-compatible API 会在响应 `usage` 中返回 prompt、completion、total token；DashScope 兼容接口也返回同类 usage 字段。LangChain 的 `AIMessage.usage_metadata` 是框架内承载 token counts 的标准位置。成熟监控系统也是基于 LLM token counts 计算成本。

### 9. 缺失 usage 时不静默扣量

**选择**: 当 LLM 响应缺失 provider usage 时，`TraceCollector` SHALL 记录 `usage_source="missing"` 的 trace 或 warning，但不写入 `TokenDailyStats`。可选地在 trace 中记录本地估算值 `estimated_prompt_tokens`，供排查使用，不参与 quota。

**替代方案**: 缺失 usage 时用本地估算值扣量。
**理由**: 本地估算可能与 provider 真实计费口径不同，尤其是工具调用、缓存、reasoning tokens 和不同模型 tokenizer。用估算扣量会让用户配额与账单不一致。

### 10. 流式调用尽量获取 usage，缺失时明确标记

**选择**: 对支持 OpenAI-compatible streaming 的 provider，流式 LLM 调用尽量启用 usage 返回能力。如果当前 LangChain provider 封装无法拿到流式 usage，流式入口在 trace 中标记 `usage_source="missing_stream_usage"`，并不累计真实账本。

**理由**: 没有最终 usage 时强行估算，会破坏统计准确性。第一阶段只做标记和不入账。

### 11. 第一阶段保持单一统计写入口

**选择**: 只在 `TraceCollector.record(node_type="llm_call")` 中累计 `TokenDailyStats`。API 层、Agent 层和预算估算层不直接写 token 统计。重试场景只统计最终成功响应；失败且无 usage 的响应不入账。

**理由**: 当前系统规模和写入路径较简单，单一写入口已经能避免重复统计，后续确实出现多写入口时再单独扩展。

## 成熟方案参考

- OpenAI API 响应通过 `usage` 返回 token 用量；流式响应可通过 `stream_options: {"include_usage": true}` 请求最终 usage。
- LangChain `AIMessage` 在可用时通过 `usage_metadata` 暴露标准 token counts。
- LangSmith 成本追踪基于模型、provider 定价和 LLM token counts 计算。
- DashScope OpenAI-compatible 响应返回 `usage.prompt_tokens`、`usage.completion_tokens`、`usage.total_tokens` 等字段。

## Risks / Trade-offs

- **[数据库迁移]** TokenDailyStats 已有数据的 user_id 为 NULL → 迁移时通过 JOIN farms 回填，新数据从 init_trace 获取。
- **[唯一约束变更]** 从 (farm_id, date, model, call_type) 改为 (user_id, farm_id, date, model, call_type) → 需要重建约束，旧数据中 user_id 回填后约束一致。
- **[并发写入]** UPSERT 无锁在高并发下可能丢失计数 → 当前用户量小可接受，后续可加悲观锁或 INSERT ON CONFLICT。
- **[前端 QUOTA_LIMIT 不一致]** 当前前端硬编码 10000，后端 100000 → 改为从后端 API 获取实际配额值。
- **[历史调用缺 user_id]** 早期或脚本调用可能没有认证用户 → 配额主链路应拒绝缺失 user_id 的 LLM 请求，迁移和统计查询可允许历史 NULL 数据存在。
- **[流式 usage 缺失]** 如果 provider 或 LangChain 封装无法返回流式 usage，流式调用短期可能只进入 trace 不进入 TokenDailyStats。第一阶段只标记缺口，不做估算扣量。
