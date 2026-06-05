## Purpose

定义 settings-ui-minimal 能力的行为要求。

## Requirements

### Requirement: 页面背景
The settings screen SHALL use a minimal light gray background.

#### Scenario: Settings background
- **WHEN** the settings screen is rendered
- **THEN** its background MUST be `#F8FAFC`

### Requirement: 用户卡片
The settings screen SHALL display a user profile card at the top.

#### Scenario: User card content
- **WHEN** the user card is rendered
- **THEN** it MUST display the user's avatar, name ("农友"), and AI farm level

### Requirement: 设置项卡片
All settings items SHALL use white cards with consistent height.

#### Scenario: Settings item height
- **WHEN** a settings item is rendered
- **THEN** its height MUST be exactly `64px`

### Requirement: 图标颜色规范
Settings icons SHALL use unified colors based on category.

#### Scenario: AI icon color
- **WHEN** an AI-related icon is rendered
- **THEN** it MUST use color `#8B5CF6`

#### Scenario: Farm icon color
- **WHEN** a farm-related icon is rendered
- **THEN** it MUST use color `#3BB273`

#### Scenario: City icon color
- **WHEN** a city-related icon is rendered
- **THEN** it MUST use color `#5B8CFF`

#### Scenario: Time icon color
- **WHEN** a time-related icon is rendered
- **THEN** it MUST use color `#14B8A6`
