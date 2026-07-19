---
last_updated: 2026-07-19
status: active
---

# 模块边界与依赖规则

## 总体依赖方向

目标后端采用“业务领域 + Agent 平台域 + 平台能力 + 共享基础设施”的结构。依赖方向按入口到能力编排，再到领域能力和基础设施收敛：

```text
bootstrap/routes
  → domains/*/routes、application、platforms/*/routes
  → domains/*/service、agent/runtime、agent/executor、prompt、context、memory、skills
  → platforms/shared、shared、infra
```

`app.api`、`app.models`、`app.schemas`、`app.services`、`app.modules`、`app.simulation`
旧技术层入口已下线；新代码必须进入 `app.domains.*`、`app.platforms.*`、`app.agent.*`
或 `app.shared.*` 真实边界，不得新增兼容 re-export 壳。
`app.core` 基础设施入口也已下线；配置、数据库、日志、时间、LLM 与 JSON 工具统一从
`app.shared.*` 导入。

## 架构变更工作流

- 默认不要直接在 `main` 分支修改架构或代码；开发任务使用 `codex/*` 分支或独立 worktree，提交后通过 GitHub PR 审核合并。
- PR 描述必须列出新增、删除、移动的目录或模块，说明调用方、边界、验证命令和剩余风险。
- 目录级变更必须同步更新 `AGENTS.md`、`docs/architecture/overview.md`、本文件和 `docs/architecture/backend-architecture.md`；若依赖方向或文件预算变化，还要同步 `scripts/check-layer-deps.sh` 与 `scripts/check-complexity-budget.sh`。
- 不得为了兼容或临时方便创建 re-export 薄壳、空目录或只有 `__init__.py` 的占位目录；新增目录必须有真实职责、真实调用方和测试落点。
- 生产 Python 文件 1000 行以内可以接受；500-1000 行只进入观察区间，不以行数为唯一理由继续拆碎。

## Agent 平台依赖矩阵

| 边界 | 可依赖 | 禁止依赖 |
|---|---|---|
| Users `domains/users/` | `shared/`，必要时通过 Farm 领域服务创建默认农场 | 直接解析当前农场、直接绕过 Farm 业务规则 |
| Farm `domains/farm/` | `domains/users/dependencies.py`, `shared/` | 把用户认证、token、密码逻辑放入 Farm |
| Domain Routes `domains/*/*routes.py` | Pydantic schema、依赖注入、application use case、同领域 service | 直接承载 Memory、Prompt、Context 选择或存储逻辑 |
| Platforms Routes `platforms/*/*routes.py` | 平台 service、领域依赖、共享基础设施 | 绕过领域服务直接复制业务规则 |
| Application `application/` | Auth/Farm 依赖结果、Context Builder、Prompt Composer、Agent Runtime、Memory Service、Evaluation capture、Observability | HTTP request 细节、数据库表直接操作 |
| Agent Runtime `agent/runtime/` | Runtime state、nodes、graph factory、tool executor 协议、Agent ports | Prompt 版本治理、Context selector 实现、Memory 存储或检索实现 |
| Agent Executor `agent/executor/` | Skill registry、权限策略、参数校验、写操作确认 | API 路由、Prompt 模板、Memory 存储 |
| Prompt `prompt/` | 结构化 PromptInput、ContextBundle 摘要、版本配置、快照 | 在模板渲染阶段直接查询数据库或读取 Memory 存储 |
| Context `context/` | 业务 selector、Memory Service 接口、token budget、cache adapter | Prompt 版本治理、LLM Runtime 节点执行 |
| Memory `memory/` | Memory models、schemas、retrieval、consolidation、infra adapter | API 路由、Agent Runtime 内部状态机细节 |
| Skills `skills/` | Skill schema、权限、执行适配、业务模块端口 | API request 对象、Prompt/Context 存储实现 |
| Platform Shared `platforms/shared/` | `shared/`, `infra/`，以及已迁入 `platforms/data_flywheel` 的 repository 实现 | API 路由、HTTP request 对象、跨平台业务编排 |
| Evaluation `platforms/evaluation/` | replay cases、Prompt 版本、Context 摘要、Skill 调用结果、trace、DataFlywheel discovery 风险信号 | 生产 API 路由编排、业务写入副作用 |
| Observability `observability/` | trace、token、latency、tool call、memory observe、evaluation capture 事件 | 业务决策、Prompt 组合、Context 选择 |

### DataFlywheel Discovery 边界

`app/platforms/evaluation/discovery/` 负责 DataFlywheel 标注候选发现层；Evaluation 代码只通过平台真实路径访问：

- Rule Engine：读取 `rules.yaml`，基于 turn 的白名单上下文计算 `rule_hits`、`rule_score`、`risk_severity`。
- Risk Scorer：融合规则信号和 Judge 信号，写出 `risk_score` 与 `risk_dominant_signal`。
- Judge Worker：批处理未人工标注 turn 的 `judge_*` 风险信号，并受成本阈值保护。

Discovery 只能依赖 `platforms/evaluation` 内模型、`platforms/shared` 中稳定的 judge client 协议和 `shared` LLM manager。不得直接承载 Admin API 路由逻辑，不得写入最终人工标注真值字段，不得把 `judge_*` 输出静默转为训练或回归数据真值。

### Platforms Shared 前置层

`app/platforms/shared/` 是 Evaluation 与 DataFlywheel 平台共享层，当前承载：

- `judge_service.py`：DataFlywheel judge 协议、OpenAI-compatible client、judge 输入构造和输出归一化。
- `repository_selector.py`：DataFlywheel 文档 Repository selector，供 `infra/repository_runtime.py` 创建仓库，避免 infra 直接依赖 `platforms/data_flywheel` 聚合出口。

旧 Evaluation 根包、旧 DataFlywheel 根包，以及 DataFlywheel root 下的 judge service、
repository selector、问题链和 repair pack 兼容薄壳均已下线。真实 DataFlywheel 代码位于
`app.platforms.data_flywheel`，共享 judge 与 repository selector 位于
`app.platforms.shared`。其中问题链与 repair pack 子域真实代码分别位于
`app.platforms.data_flywheel.review_issue_chain` 与
`app.platforms.data_flywheel.repair_pack`；生产代码、测试和 monkeypatch target 必须使用真实路径。

## 禁止规则

- 不得重新创建 `backend/app/api`、`backend/app/models`、`backend/app/schemas`、
  `backend/app/services`、`backend/app/modules`、`backend/app/simulation` 旧技术层入口。
- `domains/*/*routes.py` 不得直接 import `app.memory`、`app.prompt`、`app.context`。
- `domains/*/*routes.py` 不得实现上下文选择、Prompt 组合、记忆检索或记忆沉淀；应调用 application use case。
- `backend/app/agent/runtime/*.py` 不得直接 import `app.memory`。
- `backend/app/agent/runtime/*.py` 不得直接 import `app.context.selectors`、`app.context.retrieval`、`app.context.compressors` 等 Context 平台实现细节。
- `backend/app/agent/runtime/*.py` 不得直接 import `app.prompt.registry`、`app.prompt.versions`、`app.prompt.snippets` 等 Prompt 平台治理细节。
- Agent Runtime 需要上下文时，只接收 `ContextBundle` 或 runtime state 中已经准备好的结构化输入。
- Agent Runtime 需要记忆能力时，只通过 application 层注入的端口或 service 接口访问，不直接访问记忆表、向量索引或 selector。
- Prompt 渲染只接收结构化输入，不在模板渲染阶段直接查询数据库。
- Users/Auth 只负责“谁在请求”和“是否有权限”；当前农场解析属于 Farm 边界。
- 注册后创建默认农场必须通过 Farm 模块接口，Auth 不直接绕过 Farm 业务规则。
- 未迁移的业务模块不创建空壳目录；只有当 `routes.py`、`service.py`、`dependencies.py`、`ports.py` 等真实职责落地时，才新增对应 `domains/*` 或 `platforms/*` 目录。
- Prompt 的版本、片段和快照能力由 `prompt/registry.py`、`prompt/composer.py`、`prompt/replay.py` 以及 `backend/prompts/snippets/` 承载；不保留 `app/prompt/versions`、`app/prompt/snippets`、`app/prompt/snapshots` 空包。

## 已下线旧入口

`app.api`、`app.models`、`app.schemas`、`app.services`、`app.modules`、`app.simulation`
均不再作为活动 import 路径。Alembic 和 metadata 加载统一通过
`app.shared.model_registry` 导入真实模型模块；业务调用方必须使用领域或平台真实路径。

## 违规示例

```python
# 错误：API 直接读取 Memory 平台实现
from app.memory.retrieval import search_memory

# 正确：领域路由调用 Agent application use case
from app.application.chat.use_case import chat
```

```python
# 错误：Runtime 直接选择业务上下文
from app.context.selectors import FarmSelector

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
