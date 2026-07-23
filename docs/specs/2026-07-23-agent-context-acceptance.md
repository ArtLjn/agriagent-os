# Agent Context 架构验收套件

## 背景

Context 第一阶段已合入 Sectioned Context、外部 RAG 只读、TaskState 持久化、TaskState 写入闭环、显式长期记忆和 Context trace payload。本验收只证明当前 Context 架构完整可用、稳定即可，不扩展农业知识库内容，不新增长期记忆管理入口。

## 验收场景

| 场景 | 验收测试 | 关键断言 |
| --- | --- | --- |
| Sectioned Context | `tests/context/test_context_architecture_acceptance.py::test_sectioned_context_renderer_keeps_stable_runtime_sections` | `ContextRenderer` 稳定输出 Role & Policies / Task / Evidence / Context / Output，并按 block key 分区。 |
| RAG 触发与隔离 | `tests/context/test_context_architecture_acceptance.py::test_runtime_context_routes_fake_rag_to_evidence_for_diagnosis_and_skips_accounting` | 诊断类问题通过 fake RAG client 产生 `rag_knowledge` 并进入 Evidence；记账/查账类请求不触发 RAG。 |
| TaskState 闭环 | `tests/context/test_context_architecture_acceptance.py::test_task_state_written_after_missing_info_is_visible_in_next_runtime_context` | 本轮回复要求补充信息后写入 `waiting_user` TaskState，下一轮 Runtime Context 能读到 `active_task_state`。 |
| 显式长期记忆 | `tests/context/test_context_architecture_acceptance.py::test_explicit_long_term_memory_is_injected_for_new_session_same_farm_user` | 用户明确“记住我以后用亩”后，同 farm/user 的新 session 可注入 `long_term_memory`。 |
| Trace 安全摘要 | `tests/context/test_context_architecture_acceptance.py::test_context_trace_payload_keeps_only_safe_acceptance_summary` | Context trace 只保存 selected keys、分区摘要、RAG source 摘要，不包含完整 context、完整 RAG chunk、请求 token 或 RAG 密钥。 |

## 边界

- RAG 验收只使用 fake client，不依赖真实 API key、embedding key 或外部 RAG 服务。
- 测试覆盖当前架构链路，不新增生产行为。
- `docs/specs/2026-07-18-agent-context-storage-design.md` 在当前 `origin/main` 树中不存在，本验收以现有代码和 `2026-07-22-agent-context-trace-payload.md` 为依据。

## 剩余风险

- 测试数据库仍使用 SQLite，不能覆盖生产数据库索引、锁等待和 Mongo trace 后端真实写入行为。
- RAG fake client 覆盖的是本地 provider/client 协议和安全摘要，不验证外部 RAG 服务召回质量。
- Trace payload 允许短 preview 用于调试，本验收只禁止完整正文、密钥和原始 chunk 全文泄漏。
