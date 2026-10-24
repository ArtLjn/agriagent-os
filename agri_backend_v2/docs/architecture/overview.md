---
status: implemented-local
last_updated: 2026-10-24
---
# 运行架构与配置补充

主链路与存储布局见 [系统设计](../design.md)。普通用户消息与学习事件在同一 Mongo 文档原子写入，后台消费者恢复投递并抽取归并，不依赖主对话成败。Mongo 保存权威原子事实，QuillRAG 索引可重建。学习故障不阻塞正常对话，任务有限重试后清除原文。

本次自动学习默认开启，保留用户显式关闭设置。稳定观察直接生效，移除已无用途的 `MEMORY_MIN_TURNS`、`MEMORY_MIN_CONVERSATIONS`、`MEMORY_CANDIDATE_DAYS`，部署中旧值不再控制晋升或有效期。历史候选已有 expires_at 继续有效，新自动记忆没有候选审批和到期门槛。

沿用 `MEMORY_POLL_SECONDS=5`、`MEMORY_LEASE_SECONDS=120`、`MEMORY_ATTEMPTS=3`，读取预算 `MEMORY_CONTEXT_CHARS=3000`、原文上限 `MEMORY_EXTRACTION_CHARS=12000`。显式记忆审查预算由 `MEMORY_ASSESSMENT_TIMEOUT=15` 控制。无需新增服务，超过 200 张卡片的账号下次写入自动迁移独立正文存储；需要同步发布并重启 Agent 入口与消费者。

数据兼容与边界见 [自动学习与归并](../design/self-learning-memory.md)，完整既有配置见 [长期记忆实施记录](../spec/2026-10-20-agent-personalization-long-term-memory-plan.md)。

`MONGODB__DATABASE` 可覆盖 Agent 数据库名称，与已有 `REDIS__KEY_PREFIX` 配合隔离集成测试；常规部署不设置则继续使用 config.yaml。真实回归使用随机专属库并精确销毁，不指向用户库。

本地与线上共享 Redis 时必须配置不同的 `REDIS__KEY_PREFIX`，否则旧执行 Worker 可以消费本地请求。新版记忆消息使用 `memoryLearningV3` 字段和 `agentMemoryLearningTasksV3` 租约集合；旧消费者仍只扫描旧字段/集合，不能抢走新版事件。旧队列由旧版本完成或在停旧进程后显式迁移，不自动重学旧消息。发布时同时升级入口与消费者，环境隔离不能只靠入口健康检查的源码指纹。

发布后核对 `/api/v2/health.runtime.started_at` 与 `memory_build`（启动时计算的记忆模块源码指纹）；入口没有热重载，修改代码后必须重启。旧消息缺少学习事件时不自动补学，旧复合记忆仅在涉及更新时无损拆分，不需要全库迁移。

规模配置新增 `MEMORY_CONTEXT_TOKENS=3000`（保守字节计量）和 `MEMORY_REVIEW_BYTES=12000`；完整请求工作预算由 `CONTEXT__MODEL_CONTEXT_TOKENS` 覆盖。用户根文档发布 V3 正文引用，正文集合 `agentMemoryRecordsV3`，最多 10000 张有效卡片。升级及回滚约束见自动学习设计文档。
