## ADDED Requirements

### Requirement: 用户回答后自动剔除 missing_information

每个 turn 在 assistant 回复写库后,系统必须运行 entity extractor 抽取用户输入中的关键字段(面积/季节/种植单元名称),并从 `agent_task_states.missing_information` 列表中剔除已补字段。无 active task 时跳过。

#### Scenario: 用户回答面积后剔除 missing

- **WHEN** active task 的 missing_information 含"面积",且用户输入 "20 亩"
- **THEN** extractor 抽出面积字段,调 `AgentTaskStateStore.upsert_active_task(missing_information=[剔除"面积"后的剩余列表])`,后续轮次 bundle 中 active_task_state block 不再显示"面积"为缺失

#### Scenario: 用户回答种植单元名称后剔除 missing

- **WHEN** active task 的 missing_information 含"种植单元名称",且用户输入 "就叫 3 号棚"
- **THEN** extractor 抽出名称字段,missing_information 剔除"种植单元名称"

#### Scenario: 用户输入未命中任何规则时 missing 不变

- **WHEN** active task 的 missing_information 含"面积",且用户输入 "你好"
- **THEN** extractor 不抽出任何字段,missing_information 保持不变

#### Scenario: 无 active task 时跳过 extractor

- **WHEN** 当前会话无 active task(`agent_task_states` 表无记录或已过期)
- **THEN** extractor 不执行,turn 正常结束
