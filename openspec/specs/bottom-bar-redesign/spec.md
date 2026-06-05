## Purpose

定义 bottom-bar-redesign 能力的行为要求。

## Requirements

### Requirement: 毛玻璃背景
The bottom navigation bar SHALL use a glassmorphism background.

#### Scenario: BottomBar background
- **WHEN** the BottomBar is rendered
- **THEN** it MUST have `background: rgba(255,255,255,0.7)`
- **AND** it MUST have `backdrop-filter: blur(20px)`

### Requirement: 高度规范
The BottomBar SHALL have a consistent height.

#### Scenario: BottomBar height
- **WHEN** the BottomBar is rendered
- **THEN** its height MUST be exactly `72px`

### Requirement: 胶囊选中态
The active tab SHALL use a floating capsule style instead of a small dot.

#### Scenario: Active tab capsule
- **WHEN** a tab is selected
- **THEN** it MUST display a capsule-shaped background with the gradient from `#5B8CFF` to `#7A7DFF`
- **AND** the icon inside MUST be white

#### Scenario: Inactive tab
- **WHEN** a tab is not selected
- **THEN** it MUST NOT have a capsule background
- **AND** the icon MUST use the inactive color
