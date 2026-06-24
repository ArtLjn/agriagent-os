## MODIFIED Requirements

### Requirement: Regression draft 可进入评测回放
Evaluation SHALL 支持从 repair pack 中的 regression draft 创建或导入 evaluation replay case。Evaluation SHALL also support regression drafts created from a ReviewIssueChain, preserving the chain source, related turns, expected behavior, expected tools, expected pending, reply assertions, issue assertions and source metadata.

#### Scenario: 导入 regression draft
- **WHEN** 管理员选择 repair pack 中的一条 regression draft 进入 evaluation replay
- **THEN** 系统 SHALL 保留用户输入、期望工具、期望 pending、回复断言、issue assertions 和来源 metadata
- **AND** 导入后的用例 SHALL 可被评测运行引用

#### Scenario: 从问题链导入 regression draft
- **WHEN** 管理员从 ReviewIssueChain 生成 regression draft 并导入 evaluation replay
- **THEN** 系统 SHALL 保留 `chain_id`、`session_id`、`trigger_turn_id`、`context_turn_ids`、`result_turn_ids`、`expected_behavior`、`quality_labels` 和 `root_cause`
- **AND** 导入后的用例 SHALL 能回放相关上下文，而不是只回放 trigger turn
- **AND** 评测报告 SHALL 在失败时保留 `chain_id` 以便回流到 DataFlywheel 每日质检

## ADDED Requirements

### Requirement: 问题链 expected behavior 前置
Evaluation SHALL only accept a ReviewIssueChain-derived regression draft when the chain has human-reviewed expected behavior.

#### Scenario: 缺少 expected behavior
- **WHEN** 管理员尝试从没有 expected behavior 的 ReviewIssueChain 生成 evaluation replay case
- **THEN** 系统 SHALL 拒绝生成评测用例
- **AND** 系统 SHALL 提示管理员先完成问题链审核并填写 expected behavior
