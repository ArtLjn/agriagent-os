## Why

task_state(`agent_task_states` 表)在 router r1 决策时不可见,导致多轮承接失效。playground 已观测:用户做完一轮茬口创建后,下一轮相关输入被 router 当成新会话处理,丢失承接。`evaluate_task_state_relevance` + `task_state_routing_input` 已经存在(`app/agent/runtime/task_state_relevance.py`),但没在 router r1 主链路前注入。

## What Changes

- 在 router r1 调用前,从 `agent_task_states` 表读 active task,跑 `evaluate_task_state_relevance` 决策
- 当 `should_inject=True` 时,用 `task_state_routing_input(user_input, active_task)` 拼接路由输入(在原 user_input 前加上"当前任务/缺失信息/已知实体"前缀)
- 不修改 router r1 本身的决策逻辑,仅改变其输入

## Capabilities

### New Capabilities

无。

### Modified Capabilities

- `agent-intent-router`: router r1 输入需感知 task_state,在 should_inject 时拼接路由前缀

## Impact

- 受影响代码:`backend/app/agent/router/service.py`(r1 调用点)、可能涉及 `app/agent/runtime/nodes.py`(若 r1 在 node 内调用)
- 受影响测试:`backend/tests/agent/router/*` 需新增"有 active task 时路由输入含前缀"的 case
- 数据依赖:`agent_task_states` 表(已存在)
- 回滚:移除前缀注入即可,r1 行为退回现状
