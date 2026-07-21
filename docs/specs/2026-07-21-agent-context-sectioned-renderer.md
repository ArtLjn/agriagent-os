# Agent Context 分区渲染 Phase 1

## 背景

当前 `ContextBundle` 已能承载 runtime 所需的多个 `ContextBlock`，但 prompt 和 trace 中主要按正文拼接展示，不便区分角色策略、任务状态、证据、背景上下文和输出约束。

Phase 1 的目标是增加稳定、可读的 Sectioned Context 渲染基础，让 prompt 与 debug/log 视图都能看到上下文分区，而不改变现有 ContextBuilder 的选择、预算和压缩策略。

## Phase 1 决策

- 新增 `ContextDocument` / `ContextSection` 作为轻量文档结构，只表达渲染结果，不负责选择、压缩、检索或持久化。
- 新增 `ContextRenderer` 负责将 `ContextBundle` 映射到固定分区顺序：`Role & Policies`、`Task`、`Evidence`、`Context`、`Output`。
- 常见 key 映射保持显式表驱动；未知 key 统一 fallback 到 `Context`，避免丢失内容。
- prompt 文本以 Markdown section heading 渲染，便于人工读日志和模型识别上下文边界。
- debug summary 只输出 section、block key、source、token_estimate、required、is_compressed 等元数据，不记录完整正文。
- runtime 的 `_append_runtime_context` 使用 `ContextRenderer` 输出分区化 prompt 文本。

## Phase 1 不做

- 不接外部 RAG 服务。
- 不新增数据库表。
- 不做长期记忆入库。
- 不改变现有 ContextBuilder selector、budget、allowlist 策略。
- 不在文档、代码、测试、commit 或 PR 描述中记录任何真实密钥；敏感配置只使用环境变量名或占位符。

## 后续边界

- Phase 2 可在外部 RAG 接入稳定后，把检索结果以 `retrieval` 或 `rag_knowledge` block 注入 `Evidence` 分区。
- Phase 3 可评估长期记忆与上下文存储表设计，但需单独完成数据生命周期、权限、脱敏和迁移方案。
- 后续如需更细粒度 section，应优先从真实 trace 样本和提示词评测结果出发，避免为尚未出现的上下文类型提前扩展。
