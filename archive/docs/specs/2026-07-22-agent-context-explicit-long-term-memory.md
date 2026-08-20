# Agent Context 显式长期记忆最小版

## 背景

Sectioned Context、外部 RAG 只读接入、Task Context 持久化和 TaskState 写入闭环已落地。本轮补齐显式长期记忆最小闭环：用户明确说“记住 / 以后都这样 / 帮我记一下”时，将偏好、别名、稳定事实写入长期记忆，并在下一轮 Context 构建时注入。

## 范围

- 新增 `memory_records` MySQL 表，按 `farm_id` / `user_id` 隔离长期记忆。
- 新增 `MemoryRecordStore`，支持创建 confirmed 记忆、读取同 farm/user 的 confirmed 记忆、归档记忆。
- `MemoryService` 默认长期记忆 store 使用只读 SQL session 构建 `LongTermMemoryContext`；直接 new 的 `InMemoryMemoryService()` 仍保持空长期记忆，维持测试和降级契约。
- 非流式 chat 和流式后台收尾在回复生成后调用 `record_explicit_memory_after_turn()`。
- `MemorySelector` 将 confirmed 长期记忆注入 `long_term_memory` block，并由 Sectioned Context 渲染到 Context 分区。

## 写入规则

第一版只识别明确用户指令：

- “记住我以后用亩”
- “以后默认按一号棚算”
- “帮我记一下老王就是农资店老板”
- “以后都这样”

跳过以下场景：

- 问候、普通问答、普通查询。
- 记账确认、pending action、pending plan。
- 本轮刚处理 pending 确认或取消。
- “不要记这个 / 别记 / 不用记 / 取消刚才记忆”等取消类表达。

写入失败不打断聊天回复，只记录结构化日志 `EXPLICIT_MEMORY_RECORD_FAILED` 并回滚当前写入。

## 表结构

核心字段：

- `memory_id`：业务 ID，唯一。
- `farm_id` / `user_id`：多租户隔离边界。
- `type`：`preference`、`alias`、`fact`、`farm_profile`、`ledger_summary`。
- `content`：用户明确要求保存的自然语言内容。
- `status`：`confirmed`、`candidate`、`superseded`、`archived`；本轮只写 `confirmed`，归档使用 `archived`。
- `source`：本轮只写 `user_explicit`。
- `importance` / `confidence`：默认 `0.8` / `1.0`。
- `superseded_by_id`、`created_at`、`updated_at`、`archived_at`：生命周期字段。

## Context 注入

运行时通过 `MemoryService.build_context()` 读取同 `farm_id` / `user_id` 的 confirmed 记忆，填充 `LongTermMemoryContext`。`MemorySelector` 输出 `long_term_memory` block：

- `source=memory.long_term`
- `priority=55`
- `metadata.layer=working`
- `metadata.cache_scope=farm_user`

该 block 进入 Context Renderer 的 Context 分区，不进入 Evidence，不触发 RAG。

## 明确不做

- 不做 LLM 隐式抽取。
- 不做 candidate 升级规则。
- 不做 RAG ingest、embedding、向量库同步。
- 不做 Mongo 同步或三库一致性。
- 不做跨 farm/user 检索。
- 不把 pending action / pending plan 确认流程升级为长期记忆。
