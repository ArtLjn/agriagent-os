## Why

`fix-task-state-context-gating` 上线后,需要 Layer 1 工程加固防止静默漂移与已知窗口失忆:

- 当前没有 trace 告警机制,relevance vs bundle 一致性破坏时静默不可见
- `session_summary_message_threshold=12 + debounce=30min` 在长对话场景留有失忆窗口(spike `recent_messages_truncation` turn 9-10 之间 recent 已截断但 summary 未触发)
- spike probe (`router_c_spike.py` / `context_multiturn_spike.py` / `planner_probe.py`) 未接入 CI,失忆点回归无自动化兜底

## What Changes

- 新增 trace 告警:`relevance.should_inject` 与 bundle 中 `active_task_state` 实际存在性不一致时打 warning
- `session_summary_message_threshold` 12→8,`session_summary_debounce_minutes` 30→10
- 把 `context_multiturn_spike.py` 接入 CI 作回归 probe(PR 必跑 3 个核心 scenario)

## Capabilities

### New Capabilities

- `context-consistency-warnings`: relevance 决策与 ContextBundle 实际注入的一致性告警

### Modified Capabilities

- `agent-memory-foundation`: summary 触发参数调整(threshold 12→8, debounce 30→10)
- `agent-evaluation-foundation`: context_multiturn_spike 接入 CI 作回归 probe

## Impact

- 受影响代码:
  - `backend/app/context/builder.py`(出口加一致性检查,打 trace warning)
  - `backend/app/shared/config.py`(改默认值)
  - `.github/workflows/*.yml` 或 `.gitlab-ci.yml`(加 spike probe job)
- 受影响配置:`session_summary_message_threshold`, `session_summary_debounce_minutes`
- 运行时影响:summary 触发频率上升约 50%(threshold 12→8),LLM 成本略增
- 回滚:恢复 config 默认值;移除 trace 告警;CI 移除 spike job
