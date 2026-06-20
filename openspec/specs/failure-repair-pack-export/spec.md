# failure-repair-pack-export Specification

## Purpose

TBD

## Requirements

### Requirement: 失败样本修复路由
系统 SHALL 根据 Data Flywheel 样本的人工标签、LLM 预标注、issue candidates 和 case draft 派生修复候选信息，至少包含 `fix_target`、`priority`、`suggested_action`、`regression_ready` 和 `verification_commands`。

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

### Requirement: 生成失败案例修复包
系统 SHALL 支持管理员从 Data Flywheel 中按标签、`fix_target`、优先级、样本数量和回归准备状态选择失败样本，并导出为 repair pack 目录。

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

### Requirement: Repair pack 脱敏与证据完整性
系统 SHALL 在导出 debug evidence 前进行脱敏，并在证据缺失时显式记录 warning。

#### Scenario: debug evidence 包含密钥
- **WHEN** debug export 或 event payload 中包含 API key、token、secret 或 `.env` 内容
- **THEN** 导出的 debug JSON SHALL 用占位符替换敏感值
- **AND** repair pack SHALL 保留字段名、hash 或摘要用于定位

#### Scenario: 事件片段缺失
- **WHEN** 样本的 event file 或 seq range 无法读取
- **THEN** 系统仍可导出 MySQL 可用的消息和标签证据
- **AND** `manifest.json.warnings` SHALL 包含缺失的 `sample_id` 和缺失原因
- **AND** 该案例的 `regression_ready` SHALL 为 false

### Requirement: Vibecoding 消费说明
系统 SHALL 在 repair pack 的 `README.md` 中生成面向 vibecoding 的操作说明，要求 coding agent 先复现或补回归测试，再进行最小范围修复，最后运行 manifest 中的验证命令。

#### Scenario: README 包含修复步骤
- **WHEN** repair pack 导出成功
- **THEN** `README.md` SHALL 包含读取顺序、修复目标、限制条件、验证命令和完成回报格式
- **AND** README SHALL 明确禁止把 bad reply 直接作为训练数据使用

### Requirement: Repair pack 状态回写
系统 SHALL 支持将 repair pack 关联的 open labels 标记为 resolved，并保留修复说明。

#### Scenario: 修复通过后标记 resolved
- **WHEN** 管理员对一个 repair pack 执行“标记已修复”
- **THEN** 系统将该 pack 关联的 open labels 标记为 `resolved`
- **AND** 系统保存修复说明、验证摘要和操作者
- **AND** Data Flywheel 列表不再把这些 resolved labels 计入 open bad case

#### Scenario: 修复未通过时保持 open
- **WHEN** repair pack 的验证结果为失败
- **THEN** 系统 SHALL 保持关联 labels 为 open
- **AND** 系统记录失败摘要，供后续继续修复
