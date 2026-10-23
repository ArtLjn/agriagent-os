---
status: implemented-local
last_updated: 2026-10-23
---
# 运行架构与配置补充

主链路与存储布局见 [系统设计](../design.md)。个人记忆由 Agent Worker 在成功普通 Turn 后投递，Mongo 保存权威记录，独立消费者抽取和归并，QuillRAG 索引可重建。学习故障不阻塞正常对话，任务有限重试后清除原文。

本次自动学习默认开启，保留用户显式关闭设置。稳定观察直接生效，移除已无用途的 `MEMORY_MIN_TURNS`、`MEMORY_MIN_CONVERSATIONS`、`MEMORY_CANDIDATE_DAYS`，部署中旧值不再控制晋升或有效期。历史候选已有 expires_at 继续有效，新自动记忆没有候选审批和到期门槛。

沿用 `MEMORY_POLL_SECONDS=5`、`MEMORY_LEASE_SECONDS=120`、`MEMORY_ATTEMPTS=3`，读取预算 `MEMORY_CONTEXT_CHARS=3000`、原文上限 `MEMORY_EXTRACTION_CHARS=12000`。显式记忆审查预算由 `MEMORY_ASSESSMENT_TIMEOUT=15` 控制。无需新增服务或数据库迁移，需要发布并重启 Agent 消费者。

数据兼容与边界见 [自动学习与归并](../design/self-learning-memory.md)，完整既有配置见 [长期记忆实施记录](../spec/2026-10-20-agent-personalization-long-term-memory-plan.md)。
