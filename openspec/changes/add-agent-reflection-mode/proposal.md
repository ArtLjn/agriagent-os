## Why

当前 Agent 已有 ReAct 工具循环、Plan-Then-Execute 写操作确认、trace 和评测诊断，但缺少在线自检控制层。高风险写操作、复杂多工具回答、工具应调未调和兜底回复等场景需要在最终输出前做一致性、风险和完整性检查，避免错误执行或把不可靠回复交给用户。

## What Changes

- 新增 Agent Reflection 控制能力，在请求生命周期中以触发式方式执行自检，而不是作为用户手动切换的聊天模式。
- 为写操作 pending plan 增加执行前反思，检查意图清晰度、参数完整性、风险等级、依赖关系和确认文案是否一致。
- 为工具执行后回复增加反思，检查最终回复是否基于真实工具结果、是否遗漏必要工具、是否出现工具结果与自然语言结论矛盾。
- 为反思结果增加结构化 trace 事件，支持 Evaluation 与数据飞轮回收失败样本。
- 不引入破坏性 API 变更；默认先以高风险触发式策略接入，避免每轮请求都增加延迟和 token 成本。

## Capabilities

### New Capabilities
- `agent-reflection-control`: 定义 Agent 在线反思控制层的触发策略、检查结果、动作决策和可观测事件。

### Modified Capabilities
- `agent-platform-architecture`: 在标准 Agent 请求生命周期中纳入触发式 Reflection 控制层，并明确其与 Runtime、Evaluation、Observability 的边界。
- `write-skill-plan-execution`: 写操作 Plan-Then-Execute 流程在展示 pending action 或执行 pending plan 前必须通过反思检查。

## Impact

- 影响后端 Agent 平台：`backend/app/agent/` 下新增 reflector 边界，Agent Application/Runtime 在关键节点调用反思服务。
- 影响写操作安全链路：pending action、pending plan 和 write skill 执行前增加结构化检查结果。
- 影响观测与评测：新增 reflection trace 事件、评测指标和失败样本标签。
- 影响测试：需要覆盖反思触发策略、写操作阻断、工具后自检、trace 记录和回归评测样本。
