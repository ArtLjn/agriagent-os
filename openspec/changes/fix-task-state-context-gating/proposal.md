## Why

两个相关缺陷同时存在,实证见 `backend/scripts/context_multiturn_spike.py` 的 `task_state_db_injection` scenario:

- **#6 过度注入**: `TaskStateSelector.task_state_should_inject` 是死开关(永远 True),relevance 与 ContextBundle 注入脱钩。turn 1 "你好"(relevance=0.10/do_not_inject)时 bundle 仍塞了 `active_task_state` block,污染 LLM 输入。
- **#7 永不更新**: `task_state.missing_information` 没有任何 turn 后 hook 自动剔除。turn 3 user 说 "20 亩"、turn 4 说 "就叫 3 号棚" 后,bundle 里 missing 仍是 `['面积', '种植单元名称']`,LLM 一直看到"缺失面积",会反复追问同样问题。

## What Changes

- 修复 #6: `ContextBuilder.build_runtime_context_bundle` 入口先跑 `evaluate_task_state_relevance(user_input, active_task)`,把 `should_inject` 真正传给 `ContextBuildRequest.task_state_should_inject`(覆盖默认 True)
- 修复 #7: 新增 lightweight entity extractor(先规则版,复用 `task_state_relevance.py` 里的 `_AREA_RE/_UNIT_NAME_RE/_SEASON_RE`),在 turn 后调 `AgentTaskStateStore.upsert_active_task(missing_information=[剔除已补字段])`
- LLM 版 extractor 留给后续 `task-state-updater-hybrid` change

## Capabilities

### New Capabilities

- `task-state-auto-update`: 用户回答后自动从输入抽取 entity,更新 `agent_task_states.missing_information`

### Modified Capabilities

- `agent-context-policy`: `ContextBuilder` 必须消费 `evaluate_task_state_relevance` 决策,作为 TaskStateSelector 的注入闸门

## Impact

- 受影响代码:
  - `backend/app/context/builder.py`(`build_runtime_context_bundle` 入口加 relevance 调用)
  - `backend/app/context/selectors/task_state.py`(无需改,通过 `task_state_should_inject` 控制即可)
  - 新文件 `backend/app/agent/runtime/task_state_updater.py`(规则版 extractor)
  - `backend/app/agent/runtime/nodes.py`(turn 后调 updater)
- 受影响测试:`backend/tests/context/`、`backend/tests/agent/runtime/`
- 数据库:无 schema 变更,复用现有 `agent_task_states` 表
- 回滚:relevance 闸门恢复默认 True;移除 turn 后 updater 调用
