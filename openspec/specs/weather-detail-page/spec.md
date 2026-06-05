## Purpose

定义 weather-detail-page 能力的行为要求。

## Requirements

### Requirement: 页面背景
The weather detail screen SHALL use a sky-themed gradient background.

#### Scenario: Weather detail background
- **WHEN** the weather detail screen is rendered
- **THEN** its background MUST use the gradient from `#BFD8FF` (0%) to `#EAF3FF` (60%) to `#FFFFFF` (100%)

### Requirement: 顶部大温度显示
The weather detail screen SHALL display a large temperature reading at the top.

#### Scenario: Large temperature display
- **WHEN** the weather detail screen shows current weather
- **THEN** the temperature MUST be displayed in a very large font size
- **AND** the weather condition text MUST be displayed below it

### Requirement: 小时天气卡片
The hourly forecast SHALL use semi-transparent glassmorphism cards.

#### Scenario: Hourly forecast cards
- **WHEN** hourly weather is displayed
- **THEN** each hour card MUST have `background: rgba(255,255,255,0.25)`
- **AND** it MUST have `backdrop-filter: blur(20px)`

### Requirement: 7日趋势图
The 7-day forecast SHALL display a temperature trend line chart.

#### Scenario: Trend chart line
- **WHEN** the 7-day trend chart is rendered
- **THEN** the line color MUST be `#7AA8FF`

#### Scenario: Trend chart nodes
- **WHEN** the trend chart shows data points
- **THEN** each node MUST use color `#FFFFFF`

#### Scenario: Horizontal scroll
- **WHEN** the user views the hourly forecast
- **THEN** it MUST be horizontally scrollable
