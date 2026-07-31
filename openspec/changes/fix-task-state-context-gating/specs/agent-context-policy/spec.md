## MODIFIED Requirements

### Requirement: ContextBuilder 必须消费 relevance 决策作为 TaskStateSelector 注入闸门

`ContextBuilder.build_runtime_context_bundle` 在调 `TaskStateSelector` 前必须显式调 `evaluate_task_state_relevance(user_input, active_task)`,并把 `should_inject` 通过 `ContextBuildRequest.task_state_should_inject` 传给 selector。`task_state_should_inject` 不得保持默认 True。

#### Scenario: should_inject=False 时 bundle 不含 active_task_state

- **WHEN** 用户输入 "你好" 且 active task 存在,relevance 算出 `should_inject=False`
- **THEN** ContextBundle 的 blocks 列表不得包含 `active_task_state` block

#### Scenario: should_inject=True 时 bundle 含 active_task_state

- **WHEN** 用户输入 "20 亩" 且 active task 存在,relevance 算出 `should_inject=True`
- **THEN** ContextBundle 的 blocks 列表必须包含 `active_task_state` block,内容含 goal/entities/missing_information

#### Scenario: 无 active task 时 relevance 短路返回

- **WHEN** 当前会话无 active task
- **THEN** relevance 直接返回 `should_inject=False`,ContextBuilder 不调 selector,bundle 不含 task_state
