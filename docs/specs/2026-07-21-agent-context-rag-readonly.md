# Agent Context 外部 RAG 只读接入 Round 1

## 背景

上一轮已完成 `ContextBundle` 的分区化渲染骨架，`rag_knowledge` 会进入 Evidence 分区。本轮只接入外部 QuillRAG 的只读检索链路，让知识、诊断、方案和种植建议类问题可以获得外部农技知识摘要，同时保持主问答链路可降级。

## 落地范围

- 新增 QuillRAG HTTP client，只调用 `GET /health` 和 `POST /retrieve`。
- 新增 `KnowledgeSelector` 和 `RAGKnowledgeProvider`，把检索结果转为 `ContextBlock(key="rag_knowledge", source="external_rag")`。
- prompt 只注入来源、分数和片段摘要，不注入原始大 JSON。
- `ContextBundle.summary()` 通过 `selector_metadata.knowledge` 暴露 `rag_called`、`actual_mode`、`warning`、失败摘要等 trace 友好字段。
- `ContextPolicy` 仅对知识、诊断、方案、种植建议等问题触发 RAG；记账、查账、pending 确认和写操作确认不触发。

## 配置项

配置入口为 `rag_service`，可通过 `config.yaml` 或环境变量覆盖。环境变量使用 Pydantic 嵌套格式，例如 `RAG_SERVICE__API_KEY`。

| 字段 | 说明 |
| --- | --- |
| `enabled` | 是否启用外部 RAG 只读检索。 |
| `url` | QuillRAG 服务地址，例如 `http://127.0.0.1:8001`。 |
| `timeout_seconds` | 单次 HTTP 请求超时。 |
| `retry` | 网络错误或超时后的额外重试次数；HTTP 5xx 不重试。 |
| `fallback_enabled` | 检索失败时是否降级为空知识块并继续主问答。 |
| `api_key` | QuillRAG API key，只能放环境变量或私密配置；示例文件保持空字符串。 |
| `default_collection` | 默认检索 collection。 |
| `default_mode` | 默认检索模式：`vector`、`bm25` 或 `hybrid`。 |
| `top_k` | 请求 QuillRAG 返回的结果数。 |
| `use_hyde` | 是否请求 QuillRAG 执行 HyDE 查询改写。 |

Farm Manager 不配置、不调用、不保存 embedding provider 或 embedding key。

## 降级策略

- 未启用、未配置 `url` 或问题为空：不调用 RAG。
- 网络错误和超时：按 `retry` 重试，仍失败则标准化为 `rag_unavailable` 元数据。
- HTTP 4xx/5xx：不重试，标准化为 `http_<status>` 错误码。
- `fallback_enabled=true` 时，失败不会抛出到主问答，只在 bundle metadata 中留下失败摘要。
- 空检索结果返回空 block，并记录 `rag_empty=true`。

## 明确不做

- 不调用 `/ingest`。
- 不做文档 ingest UI 或任务。
- 不做 memory 同步。
- 不新增 memory/task 表。
- 不接 Mongo trace 写入；本轮只保留可被下一轮 trace 使用的 metadata。
- 不把任何真实服务密钥写入代码、测试、文档、commit 或 PR 描述。
