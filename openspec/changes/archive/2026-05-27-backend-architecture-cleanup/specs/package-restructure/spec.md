## ADDED Requirements

### Requirement: core/ 仅保留基础设施模块
`app/core/` 包 SHALL 只包含被多个领域共用的基础设施模块：config、database、security、logger、date_context、json_repair、seed。Agent 专属模块和可观测性模块 MUST 移至对应包。

#### Scenario: core/ 目录内容
- **WHEN** 列出 `app/core/` 目录文件
- **THEN** 仅包含：`__init__.py`、`config.py`、`database.py`、`security.py`、`logger.py`、`date_context.py`、`json_repair.py`、`seed.py`

### Requirement: Agent 专属模块归属 agent/ 包
Agent 领域相关模块 SHALL 统一放在 `app/agent/` 包中，包括：graph、advisor、report、state、llm、guardrails、prompt_registry、prompt_renderer、skills。

#### Scenario: agent/ 目录结构
- **WHEN** 列出 `app/agent/` 目录
- **THEN** 包含：`graph.py`、`advisor.py`、`report.py`、`state.py`、`llm.py`、`guardrails.py`、`prompt_registry.py`、`prompt_renderer.py`、`skills/`

### Requirement: 可观测性模块归属 infra/ 包
可观测性和运维模块 SHALL 统一放在 `app/infra/` 包中，包括：trace_collector、trace_dao、trace_context、trace_cleaner、circuit_breaker、limiter、pending_actions、skill_cache。

#### Scenario: infra/ 目录结构
- **WHEN** 列出 `app/infra/` 目录
- **THEN** 包含：`trace_collector.py`、`trace_dao.py`、`trace_context.py`、`trace_cleaner.py`、`circuit_breaker.py`、`limiter.py`、`pending_actions.py`、`skill_cache.py`

### Requirement: 所有 import 路径更新
移动模块后，所有引用这些模块的 import 语句 SHALL 更新为新路径。MUST 无 ImportError。

#### Scenario: 全量测试通过
- **WHEN** 运行 `python -m pytest` 全量测试
- **THEN** 所有测试通过，无 ImportError 或 ModuleNotFoundError

#### Scenario: 无外部 API 变化
- **WHEN** 对比重构前后的 API 端点行为
- **THEN** 所有端点的请求/响应格式完全一致
