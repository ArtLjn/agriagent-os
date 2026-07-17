---
last_updated: 2026-07-17
status: active
---

# 当前迭代

> 本文档跟踪当前迭代中的任务和进度。

## 进行中

- Agent 平台架构地基：完成 Prompt、Context、Memory、Evaluation 骨架与最终验证；已清理仅含 `__init__.py` 的空壳模块目录。

## 待办

- 后续删除仍保留的兼容入口前，先按 `docs/architecture/compatibility-entries.md` 逐项确认调用方迁移完成。
- 后续业务模块迁移按真实职责推进：`crop`、`cycle`、`ledger`、`weather`、`conversation`、`feedback`、`admin` 只有在 router/service/dependencies/ports 至少一类职责落地时才创建目录。

## 已完成

- Auth 模块化：密码、Token、权限、用户依赖和稳定错误码已迁移到 `app.modules.auth`。
- 平台级 `skills/` 迁移已整体迁出 `agent/skills/` 的注册、权限、schema 和执行适配；旧 agent skills 兼容入口已删除，新增 Skill 必须进入 `app.skills`。
- Bootstrap 与 API 瘦身：应用启动逻辑进入 `app.bootstrap`，Agent API 业务编排已迁移到顶层 `app.application`，旧 agent application 兼容入口已删除。
- Context selector 与茬口小 operation 收束：`conversation/cycle/farm/ledger/retrieval/user_settings/weather` 旧 selector 子模块兼容壳已删除，真实入口为 `app.context.selectors.core` 或包级 `app.context.selectors`；`create_cycle/delete_cycle/query_cycles/query_cycle_info` 旧小脚本兼容壳已删除，真实入口为 `app.skills.manage-crop-cycle.scripts.main`。
- Agent 根兼容壳清理：`advisor`、`report`、`skill_coverage`、`intent_router`、`tool_selector`、`tool_selection_rules`、`llm`、`assistant_roles` 旧入口已删除，生产代码和测试使用真实路径。
- Agent Runtime 拆分：`app.agent.graph` 已收敛为兼容门面，Runtime、Planner、Executor、Response、Sessions、Ports 边界已建立。
- Prompt、Context、Memory、Evaluation 平台骨架：已建立 `app.prompt`、`app.context`、`app.memory`、`app.platforms.evaluation`，旧 Evaluation 根包已下线，并补充对应单元测试与回归测试。
- DataFlywheel 平台迁移：真实代码已迁入 `app.platforms.data_flywheel`，旧 DataFlywheel 根包与 root 兼容薄壳已下线。
- 架构门禁债务：`services -> core` 违规依赖已通过 `infra` 适配层修复；`agent_service.py` 与 `web_search/scripts/main.py` 已拆分到 500 行以内。
