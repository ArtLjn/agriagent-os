## Why

当前 Agent 已注册 19 个 Skill，但并非所有 Skill 都能被 LLM 稳定发现、受统一权限保护、进入工具链扩展、被回归评测覆盖。系统 API 与服务能力也明显大于现有 Skill 能力面，导致“用户能在界面/API 操作的功能”与“用户能通过自然语言让 LLM 调用 Skill 完成的功能”之间存在断层。

这个变更将把 Skill 从零散工具集合升级为可治理的功能入口层：先补齐现有 Skill 的调用闭环，再建立全系统功能到 Skill capability 的覆盖矩阵，最终让适合由 LLM 调用的系统功能都能通过受控 Skill 实现。

## What Changes

- 补齐现有 19 个已注册 Skill 的选择器触发词、工具链映射、metadata、缓存失效、确认策略和评测覆盖。
- 新增 Skill 覆盖审计机制，自动发现“已注册但 selector/chain/evaluation/metadata 未覆盖”的 Skill。
- 建立系统功能覆盖矩阵，将 API/Service 功能分类为已有 Skill、待新增 Skill、Admin Skill、禁止 LLM 调用或无需 Skill。
- 按业务域补齐缺失 Skill，优先覆盖普通农场用户高频能力，再覆盖受管理员权限保护的系统管理能力。
- 将所有写操作 Skill 纳入 metadata 驱动的 `write_confirm` 流程，确保参数校验、pending action、trace、缓存失效和评测一致。
- 将外部网络 Skill 纳入可配置治理，明确启用状态、权限等级、失败降级和评测边界。
- 不引入万能 API 调用 Skill；每个新增 Skill 必须有明确业务语义、参数 schema、权限等级、确认策略和测试。

## Capabilities

### New Capabilities

- `llm-skill-coverage`: 定义系统功能通过 LLM Skill 暴露的覆盖矩阵、覆盖分类、审计规则和完成标准。

### Modified Capabilities

- `agent-intent-router`: 要求 intent/tool 选择覆盖所有已注册且启用的 Skill，并为遗漏提供审计失败。
- `llm-tool-calling`: 强化 Tool Executor 以 metadata 为准处理权限、写确认、外部网络和管理员 Skill。
- `skill-capability-governance`: 要求 Skill metadata、文档、缓存失效、确认 schema 和评测标签完整，不允许长期依赖默认 incomplete metadata。
- `skill-regression-evaluation`: 要求回归报告按 Skill、业务域、权限等级、确认路径和覆盖状态标出缺口。
- `agent-skill-diagnostics`: 要求诊断报告能解释 Skill 未调用是 selector 排除、禁用、权限拒绝、schema 校验失败还是 LLM 未选择。

## Impact

- 后端 Agent 运行时：`backend/app/agent/tool_selector.py`、`backend/app/agent/runtime/tool_executor.py`、`backend/app/agent/executor/pending_actions.py`、`backend/app/agent/skills/metadata.py`。
- Skill 目录：`backend/app/agent/skills/*/skill.md`、`scripts/main.py`、新增缺失业务 Skill。
- 评测与诊断：`backend/app/evaluation/`、`backend/tests/evaluation/`、`backend/tests/skills/`、`backend/tests/agent/`。
- Admin 能力展示：`backend/app/api/admin_config.py` 可展示 coverage、metadata completeness 和启用状态。
- OpenSpec 规范：新增 `llm-skill-coverage`，修改 intent routing、tool calling、skill governance、regression evaluation 和 diagnostics 相关规范。
