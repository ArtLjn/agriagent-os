## Why

当前后端已经具备农事 Agent、Skill 调用、Prompt 模板、Trace、用户鉴权和业务 API，但这些能力主要按技术层分散在 `api/`、`services/`、`agent/`、`infra/`、`core/` 中。随着后续要建设成熟 Agent 系统、Prompt 工程、Context 工程、短时/长时记忆和评测回归，现有边界会让功能继续堆进 `agent/graph.py`、`api/agent.py` 和通用 service，增加改动风险。

本变更建立 Agent Platform 架构地基，把 Auth、Agent Runtime、Prompt、Context、Memory、Skill、Evaluation、Observability 明确为可演进边界，为后续短时记忆、长时记忆、RAG、工具权限、Prompt 版本治理和 Agent 评测留出空间。

## What Changes

- 建立后端目标架构：业务模块 `modules/`、Agent 平台 `agent/`、Prompt 工程 `prompt/`、Context 工程 `context/`、Memory `memory/`、Evaluation `evaluation/`、Observability `observability/`、外部适配 `infra/`、基础内核 `core/`。
- 将 Auth 作为独立安全边界设计，后续迁移 `api/auth.py`、`services/auth_service.py`、`api/deps.py` 中的认证职责到 `modules/auth/`。
- 将 Agent 从单个大图和服务函数拆为 runtime、planner、executor、response、guardrails、sessions、application 等子域。
- 将 Prompt 从模板文件管理升级为版本化、片段化、可测试、可回放验证的工程能力。
- 新增 Context 工程边界，统一管理上下文选择、token 预算、压缩、缓存、并行预热和注入顺序。
- 新增 Memory 模块边界，先预留短时记忆、长时记忆、语义检索、异步沉淀接口，不在本变更中实现完整向量数据库。
- 新增 Evaluation 边界，支持后续对话回放、Prompt A/B、Skill 调用准确率、上下文命中率、延迟和 token 成本评测。
- 明确拆发顺序，降低与当前 MySQL 迁移、用户额度、每日建议等进行中 change 的冲突。
- 不改变现有外部 API 行为，不在本变更中删除业务能力。

## Capabilities

### New Capabilities

- `agent-platform-architecture`: 定义成熟 Agent 系统的模块边界、依赖方向、运行时分层和拆发约束。
- `context-engineering`: 定义上下文构建、选择、预算、压缩、缓存和注入顺序能力。
- `agent-memory-foundation`: 定义短时记忆、长时记忆、检索和沉淀的边界与最小接口。
- `agent-evaluation-foundation`: 定义 Agent 回放评测、Prompt 回归、Skill 调用质量和上下文质量指标。
- `auth-module-boundary`: 定义认证鉴权独立模块边界、token、权限依赖和 Farm 上下文关系。

### Modified Capabilities

- `user-auth`: 用户认证要求补充 token payload、统一错误码、管理员权限、依赖注入和模块边界。
- `prompt-management`: Prompt 管理要求补充版本化、片段化、渲染快照测试和回放验证。
- `llm-tool-calling`: 工具调用要求补充 executor 边界、工具权限分级、写操作确认和 trace 标准化。
- `agent-trace`: Trace 要求补充 Agent Runtime、Prompt、Context、Memory、Skill 和评测可观测事件。
- `conversation-management`: 对话管理要求补充短时记忆输入、会话摘要和异步记忆观察事件。

## Impact

- 影响后端架构文档、OpenSpec 规划、后续模块迁移任务。
- 后续会逐步调整 `backend/app/main.py`、`backend/app/api/agent.py`、`backend/app/agent/graph.py`、`backend/app/services/agent_service.py`、`backend/app/api/auth.py`、`backend/app/api/deps.py`、`backend/app/core/security.py`。
- 后续新增目录包括 `backend/app/modules/`、`backend/app/prompt/`、`backend/app/context/`、`backend/app/memory/`、`backend/app/evaluation/`、`backend/app/observability/`。
- 本变更本身以架构与任务规划为主，不要求立即改变数据库结构或外部 API。
