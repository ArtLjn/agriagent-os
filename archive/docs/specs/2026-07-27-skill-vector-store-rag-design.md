# Skill 向量库存储设计

## 背景

Skill Router 的线上日志曾暴露出错误路径：

```text
candidate_count=34
doc_embedding_calls=34
cache_hits=0
duration_ms=96553
```

这说明旧实现把每个 Skill 文档都在请求时在线 embedding，导致一次短查询触发几十次外部 embedding 调用。新的方向是复用独立部署的 QuillRAG 服务：Farm Manager 只生成 Skill route 文档并调用 RAG 入库与检索接口，embedding、dense/sparse 检索、Qdrant 写入和 rerank 都由 `rag.lllcnm.cn` 内部完成。

已确认 `https://rag.lllcnm.cn/health` 可用，组件状态包含 Qdrant、embedder、reranker。本文按本地项目 `/Users/ljn/Documents/demo/finished/rag-service` 的实际 API 契约设计。

## 目标

- Skill 文档只在注册、更新、删除、重建索引时写入 RAG 服务。
- Router 在线查询路径不在 Farm Manager 内调用 embedding。
- Router 不再在线遍历 Skill 并生成 Skill embedding。
- Skill 向量召回结果可解释、可回退、可评测。
- 写入流程支持稳定 `doc_id`、幂等覆盖和删除旧文档。

## 非目标

- 不把业务知识 RAG 与 Skill Router 向量库混在同一个 collection。
- 不在 Farm Manager 后端保存 embedding provider 密钥。
- 不在 Farm Manager 中配置或调用 `qwen3-embedding:0.6b`。
- 不要求第一阶段启用 rerank；先保证稳定 TopK 召回。

## Collection

collection 名称：

```text
farm_manager_skill_routes_v1
```

命名规则：

- `farm_manager`：项目命名空间。
- `skill_routes`：用途是工具/操作路由，不是业务知识问答。
- `v1`：文档结构或 RAG 服务 embedding 模型变更时升级版本，避免污染旧索引。

向量维度、距离函数、dense/sparse 配置以 QuillRAG 服务的 collection 创建配置为准，Farm Manager 不感知具体 embedding 模型和维度。

## 文档粒度

每个可路由 operation 一条 RAG 文档，而不是每个 Skill 一条。

稳定 `doc_id`：

```text
skill:{capability}.{operation}
```

示例：

```text
skill:manage_cost.query_summary
skill:manage_crop_cycle.query_cycles
skill:manage_labor_payment.query_payables
```

原因：

- Router 最终需要选择 operation，不只是 Skill。
- 同一个 Skill 的 create/query/delete 语义差异很大。
- 检索结果可以直接映射为 `ToolCandidate` route key。

## Metadata

通过 QuillRAG `/ingest` 的 `metadata_json` 写入每个 chunk payload：

```json
{
  "project": "farm-manager",
  "route_key": "manage_cost.query_summary",
  "capability": "manage_cost",
  "operation": "query_summary",
  "legacy_alias": "get_cost_summary",
  "skill_name": "manage_cost",
  "domain": "finance",
  "risk": "read",
  "operation_risk": "read",
  "enabled": true,
  "status": "active",
  "tags": ["成本", "费用", "收支", "余额"],
  "intents": ["query_cost_summary"],
  "entities": ["cost", "income", "balance"],
  "trigger_examples": ["我的余额", "这个月花了多少", "最近收支情况"],
  "anti_examples": ["买了化肥200块", "记一笔支出"],
  "doc_hash": "sha256:...",
  "registry_version": "2026-07-27",
  "updated_at": "2026-07-27T15:50:00+08:00"
}
```

约束：

- `route_key` 是 Farm Manager Router 的唯一读取主键。
- `source` 使用 `route_key`，`category` 使用 `skill_route`，便于 QuillRAG 原生过滤。
- 不在 metadata 放 API key、数据库 URL、用户隐私数据或完整工具 schema。
- 不存 Farm Manager 自己的 embedding 模型名，避免与 QuillRAG 内部模型耦合。

## Document Text

入库文本必须稳定、短、面向路由，不直接拼完整 Python/JSON schema。

模板：

```text
Capability: manage_cost
Operation: query_summary
Domain: finance
Risk: read
Intents: query_cost_summary
Entities: cost, income, balance
Examples:
- 我的余额
- 这个月花了多少
- 最近收支情况
Anti examples:
- 买了化肥200块
- 记一笔支出
```

生成规则：

- 字段顺序固定。
- 去掉空字段。
- 每条 operation 只保留最关键 examples。
- `doc_hash = sha256(document_text + route_key + registry_version)`。

## 写入 API

复用 QuillRAG 原生 `/ingest`，由服务内部完成解析、分块、embedding 和 Qdrant upsert。

```http
POST /ingest
Content-Type: multipart/form-data
```

表单字段：

```text
collection=farm_manager_skill_routes_v1
text=<Document Text>
file_type=txt
strategy=fixed
chunk_size=1200
chunk_overlap=0
source=manage_cost.query_summary
category=skill_route
doc_id=skill:manage_cost.query_summary
metadata_json=<Metadata JSON>
```

响应：

```json
{
  "code": "OK",
  "data": {
    "doc_id": "skill:manage_cost.query_summary",
    "chunk_count": 1,
    "collection": "farm_manager_skill_routes_v1",
    "action": "created"
  },
  "warning": null
}
```

同步脚本：

```bash
PYTHONPATH=. python -m app.ops.skill_vector_sync --collection farm_manager_skill_routes_v1
```

脚本流程：

1. 从 Skill Registry 读取所有 active capability operation。
2. 生成 `document_text`、`metadata_json` 和 `doc_hash`。
3. 对新增或变化的 operation 调用 `/ingest`。
4. 对本地已删除或 disabled 的 operation 调用 `/collections/{name}/documents/{doc_id}` 删除。
5. 输出 `created/updated/noop/deleted/failed`。

## 检索 API

复用 QuillRAG 原生 `/retrieve`，Farm Manager 只传 query 文本。

```http
POST /retrieve
Content-Type: application/json
```

请求：

```json
{
  "query": "我的花费多少",
  "collection": "farm_manager_skill_routes_v1",
  "mode": "hybrid",
  "top_k": 8,
  "filters": {
    "project": "farm-manager",
    "category": "skill_route",
    "enabled": true,
    "status": "active"
  },
  "use_hyde": false
}
```

响应中的每条 result 需要包含：

```json
{
  "doc_id": "skill:manage_cost.query_summary",
  "score": 0.82,
  "content": "Capability: manage_cost...",
  "metadata": {
    "source": "manage_cost.query_summary",
    "category": "skill_route",
    "doc_id": "skill:manage_cost.query_summary",
    "route_key": "manage_cost.query_summary",
    "capability": "manage_cost",
    "operation": "query_summary",
    "skill_name": "manage_cost"
  }
}
```

Farm Manager Router 只读取 `metadata.route_key` 和 `score`。如果历史数据缺少 `route_key`，可以临时回退读取 `metadata.source`。

## Router 接入

`HybridOperationRetriever` 不在线生成 candidate document embedding，也不在线生成 query embedding。

正确在线流程：

```text
User Query
  -> Farm Manager QuillRAGSkillVectorStore.search(query_text)
  -> rag.lllcnm.cn /retrieve collection=farm_manager_skill_routes_v1
  -> route_key score map
  -> BM25 + lexical + vector score rerank
  -> TopK ToolCandidate
```

日志指标：

```text
event=skill_router_vector_recall_completed
status=success
candidate_count=34
local_query_embedding_calls=0
local_doc_embedding_calls=0
vector_search_calls=1
scored_count=8
duration_ms=120
```

如果向量库未配置：

```text
status=missing_index
local_query_embedding_calls=0
local_doc_embedding_calls=0
vector_search_calls=0
```

这时回退 BM25 + 强规则，不允许在线 embed Skill 文档。

## 配置建议

Farm Manager 增加 Skill Vector Store 配置：

```yaml
skill_vector_store:
  enabled: true
  provider: "quillrag"
  url: "" # 留空复用 rag_service.url
  collection: "farm_manager_skill_routes_v1"
  mode: "hybrid"
  top_k: 8
  timeout_seconds: 1.5
  sync_timeout_seconds: 30.0
  retry: 0
  api_key: ""
  create_collection_on_startup: true
  sync_on_startup: true
```

该配置与业务知识库 RAG 分开，避免两个场景共享 collection、top_k、mode 和过滤条件。

启动同步必须是非阻塞后台任务：

1. FastAPI lifespan 只创建 `skill-vector-sync` task，不等待 QuillRAG 入库完成。
2. 后台任务先调用 `GET /collections/{collection}/documents` 读取 `skill:__manifest__`。
3. 如果远端 `registry_hash` 与本地 Skill Registry hash 一致，记录 `sync_status=skipped` 并结束。
4. 只有 manifest 缺失或 hash 不一致时，才执行 `POST /collections` 和逐条 `POST /ingest`。
5. 全量同步成功后写入新的 `skill:__manifest__`；同步失败不更新 manifest，下一次启动继续重试。

## 失败回退

向量库失败时：

1. 记录 `status=fallback`、`error_code`、`vector_search_calls=1`。
2. 不阻断主流程。
3. 回退 BM25 + 规则召回。
4. Admin 检索测试显示 `vector_status=fallback`。

QuillRAG 自身降级时会返回 `warning` 和 `actual_mode`，Farm Manager 需要把它们写入 Router evidence。

## 验收标准

- 任意 Router 请求中 `local_doc_embedding_calls` 必须恒为 `0`。
- 任意 Router 请求中 `local_query_embedding_calls` 必须恒为 `0`，因为 embedding 在 QuillRAG 内部完成。
- 向量库启用且可用时，`vector_search_calls=1`。
- `skill_route_cases.json` 的 `recall@5` 和 `operation_hit@5` 保持 100%。
- `我的花费多少` Top1 为 `manage_cost.query_summary`。
- `查一下成本` 总召回耗时目标小于 300ms。
- RAG 服务不可用时 Router 仍可返回 BM25/规则结果。

## 分阶段落地

第一阶段：止血。

- 禁止在线 candidate document embedding。
- Router 不再构建 Farm Manager 本地 embedding client。
- 没有 vector index 时输出 `missing_index` 并回退 BM25。

第二阶段：QuillRAG 入库增强。

- `/ingest` 支持可选 `doc_id`。
- `/ingest` 支持可选 `metadata_json`。
- 检索 result 可返回 `route_key` 等扩展 metadata。

第三阶段：同步脚本。

- 实现 `app.ops.skill_vector_sync`。
- 支持 dry-run、ingest、delete-stale。
- 保存同步结果，供 Admin 展示索引状态。

第四阶段：Router 接入 RAG。

- 新增 `SkillVectorStoreConfig`。
- 新增 `QuillRAGSkillVectorStore.search(query, candidates)`。
- 注入 `HybridOperationRetriever(vector_search=...)`。

第五阶段：Admin 可视化。

- Skill 注册表显示向量索引状态。
- 检索测试显示完整 `skill_router` JSON。
- 检索测试显示 `vector_score`、`bm25`、`lexical`、`operation_prior`、最终分、RAG `actual_mode` 和 `warning`。
