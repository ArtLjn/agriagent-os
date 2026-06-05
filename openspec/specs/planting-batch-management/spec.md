# planting-batch-management Specification

## Purpose
TBD - created by archiving change mvp-planting-operations. Update Purpose after archive.
## Requirements
### Requirement: 种植批次代表一批作物生产周期
系统 SHALL 将种植批次作为作物生产管理的主对象，一个种植批次代表同一作物、同一生产周期下的一批种植活动，而不是单个亩、棚或地块。

#### Scenario: 创建春茬西瓜批次
- **WHEN** 用户创建“2026 春茬 8424 西瓜”并填写总面积 18 亩
- **THEN** 系统 SHALL 创建 1 个种植批次，而不是要求用户为每亩或每个棚创建独立茬口

#### Scenario: 批次列表展示面积和单元数
- **WHEN** 用户打开种植规划列表
- **THEN** 系统 SHALL 展示每个批次的作物、品种、总面积、种植单元数量、当前阶段和状态

### Requirement: 种植批次可包含多个种植单元
系统 SHALL 允许一个种植批次维护多个种植单元，用于表达棚、地块或区域。

#### Scenario: 添加多个棚作为种植单元
- **WHEN** 用户在春茬西瓜批次下添加“东大棚 1-3 号”和“东大棚 4-6 号”
- **THEN** 系统 SHALL 将这些棚作为同一批次下的种植单元保存

#### Scenario: 统计批次总面积
- **WHEN** 批次下存在多个带面积的种植单元
- **THEN** 系统 SHALL 能按种植单元面积汇总批次面积，并允许与用户填写的总面积进行展示对比

### Requirement: 兼容旧茬口字段
系统 MUST 保持现有茬口数据可读，并将旧 `field_name` 作为兼容展示信息处理。

#### Scenario: 查看旧茬口
- **WHEN** 用户查看升级前创建的茬口
- **THEN** 系统 SHALL 继续展示旧地块名，并允许用户后续补充分解为种植单元

