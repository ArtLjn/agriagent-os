## MODIFIED Requirements

### Requirement: 生成失败案例修复包
系统 SHALL 支持管理员从 Data Flywheel 中按标签、`fix_target`、优先级、样本数量和回归准备状态选择失败样本，并导出为 repair pack 目录。For formal DataFlywheel review workflows, the system SHALL create repair packs from accepted ReviewIssueChain objects with expected behavior; sample-level export SHALL remain only as an explicit compatibility or debug path.

#### Scenario: 导出 pending plan 修复包
- **WHEN** 管理员选择 `fix_target=pending_plan` 且样本数量上限为 5
- **THEN** 系统创建一个唯一 `pack_id`
- **AND** 系统导出 `manifest.json`、`cases.jsonl`、`README.md`、`debug/` 和 `regression-drafts/`
- **AND** `manifest.json` 包含 `fix_target`、`goal`、`labels`、`source_sample_ids`、`verification_commands` 和 `warnings`

#### Scenario: 单包不得混合多个主修复目标
- **WHEN** 管理员选择的样本包含多个不同主 `fix_target`
- **THEN** 系统拒绝导出单个混合 repair pack
- **AND** 系统返回每个 `fix_target` 对应的分组建议

#### Scenario: 导出样本必须可追溯
- **WHEN** repair pack 包含一条失败案例
- **THEN** `cases.jsonl` 中该案例 SHALL 包含 `sample_id`、`session_id`、`turn_id`、`request_id`、`labels`、`fix_target`、`observed_failure`、`expected_behavior`、`source_debug_json` 和 `regression_draft`

#### Scenario: 默认从问题链导出正式修复包
- **WHEN** 管理员在 Daily Review 中导出 repair pack
- **THEN** 系统 SHALL use the selected accepted ReviewIssueChain as the source
- **AND** `manifest.json` SHALL include `source_chain_ids`, `source_sample_ids`, `root_cause`, `expected_behavior`, `fix_target`, `labels`, `verification_commands`, and evidence warnings
- **AND** `cases.jsonl` SHALL include trigger, context and result turn references

#### Scenario: 高级搜索不暴露正式导出
- **WHEN** 管理员在 Advanced Search or Turn Review compatibility view opens a raw turn
- **THEN** 系统 SHALL NOT expose the formal repair pack export control
- **AND** 系统 SHALL direct the administrator to create or open a ReviewIssueChain first

## ADDED Requirements

### Requirement: Sample 级 repair pack 出口兼容限制
Sample-level repair pack export SHALL be treated as a compatibility/debug path and SHALL NOT be the default product path for confirmed DataFlywheel issues.

#### Scenario: Compatibility export is explicit
- **WHEN** a caller uses the sample-level repair pack API
- **THEN** 系统 SHALL mark the result or API documentation as compatibility/debug output
- **AND** product UI SHALL NOT use this path for normal Daily Review repair pack export

#### Scenario: 缺少 expected behavior 的 sample 不进入正式修复包
- **WHEN** a raw turn sample has no linked accepted ReviewIssueChain with expected behavior
- **THEN** 系统 SHALL NOT present it as ready for formal repair pack export in the UI
- **AND** 系统 SHALL require issue chain review before formal export
