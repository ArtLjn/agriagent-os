## ADDED Requirements

### Requirement: Relevance 与 ContextBundle 注入一致性告警

`ContextBuilder.build_runtime_context_bundle` 出口必须检查 `relevance.should_inject` 与最终 bundle 中是否存在 `active_task_state` block 的一致性。不一致时打 trace 级别 warning,含决策上下文(farm_id/session_id/relevance_score/decision/actual_blocks)。

#### Scenario: should_inject=True 但 bundle 缺 active_task_state

- **WHEN** relevance 计算出 `should_inject=True`,但最终 bundle.blocks 中无 `active_task_state` block(可能因 selector 异常或表过期)
- **THEN** trace 必须含 warning 事件 `task_state_injection_inconsistent`,字段含 `expected=true, actual=false, reason=...`

#### Scenario: should_inject=False 但 bundle 含 active_task_state

- **WHEN** relevance 计算出 `should_inject=False`,但最终 bundle.blocks 中仍含 `active_task_state` block
- **THEN** trace 必须含 warning 事件 `task_state_injection_inconsistent`,字段含 `expected=false, actual=true`

#### Scenario: 一致时不打 warning

- **WHEN** should_inject 与 bundle 一致(True+注入 / False+不注入 / 无 active_task 短路)
- **THEN** trace 不打 warning,可打 info 级别 trace 记录决策上下文
