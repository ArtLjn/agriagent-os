---
last_updated: 2026-07-17
status: active
---

# 模块边界与依赖规则

## 总体依赖方向

目标后端采用“业务模块 + Agent 平台域 + 共享基础设施”的结构。依赖方向按入口到能力编排，再到领域能力和基础设施收敛：

```text
api/
  → modules/*/router 或 application
  → modules/*/service、agent/runtime、agent/executor、prompt、context、memory、skills
  → platforms/shared、shared、core、models、infra
```

允许迁移期保留旧 `api/`、`services/`、`agent/` 兼容入口，但新增代码必须优先进入目标边界。

## Agent 平台依赖矩阵

| 边界 | 可依赖 | 禁止依赖 |
|---|---|---|
| Auth `modules/auth/` | `shared/`, `core/`, `models/user.py`，必要时通过 Farm 模块端口创建默认农场 | 直接解析当前农场、直接绕过 Farm 模块操作农场业务规则 |
| Farm `modules/farm/` | `modules/auth/dependencies.py`, `shared/`, `core/`, `models/farm.py` | 把用户认证、token、密码逻辑放入 Farm |
| API `api/` | Pydantic schema、依赖注入、application use case、模块 router/service | 直接承载 Memory、Prompt、Context 选择或存储逻辑 |
| Application `application/` | Auth/Farm 依赖结果、Context Builder、Prompt Composer、Agent Runtime、Memory Service、Evaluation capture、Observability | HTTP request 细节、数据库表直接操作 |
| Agent Runtime `agent/runtime/` | Runtime state、nodes、graph factory、tool executor 协议、Agent ports | Prompt 版本治理、Context selector 实现、Memory 存储或检索实现 |
| Agent Executor `agent/executor/` | Skill registry、权限策略、参数校验、写操作确认 | API 路由、Prompt 模板、Memory 存储 |
| Prompt `prompt/` | 结构化 PromptInput、ContextBundle 摘要、版本配置、快照 | 在模板渲染阶段直接查询数据库或读取 Memory 存储 |
| Context `context/` | 业务 selector、Memory Service 接口、token budget、cache adapter | Prompt 版本治理、LLM Runtime 节点执行 |
| Memory `memory/` | Memory models、schemas、retrieval、consolidation、infra adapter | API 路由、Agent Runtime 内部状态机细节 |
| Skills `skills/` | Skill schema、权限、执行适配、业务模块端口 | API request 对象、Prompt/Context 存储实现 |
| Platform Shared `platforms/shared/` | `core/`, `models/`, `infra/`，以及已迁入 `platforms/data_flywheel` 的 repository 实现 | API 路由、HTTP request 对象、跨平台业务编排 |
| Evaluation `platforms/evaluation/` | replay cases、Prompt 版本、Context 摘要、Skill 调用结果、trace、DataFlywheel discovery 风险信号 | 生产 API 路由编排、业务写入副作用 |
| Observability `observability/` | trace、token、latency、tool call、memory observe、evaluation capture 事件 | 业务决策、Prompt 组合、Context 选择 |

### DataFlywheel Discovery 边界

`app/platforms/evaluation/discovery/` 负责 DataFlywheel 标注候选发现层；`app.evaluation` 仅作为旧 import 兼容入口保留：

- Rule Engine：读取 `rules.yaml`，基于 turn 的白名单上下文计算 `rule_hits`、`rule_score`、`risk_severity`。
- Risk Scorer：融合规则信号和 Judge 信号，写出 `risk_score` 与 `risk_dominant_signal`。
- Judge Worker：批处理未人工标注 turn 的 `judge_*` 风险信号，并受成本阈值保护。

Discovery 只能依赖 `models/`、`platforms/shared` 中稳定的 judge client 协议和 `core` LLM manager。不得直接承载 Admin API 路由逻辑，不得写入最终人工标注真值字段，不得把 `judge_*` 输出静默转为训练或回归数据真值。

### Platforms Shared 前置层

`app/platforms/shared/` 是 Evaluation 与 DataFlywheel 平台共享层，当前承载：

- `judge_service.py`：DataFlywheel judge 协议、OpenAI-compatible client、judge 输入构造和输出归一化。
- `repository_selector.py`：DataFlywheel 文档 Repository selector，供 `infra/repository_runtime.py` 创建仓库，避免 infra 直接依赖 `platforms/data_flywheel` 聚合出口。

迁移期旧入口必须保留 re-export 或 alias，确保 `app.evaluation`、
`app.modules.data_flywheel.judge_service` 和
`app.modules.data_flywheel.document_repository_selector` 的旧 import API 可用。
`app.modules.data_flywheel` 仅作为兼容入口，真实 DataFlywheel 代码位于
`app.platforms.data_flywheel`。其中问题链与 repair pack 子域真实代码分别位于
`app.platforms.data_flywheel.review_issue_chain` 与
`app.platforms.data_flywheel.repair_pack`；data_flywheel root 下同名旧文件仅做
`sys.modules` alias，供旧动态 import 与 monkeypatch target 过渡使用。

## 禁止规则

- `backend/app/api/*.py` 不得直接 import `app.memory`、`app.prompt`、`app.context`。
- `backend/app/api/*.py` 不得实现上下文选择、Prompt 组合、记忆检索或记忆沉淀；应调用 application use case。
- `backend/app/agent/runtime/*.py` 不得直接 import `app.memory`。
- `backend/app/agent/runtime/*.py` 不得直接 import `app.context.selectors`、`app.context.retrieval`、`app.context.compressors` 等 Context 平台实现细节。
- `backend/app/agent/runtime/*.py` 不得直接 import `app.prompt.registry`、`app.prompt.versions`、`app.prompt.snippets` 等 Prompt 平台治理细节。
- Agent Runtime 需要上下文时，只接收 `ContextBundle` 或 runtime state 中已经准备好的结构化输入。
- Agent Runtime 需要记忆能力时，只通过 application 层注入的端口或 service 接口访问，不直接访问记忆表、向量索引或 selector。
- Prompt 渲染只接收结构化输入，不在模板渲染阶段直接查询数据库。
- Auth 只负责“谁在请求”和“是否有权限”；当前农场解析属于 Farm 边界。
- 注册后创建默认农场必须通过 Farm 模块接口，Auth 不直接绕过 Farm 业务规则。
- 未迁移的业务模块不创建空壳目录；只有当 `router.py`、`service.py`、`dependencies.py`、`ports.py` 等真实职责落地时，才新增对应 `modules/*` 目录。
- Prompt 的版本、片段和快照能力由 `prompt/registry.py`、`prompt/composer.py`、`prompt/replay.py` 以及 `backend/prompts/snippets/` 承载；不保留 `app/prompt/versions`、`app/prompt/snippets`、`app/prompt/snapshots` 空包。

## 后端兼容分层

迁移期仍保留旧技术层约束，用于检查已有目录的反向依赖：

| 层 | 可依赖 | 不可依赖 |
|---|--------|---------|
| `schemas/` | 无 | `agent/`, `agents/`, `api/`, `core/`, `models/`, `services/` |
| `agent/` | `core/`, `models/`, `services/`, `infra/` | `api/` |
| `api/` | `core/`, `models/`, `schemas/`, `services/`, application use case | 平台实现细节、Agent Runtime 内部细节 |
| `core/` | `models/` | `agent/`, `agents/`, `api/`, `schemas/`, `services/` |
| `models/` | `core/` | `agent/`, `agents/`, `api/`, `schemas/`, `services/` |
| `services/` | `agent/`, `core/`, `infra/`, `models/`, `schemas/`, `services/` | `api/` |

## 违规示例

```python
# 错误：API 直接读取 Memory 平台实现
from app.memory.retrieval import search_memory

# 正确：API 调用 Agent application use case
from app.application.chat.use_case import chat
```

```python
# 错误：Runtime 直接选择业务上下文
from app.context.selectors.farm import select_farm_context

# 正确：Runtime 接收 application 已准备好的 ContextBundle
state.context_bundle = context_bundle
```

```python
# 错误：Runtime 直接读取 Prompt 版本注册表
from app.prompt.registry import get_registry

# 正确：Prompt Composer 在 runtime 前完成渲染
state.system_prompt = rendered_prompt
```

## 前端依赖矩阵

| 层 | 可依赖 | 不可依赖 |
|---|--------|---------|
| `api/` | 无 | `components/`, `layouts/`, `pages/` |
| `components/` | `api/` | `layouts/`, `pages/` |
| `layouts/` | 无 | `api/`, `components/`, `pages/` |
| `pages/` | `api/`, `components/` | `layouts/` |

## 豁免机制

特殊情况下需绕过约束时，必须添加注释说明原因：

```python
# harness-exempt: 此处需要直接访问低层，原因见 #PR-XXX
from app.xxx import XxxClass
```
