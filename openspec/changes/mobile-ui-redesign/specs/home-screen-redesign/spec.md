## ADDED Requirements

### Requirement: 页面结构
The home screen SHALL follow a strict vertical layout with large whitespace between sections.

#### Scenario: Home screen layout
- **WHEN** the home screen is displayed
- **THEN** it MUST show sections in order: greeting header → weather card → AI briefing card → quick actions → bottom navigation
- **AND** each section MUST have adequate vertical spacing (breathing room)

### Requirement: 顶部问候区
The header SHALL display a personalized greeting with the current date and an AI icon button.

#### Scenario: Morning greeting
- **WHEN** the time is before 11:00
- **THEN** the greeting MUST display "早上好，农友"

#### Scenario: AI icon button
- **WHEN** the AI icon button is rendered
- **THEN** it MUST have background color `#EDF4FF`
- **AND** tapping it MUST navigate to the AI chat screen

### Requirement: 天气大卡片
The weather card SHALL be a large gradient card displaying current weather with a 3-day forecast.

#### Scenario: Weather card appearance
- **WHEN** the weather card is rendered
- **THEN** it MUST use the gradient background from `#5B8CFF` to `#7AA8FF` at 135 degrees
- **AND** it MUST display current temperature, weather condition, and feels-like temperature

#### Scenario: 3-day forecast
- **WHEN** the weather card shows forecast
- **THEN** it MUST display today, tomorrow, and the day after tomorrow with simple icons

### Requirement: AI 晨间简报卡片
The AI briefing card SHALL be an emotion-based card that changes background based on weather conditions.

#### Scenario: Foggy day card
- **WHEN** the weather is foggy
- **THEN** the card background MUST use the gradient from `#EAF3FF` to `#F7F9FF`

#### Scenario: Sunny day card
- **WHEN** the weather is sunny
- **THEN** the card background MUST use the gradient from `#FFF4D6` to `#FFF9EA`

#### Scenario: Rainy day card
- **WHEN** the weather is rainy
- **THEN** the card background MUST use the gradient from `#DCEBFF` to `#EEF5FF`

#### Scenario: Cold day card
- **WHEN** the temperature drops significantly
- **THEN** the card background MUST use the gradient from `#E7F2FF` to `#F3F8FF`

### Requirement: 渐变标题文字
The briefing card title SHALL use gradient text instead of solid black.

#### Scenario: Gradient title
- **WHEN** the briefing card title is rendered
- **THEN** it MUST use the gradient from `#4DA2FF` to `#C26CFF`
- **AND** it MUST use `-webkit-background-clip: text` effect

### Requirement: AI 小宠物
The home screen SHALL display a small AI pet in the bottom-right corner.

#### Scenario: AI pet appearance
- **WHEN** the AI pet is rendered
- **THEN** it MUST be 72px in size
- **AND** it MUST have opacity 0.9
- **AND** it MUST have a floating/breathing animation

### Requirement: 快捷功能区
The quick actions SHALL be displayed as horizontally scrollable cards, not a grid.

#### Scenario: Quick action cards
- **WHEN** quick actions are displayed
- **THEN** they MUST be in a horizontal scrollable row
- **AND** each card MUST have a low-saturation background color

#### Scenario: Planting card color
- **WHEN** the planting planning card is rendered
- **THEN** its background MUST be `#EDFDF3`

#### Scenario: Reminder card color
- **WHEN** the farming reminder card is rendered
- **THEN** its background MUST be `#EEF4FF`

#### Scenario: Weather card color
- **WHEN** the weather trend card is rendered
- **THEN** its background MUST be `#FFF8E8`

#### Scenario: Pest card color
- **WHEN** the pest identification card is rendered
- **THEN** its background MUST be `#FFF1F2`

### Requirement: 按钮样式
Buttons SHALL use glassmorphism style instead of solid colors.

#### Scenario: Glassmorphism button
- **WHEN** a button uses the glassmorphism style
- **THEN** it MUST have `background: rgba(255,255,255,0.7)` and `backdrop-filter: blur(10px)`
