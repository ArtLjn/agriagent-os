## MODIFIED Requirements

### Requirement: Spike Probe 接入 CI 作回归门禁

`backend/scripts/context_multiturn_spike.py` 必须接入 CI,在每个 PR 流水线跑 3 个核心 scenario 并校验关键不变量。scenario 失败时 CI 必须报错(warn-only 阶段可降级,稳定后转 hard fail)。

#### Scenario: PR 跑 task_state_db_injection

- **WHEN** 任何 PR 触发 CI
- **THEN** 必须执行 `python -m scripts.context_multiturn_spike --only task_state_db_injection`,断言:turn 1 bundle 不含 active_task_state,turn 3+ missing 含"面积"被剔除

#### Scenario: PR 跑 recent_messages_truncation

- **WHEN** 任何 PR 触发 CI
- **THEN** 必须执行 `python -m scripts.context_multiturn_spike --only recent_messages_truncation`,断言:turn 13 bundle 含 conversation_summary,且 summary 含"西瓜"或"番茄"关键词

#### Scenario: PR 跑 long_query_summary_trigger

- **WHEN** 任何 PR 触发 CI
- **THEN** 必须执行 `python -m scripts.context_multiturn_spike --only long_query_summary_trigger`,断言:至少 1 个 turn 触发 summary_changed=True
