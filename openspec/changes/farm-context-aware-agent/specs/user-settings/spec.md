## ADDED Requirements

### Requirement: 默认关注茬口设置
settingsStore SHALL 新增 `default_active_cycles` 字段，用于用户手动指定优先关注的茬口（当 Agent 生成建议时优先展示）。

#### Scenario: 设置关注茬口
- **WHEN** 用户在设置页选择"关注茬口"，勾选"春季西瓜"
- **THEN** settingsStore 保存 `default_active_cycles: [123]`，每日建议页面优先展示该茬口

#### Scenario: 未设置时自动选择
- **WHEN** 用户未设置关注茬口
- **THEN** 系统默认关注所有 active 茬口

### Requirement: 作物模板偏好
settingsStore SHALL 新增 `preferred_crop_templates` 字段，记录用户常用的作物模板 ID 列表。

#### Scenario: 保存常用作物
- **WHEN** 用户在"常种作物"设置中选择"西瓜、豆角、小瓜"
- **THEN** settingsStore 保存对应的 crop_template_id 列表，创建茬口时优先展示这些模板

### Requirement: 赊账提醒偏好
settingsStore SHALL 新增 `debt_reminder_enabled` 字段，控制是否在首页显示待还/待收提醒。

#### Scenario: 开启赊账提醒
- **WHEN** 用户开启"赊账提醒"
- **THEN** 首页显示待还金额和待收金额的快速入口

#### Scenario: 关闭赊账提醒
- **WHEN** 用户关闭"赊账提醒"
- **THEN** 首页不显示赊账相关信息
