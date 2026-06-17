## ADDED Requirements

### Requirement: Repair pack regression case 执行
Simulation SHALL 支持运行从 failure repair pack 生成或接受的 regression cases，并将运行结果与 `pack_id` 和 `source_sample_id` 关联。

#### Scenario: 运行 repair pack regression case
- **WHEN** 管理员或 vibecoding 触发 repair pack 的 regression cases
- **THEN** Simulation SHALL 执行关联 case
- **AND** 每条结果 SHALL 包含 `pack_id`、`source_sample_id`、`fix_target`、通过状态和失败断言

### Requirement: Simulation 结果回流修复包状态
Simulation SHALL 将 repair pack regression case 的结果提供给 Data Flywheel，用于判断 pack 是否可以标记为已修复。

#### Scenario: 所有关联 regression case 通过
- **WHEN** 一个 repair pack 的所有关联 regression cases 均通过
- **THEN** 系统 SHALL 允许管理员将该 repair pack 标记为已修复
- **AND** 系统 SHALL 显示对应验证摘要

#### Scenario: 任一关联 regression case 失败
- **WHEN** 一个 repair pack 的任一关联 regression case 失败
- **THEN** 系统 SHALL 禁止自动 resolve 关联 labels
- **AND** 系统 SHALL 将失败断言展示为继续修复依据
