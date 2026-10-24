---
status: implemented-local
last_updated: 2026-10-24
---
# 运行架构与配置补充

主链路与存储布局见 [系统设计](../design.md)。普通用户消息与学习事件在同一 Mongo 文档原子写入，后台消费者恢复投递并抽取归并，不依赖主对话成败。Mongo 保存权威原子事实，QuillRAG 索引可重建。学习故障不阻塞正常对话，任务有限重试后清除原文。

本次自动学习默认开启，保留用户显式关闭设置。稳定观察直接生效，移除已无用途的 `MEMORY_MIN_TURNS`、`MEMORY_MIN_CONVERSATIONS`、`MEMORY_CANDIDATE_DAYS`，部署中旧值不再控制晋升或有效期。历史候选已有 expires_at 继续有效，新自动记忆没有候选审批和到期门槛。

沿用 `MEMORY_POLL_SECONDS=5`、`MEMORY_LEASE_SECONDS=120`、`MEMORY_ATTEMPTS=3`，读取预算 `MEMORY_CONTEXT_CHARS=3000`、原文上限 `MEMORY_EXTRACTION_CHARS=12000`。显式记忆审查预算由 `MEMORY_ASSESSMENT_TIMEOUT=15` 控制。无需新增服务，超过 200 张卡片的账号下次写入自动迁移独立正文存储；需要同步发布并重启 Agent 入口与消费者。

数据兼容与边界见 [自动学习与归并](../design/self-learning-memory.md)，完整既有配置见 [长期记忆实施记录](../spec/2026-10-20-agent-personalization-long-term-memory-plan.md)。

记忆抽取、归并、完整性复核和工具审核共用 `agent/platforms/llm/structured.py`：由 Pydantic 生成强制工具输出协议，再按同一模型严格解析。当前 Qwen 网关实测忽略 `json_schema`，所以不能仅依赖该参数；结果工具只承载结构化数据，不进入业务执行器。完整内容通道 JSON 和旧抽取数组仍可兼容，截断、拒绝、多结果、重复键或字段类型错误统一失败，不自动修补事实。后台仍沿用既有有限重试，授权审核失败则拒绝写入。

语义提示词位于 `agent/prompts/memory_*.md`，使用现有 `render_prompt` 加载；Python 中不保存提示词正文。输出字段、类型、枚举和长度来自模型定义，Markdown 只描述来源、时间、条件与授权等语义规则。

QuillRAG 使用 Cloudflare BGE-M3 时，配置 `EMBEDDING_PROVIDER=openai`、`EMBEDDING_MODEL=@cf/baai/bge-m3`、`EMBEDDING_DIM=1024`、`EMBEDDING_BATCH_SIZE=64`。其客户端自行追加 `/v1/embeddings`，因此 `EMBEDDING_BASE_URL` 应为 `https://api.cloudflare.com/client/v4/accounts/<account_id>/ai`。Token 仅放部署环境的 `EMBEDDING_API_KEY`。模型切换必须重新嵌入已有正文，旧模型同维度也不能混用；先备份配置、元数据和原始向量，切换后检查真实 `actual_mode`，不能只看 HTTP 200。

本次抽样验证集合为 `agent_user_memory_bge_m3_sample_1000`，包含 1000 条已有记忆，保留账号、农场和版本过滤。它用于受控验证，不修改 Mongo 原始记忆；测试进程显式指定 `MEMORY_RAG_COLLECTION`。不要对这个固定样本集合启动全量索引 Worker，否则会继续补齐原库全部记忆。正式运行仍按部署的 `MEMORY_RAG_COLLECTION` 选择集合。

`MONGODB__DATABASE` 可覆盖 Agent 数据库名称，与已有 `REDIS__KEY_PREFIX` 配合隔离集成测试；常规部署不设置则继续使用 config.yaml。真实回归使用随机专属库并精确销毁，不指向用户库。

本地与线上共享 Redis 时必须配置不同的 `REDIS__KEY_PREFIX`，否则旧执行 Worker 可以消费本地请求。新版记忆消息使用 `memoryLearningV3` 字段和 `agentMemoryLearningTasksV3` 租约集合；旧消费者仍只扫描旧字段/集合，不能抢走新版事件。旧队列由旧版本完成或在停旧进程后显式迁移，不自动重学旧消息。发布时同时升级入口与消费者，环境隔离不能只靠入口健康检查的源码指纹。

发布后核对 `/api/v2/health.runtime.started_at` 与 `memory_build`（启动时计算的记忆模块源码指纹）；入口没有热重载，修改代码后必须重启。旧消息缺少学习事件时不自动补学，旧复合记忆仅在涉及更新时无损拆分，不需要全库迁移。

规模配置新增 `MEMORY_CONTEXT_TOKENS=3000`（保守字节计量）和 `MEMORY_REVIEW_BYTES=12000`；完整请求工作预算由 `CONTEXT__MODEL_CONTEXT_TOKENS` 覆盖。用户根文档发布 V3 正文引用，正文集合 `agentMemoryRecordsV3`，最多 10000 张有效卡片。升级及回滚约束见自动学习设计文档。

回答前固定运行主动记忆检索，默认 `MEMORY_CONTEXT_MODE=retrieve`：Mongo 词项召回与 QuillRAG 语义召回并行，经 RRF、多样性排序及权威版本回查，将原子事实放在当前问题之前，由主模型判断条件、否定与用途。此路径没有额外的记忆阅读模型调用；需要对照旧阅读器时可设置 `MEMORY_CONTEXT_MODE=read`，总时限仍由 `MEMORY_CONTEXT_COMPILE_TIMEOUT=12` 控制。

`MEMORY_CONTEXT_TIMEOUT=3` 控制单次存储准备边界，`MEMORY_RETRIEVE_TIMEOUT=2` 控制语义请求（包括两种权限范围）；语义故障降级词项召回，Trace 明确记录 timeout/unavailable/lexical_fallback。每路最多 24 个语义候选、融合最多 12 张卡片；仍限制 60 条原子事实、12KB 阅读材料和最终 3000 字符/保守 token 双预算。整张卡片必须同时满足预算，避免只留下喜欢而截掉禁忌。

配置样例默认 `context.skill_router_mode=llm_router`、`tool_schema_mode=candidate`、路由超时 5 秒。旧部署的显式配置不会自动覆盖，升级时同步修改配置并重启。路由与记忆检索并行，普通闲聊允许空业务工具集；路由故障仍回全目录。`context.estimate_steps=false`（或 `CONTEXT__ESTIMATE_STEPS=false`）跳过额外步数预估调用，运行时硬步数与工具结果预算继续生效。

语义服务通过 `MEMORY_RAG_URL`、`MEMORY_RAG_API_KEY`、`MEMORY_RAG_COLLECTION` 注入，不把服务凭证提交到仓库。Ollama 可由 QuillRAG 的 OpenAI embedding 适配接入：provider=openai，base URL 为可达的 Ollama 根地址，model 与 dim 必须匹配实测结果。模型只负责向量化，主模型负责回答。索引与查询必须使用同一模型及维度；切模型必须启用新集合并重新标记账号 `index_pending=true,index_available_at=0`，待清单确认全量完成后切查询。生产建议蓝绿服务切换，不能在旧集合内混写不同维度。

索引清单以 `collection:doc_id` 唯一标识，保存 collection/doc_id/owner/version；每批最多 48 条、4 个并发上传。旧无 collection 清单不视为新集合已就绪；默认集合仍兼容清理旧清单，更换服务或集合时须在旧端单独清理。清理每批 100 条但同用户只回查一次主数据，已删除/旧版本永远不能凭向量结果复活。根文档版本条件更新避免索引任务把新变更误标完成。若索引失败，只完成成功条目，剩余条目有限并发重试。

`health.runtime.memory_semantic_configured` 仅表示已配置，不代表向量服务可用；以真实 `/retrieve` 返回的 actual_mode 和 Trace retrieval.status 验证。`answer_memory_context` 记录模式、候选、实际注入与检索耗时；`final_llm_context.memory_context_included` 检查最终请求是否仍含记忆。注入命中和回答是否遵守偏好须分别验收。
