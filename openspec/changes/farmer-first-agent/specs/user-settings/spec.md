## ADDED Requirements

### Requirement: 用户称呼设置
用户设置 SHALL 新增 `display_name` 字段，用于 Agent 回复时的个性化称呼。

#### Scenario: 设置称呼
- **WHEN** 用户在设置页输入 display_name="老李" 并保存
- **THEN** 后续 Agent 回复开头使用「老李」

#### Scenario: 默认称呼
- **WHEN** 用户未设置 display_name
- **THEN** Agent 使用默认称呼「农友」

#### Scenario: 修改称呼
- **WHEN** 用户将 display_name 从"老李"改为"李哥"
- **THEN** 后续 Agent 回复使用「李哥」
