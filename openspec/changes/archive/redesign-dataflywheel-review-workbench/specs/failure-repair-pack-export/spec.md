## MODIFIED Requirements

### Requirement: 失败样本修复路由
系统 SHALL 根据 Data Flywheel 样本或 ReviewIssueChain 的人工标签、LLM 预标注、issue candidates、expected behavior 和 case draft 派生修复候选信息，至少包含 `fix_target`、`priority`、`suggested_action`、`regression_ready` 和 `verification_commands`。

#### Scenario: pending 漏拦截样本路由到 pending plan
- **WHEN** 样本包含 open 状态的 `pending_missed` 标签
- **THEN** 系统将该样本的主 `fix_target` 设置为 `pending_plan`
- **AND** `suggested_action` 描述修复写操作确认计划和多步骤 pending lifecycle
- **AND** 如果 case draft 包含 `expected_pending_action` 或 `issue_assertions`，`regression_ready` 为 true

#### Scenario: 多标签样本按优先级选择主修复目标
- **WHEN** 样本同时包含 `sensitive_info_leak` 和 `bad_reply`
- **THEN** 系统将主 `fix_target` 设置为 `guardrail`
- **AND** 系统仍在导出 case 中保留全部标签和次级修复建议

#### Scenario: 未知标签进入人工分诊
- **WHEN** 样本只包含系统无法识别的 open 标签
- **THEN** 系统将 `fix_target` 设置为 `manual_triage`
- **AND** 系统要求管理员在导出前确认或覆盖修复目标

#### Scenario: 参数作用域错配问题链路由到 router
- **WHEN** ReviewIssueChain 包含 `tool_parameter_mismatch` 或 `bulk_intent_narrowed_to_single_entity` 候选类型
- **THEN** 系统 SHALL 将主 `fix_target` 设置为 `router`
- **AND** `suggested_action` SHALL 描述修复参数抽取、批量作用域保持或 pending 确认策略
- **AND** 如果问题链包含 expected behavior 和 related turn evidence，`regression_ready` SHALL 为 true

### Requirement: 生成失败案例修复包
系统 SHALL 支持管理员从 Data Flywheel 中按标签、`fix_target`、优先级、样本数量和回归准备状态选择失败样本或 ReviewIssueChain，并导出为 repair pack 目录。

#### Scenario: 导出 pending plan 修复包
- **WHEN** 管理员选择 `fix_target=pending_plan` 且样本数量上限为 5
- **THEN** 系统创建一个唯一 `pack_id`
- **AND** 系统导出 `manifest.json`、`cases.jsonl`、`README.md`、`debug/` 和 `regression-drafts/`
- **AND** `manifest.json` 包含 `fix_target`、`goal`、`labels`、`source_sample_ids`、`verification_commands` 和 `warnings`

#### Scenario: 单包不得混合多个主修复目标
- **WHEN** 管理员选择的样本包含多个不同主 `fix_target`
- **THEN** 系统拒绝导出单个混合 repair pack
- **AND** 系统返回每个 `fix_target` 对应的分组建议

#### Scenario: 导出问题链修复包
- **WHEN** 管理员选择一个已 accepted 且 regression-ready 的 ReviewIssueChain 导出 repair pack
- **THEN** 系统 SHALL 创建一个唯一 `pack_id`
- **AND** `manifest.json` SHALL 包含 `source_chain_ids`、`source_sample_ids`、`fix_target`、`labels`、`root_cause`、`verification_commands` 和 `warnings`
- **AND** `cases.jsonl` SHALL 保留 trigger/context/result turns 的来源信息

#### Scenario: 导出样本必须可追溯
- **WHEN** repair pack 包含一条失败案例
- **THEN** `cases.jsonl` 中该案例 SHALL 包含 `sample_id`、`session_id`、`turn_id`、`request_id`、`labels`、`fix_target`、`observed_failure`、`expected_behavior`、`source_debug_json` 和 `regression_draft`

#### Scenario: 导出问题链必须可追溯
- **WHEN** repair pack 包含一条来源为 ReviewIssueChain 的失败案例
- **THEN** `cases.jsonl` 中该案例 SHALL 包含 `chain_id`、`session_id`、`trigger_turn_id`、`context_turn_ids`、`result_turn_ids`、`labels`、`root_cause`、`fix_target`、`observed_failure`、`expected_behavior`、`source_debug_json` 和 `regression_draft`
- **AND** debug evidence SHALL include the related turn messages and available tool/pending evidence

## ADDED Requirements

### Requirement: 问题链证据不足禁止导出
系统 SHALL prevent repair pack export from a ReviewIssueChain when the chain is marked `needs_evidence` or lacks human-reviewed expected behavior.

#### Scenario: 问题链缺少 expected behavior
- **WHEN** 管理员尝试导出没有 expected behavior 的 ReviewIssueChain
- **THEN** 系统 SHALL 拒绝导出 repair pack
- **AND** 系统 SHALL 提示管理员先完成问题链审核

#### Scenario: 问题链证据缺失
- **WHEN** 管理员尝试导出状态为 `needs_evidence` 的 ReviewIssueChain
- **THEN** 系统 SHALL 拒绝导出 repair pack
- **AND** 系统 SHALL 展示缺失证据清单
