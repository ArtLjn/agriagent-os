## ADDED Requirements

### Requirement: 每日质检是最终审核入口
DataFlywheel SHALL use Daily Review as the only UI entry for saving final human review decisions on bad cases. Final decisions include `accepted`, `rejected`, `needs_evidence`, `not_actionable`, `final_labels`, `root_cause`, and `expected_behavior`.

#### Scenario: 保存最终人工判断
- **WHEN** 管理员需要确认一个 DataFlywheel 坏例
- **THEN** 系统 SHALL require the administrator to open the ReviewIssueChain in Daily Review
- **AND** the final decision SHALL be saved against the ReviewIssueChain rather than an isolated turn

#### Scenario: 高级搜索不能保存最终判断
- **WHEN** 管理员在高级搜索中查看 session、request 或 turn
- **THEN** 系统 SHALL NOT expose controls that save `accepted`, `rejected`, `final_labels`, `root_cause`, or `expected_behavior`
- **AND** 系统 SHALL provide a path to create or open a ReviewIssueChain for final review

### Requirement: 高级搜索只作为查证入口
Advanced Search SHALL support locating raw sessions, turns, request IDs, messages, event evidence, trace links, selected tools, actual tools and pending lifecycle, but SHALL NOT create formal regression or repair assets directly.

#### Scenario: 从 turn 创建候选链
- **WHEN** 管理员在高级搜索中发现一个 turn 可能是坏例
- **THEN** 系统 SHALL allow creating a ReviewIssueChain candidate or adding the turn to an existing chain
- **AND** 系统 SHALL direct the administrator to Daily Review to complete final labeling

#### Scenario: 禁止从高级搜索导出正式修复包
- **WHEN** 管理员在高级搜索中查看单个 turn
- **THEN** 系统 SHALL NOT expose the formal repair pack export action for that turn
- **AND** 系统 SHALL explain that repair packs require an accepted ReviewIssueChain with expected behavior

### Requirement: 固定标签集合对齐设计
DataFlywheel SHALL support the fixed label set defined by the data flywheel design, including `tool_parameter_mismatch`, across backend validation, frontend types, filters, and ReviewIssueChain review controls.

#### Scenario: 保存参数作用域错配标签
- **WHEN** 管理员审核一个批量意图被收窄或工具参数作用域错配的问题链
- **THEN** 系统 SHALL allow selecting `tool_parameter_mismatch` as a final label
- **AND** 系统 SHALL persist the label without backend validation errors

#### Scenario: 审核面板展示完整标签集合
- **WHEN** 管理员打开 ReviewIssueChain 审核面板
- **THEN** 系统 SHALL show all supported final labels, including `good_reply`, `bad_reply`, `wrong_tool_selection`, `tool_parameter_mismatch`, `pending_missed`, `hallucinated_execution`, `tool_error_ignored`, `off_topic`, `sensitive_info_leak`, `missing_wage`, `disabled_worker_used`, `unclear_intent`, `not_actionable`, and `needs_regression`

### Requirement: 问题链证据状态完整展示
ReviewIssueChain detail SHALL expose a checklist that distinguishes event log, chat messages, router decision, tool result, pending lifecycle, trace, database diff, and backfilled event status.

#### Scenario: 回填事件可见
- **WHEN** a ReviewIssueChain contains turns whose event payload or message metadata is backfilled
- **THEN** 系统 SHALL mark the evidence as backfilled in the checklist or timeline
- **AND** 系统 SHALL NOT present a backfilled request ID as a complete real trace

#### Scenario: 缺少 trace 或 db diff
- **WHEN** a ReviewIssueChain lacks trace records or database diff evidence
- **THEN** 系统 SHALL show the missing evidence key explicitly
- **AND** 系统 SHALL NOT treat an empty tool or diff section as proof that no tool or database change happened

### Requirement: 问题链闭环出口
The Daily Review issue chain panel SHALL expose chain-derived regression draft and repair pack actions with explicit enablement rules.

#### Scenario: 生成问题链回归草稿
- **WHEN** a ReviewIssueChain is accepted and has expected behavior
- **THEN** 系统 SHALL allow generating a regression draft from the chain
- **AND** the draft SHALL include `chain_id`, `session_id`, trigger turn, context turns, result turns, final labels, root cause, and expected behavior

#### Scenario: 阻止不完整问题链闭环
- **WHEN** a ReviewIssueChain is not accepted, is marked `needs_evidence`, or lacks expected behavior
- **THEN** 系统 SHALL disable formal regression draft and repair pack actions
- **AND** 系统 SHALL show the reason the action is blocked
