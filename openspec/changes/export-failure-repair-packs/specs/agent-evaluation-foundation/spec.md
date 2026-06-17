## ADDED Requirements

### Requirement: Repair pack 来源评测追踪
Evaluation SHALL 支持识别从 failure repair pack 派生的评测用例，并在评测结果中保留 `pack_id`、`source_sample_id`、`fix_target` 和原始标签。

#### Scenario: 运行 repair pack 派生用例
- **WHEN** 开发者运行来源为 repair pack 的 evaluation replay case
- **THEN** 评测报告 SHALL 包含对应 `pack_id`、`source_sample_id`、`fix_target`、`quality_labels` 和断言结果
- **AND** 失败结果 SHALL 能回流到 Data Flywheel 作为仍未修复的样本证据

### Requirement: Regression draft 可进入评测回放
Evaluation SHALL 支持从 repair pack 中的 regression draft 创建或导入 evaluation replay case。

#### Scenario: 导入 regression draft
- **WHEN** 管理员选择 repair pack 中的一条 regression draft 进入 evaluation replay
- **THEN** 系统 SHALL 保留用户输入、期望工具、期望 pending、回复断言、issue assertions 和来源 metadata
- **AND** 导入后的用例 SHALL 可被评测运行引用
