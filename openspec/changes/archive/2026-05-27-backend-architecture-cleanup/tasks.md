## 1. 删除死代码

- [ ] 1.1 删除 `app/core/term_whitelist.py`
- [ ] 1.2 全局搜索确认无残留引用（`term_whitelist`、`is_whitelisted`、`_AGRICULTURAL_TERMS`）
- [ ] 1.3 运行全量测试确认无影响

## 2. 消除 prompt 双数据源

- [ ] 2.1 删除 `app/core/prompt_registry.py` 中的 `_DEFAULT_PROMPTS` 字典
- [ ] 2.2 删除 `PromptRegistry.get_fallback()` 方法
- [ ] 2.3 修改 `app/core/prompt_renderer.py`：模板未注册时直接让 KeyError 冒泡，渲染失败时抛出异常而非调用 get_fallback
- [ ] 2.4 更新 `prompt_renderer.py` 的 docstring，移除"回退到内置默认"的描述
- [ ] 2.5 测试：验证模板正常渲染、未注册模板抛 KeyError、无 `_DEFAULT_PROMPTS` 引用

## 3. 创建 agent/ 包并迁移 Agent 模块

- [ ] 3.1 创建 `app/agent/__init__.py`
- [ ] 3.2 将 `app/agents/graph.py` → `app/agent/graph.py`
- [ ] 3.3 将 `app/agents/advisor.py` → `app/agent/advisor.py`
- [ ] 3.4 将 `app/agents/report.py` → `app/agent/report.py`
- [ ] 3.5 将 `app/agents/state.py` → `app/agent/state.py`
- [ ] 3.6 将 `app/core/llm.py` → `app/agent/llm.py`
- [ ] 3.7 将 `app/core/guardrails.py` → `app/agent/guardrails.py`
- [ ] 3.8 将 `app/core/prompt_registry.py` → `app/agent/prompt_registry.py`
- [ ] 3.9 将 `app/core/prompt_renderer.py` → `app/agent/prompt_renderer.py`
- [ ] 3.10 将 `app/skills/` 目录整体移至 `app/agent/skills/`
- [ ] 3.11 删除旧的 `app/agents/` 目录

## 4. 创建 infra/ 包并迁移可观测性模块

- [ ] 4.1 创建 `app/infra/__init__.py`
- [ ] 4.2 将 `app/core/trace_collector.py` → `app/infra/trace_collector.py`
- [ ] 4.3 将 `app/core/trace_dao.py` → `app/infra/trace_dao.py`
- [ ] 4.4 将 `app/core/trace_context.py` → `app/infra/trace_context.py`
- [ ] 4.5 将 `app/core/trace_cleaner.py` → `app/infra/trace_cleaner.py`
- [ ] 4.6 将 `app/core/circuit_breaker.py` → `app/infra/circuit_breaker.py`
- [ ] 4.7 将 `app/core/limiter.py` → `app/infra/limiter.py`
- [ ] 4.8 将 `app/core/pending_actions.py` → `app/infra/pending_actions.py`
- [ ] 4.9 将 `app/core/skill_cache.py` → `app/infra/skill_cache.py`

## 5. 更新所有 import 路径

- [ ] 5.1 更新 `app/api/` 下所有文件的 import（agent 相关 → `app.agent.*`，trace/limiter → `app.infra.*`）
- [ ] 5.2 更新 `app/services/` 下所有文件的 import
- [ ] 5.3 更新 `app/main.py` 的 import（agents → agent，trace → infra）
- [ ] 5.4 更新模块间的内部交叉引用（如 agent/guardrails.py 引用 agent/llm.py）
- [ ] 5.5 更新 `app/models/__init__.py` 如有需要
- [ ] 5.6 更新 `tests/` 目录下所有测试文件的 import 路径

## 6. 验证与收尾

- [ ] 6.1 运行 `python -m pytest` 全量测试，确认所有测试通过
- [ ] 6.2 运行 `ruff check . && ruff format .` 确认代码规范
- [ ] 6.3 全局搜索 `from app.core.llm`、`from app.core.guardrails`、`from app.core.prompt_`、`from app.core.trace_`、`from app.core.circuit_breaker`、`from app.core.limiter`、`from app.core.pending_actions`、`from app.core.skill_cache`、`from app.agents.` 确认零残留
- [ ] 6.4 确认 `app/core/` 目录仅剩 7 个文件（`__init__.py`、`config.py`、`database.py`、`logger.py`、`date_context.py`、`json_repair.py`、`seed.py`）
- [ ] 6.5 更新 `CLAUDE.md` 快速导航表中的目录说明
