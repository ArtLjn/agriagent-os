# Agent Context Trace 摘要证据链

## 背景

Sectioned Context、外部 RAG 只读接入、Task Context 持久化和显式长期记忆已落地。Phase 5 补齐 Context/RAG/Tool 调试证据，但 trace 只做旁路诊断，不进入 Agent 的运行时必需路径。

## 落地范围

- 新增 `app.context.trace.build_context_trace_payload()`，从 `ContextBundle` 构造可落 Mongo 的安全摘要。
- `ContextBuilder._record_trace()` 写入新的 trace payload，不再直接写 `bundle.summary()`。
- trace `input_data` 只保留 `block_count`、`selected_keys` 和可用时的 `policy_intent`。
- RAG metadata 增加 `source_count`、`top_score` 和安全 source 摘要，便于定位检索质量问题。
- TraceCollector 或 Mongo 写入失败继续静默降级，不影响 `ContextBuilder.build()` 返回。

## Payload 边界

Mongo trace 可保存：

- `token_budget` / `token_estimate`。
- selected、compressed、dropped block 的摘要。
- `selector_errors`、`allowlist_filtered_keys`、`context_dependency_diagnostics`。
- policy 摘要：intent、selected tool names、enabled layers、dependency keys。
- section 摘要：分区名、token 估算、block key/source/purpose/required/compressed/reason。
- 每个 block 的短 preview，已截断并做敏感信息脱敏。

Mongo trace 不保存：

- 完整 `ContextBundle` 正文。
- 完整 prompt 正文。
- RAG 原始 chunk 全文、原始请求头、原始大 JSON。
- API key、Authorization、token、secret、password。
- 带明文密码的 Mongo URI。

## RAG Trace 摘要

`rag_knowledge` block 的 trace 摘要只保留：

- collection。
- requested mode 和 actual mode。
- warning。
- source_count。
- top_score。
- 前 5 条 source 摘要：doc_id、chunk_index、score，以及 `source/title/url/collection` 等安全 metadata。

RAG 检索失败且降级为空 block 时，trace 仍可通过 `selector_metadata.knowledge` 保存 `rag_called`、`rag_unavailable`、`rag_error_code`、`rag_error_summary` 等轻量字段。

## 明确不做

- 不新增数据库表。
- 不改变 selector 业务查询逻辑。
- 不改变 TokenBudget 语义。
- 不改变 RAG 触发策略。
- 不把 Mongo trace 作为主决策依赖。
- 不把 trace payload 作为 prompt 或工具调用输入。
