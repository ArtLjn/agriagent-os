## ADDED Requirements

### Requirement: 全局配色系统
The theme system SHALL provide a unified color palette with three primary colors.

#### Scenario: Primary blue usage
- **WHEN** any component uses the primary blue color
- **THEN** it MUST use `#5B8CFF`

#### Scenario: AI purple usage
- **WHEN** any component uses the AI accent color
- **THEN** it MUST use `#8B5CF6`

#### Scenario: Agriculture green usage
- **WHEN** any component uses the success/agriculture color
- **THEN** it MUST use `#3BB273`

### Requirement: 全局背景色
The theme system SHALL provide background colors that are low-saturation and never pure white.

#### Scenario: Global background
- **WHEN** the app background is rendered
- **THEN** it MUST use `#F6F8FC` or the gradient from `#F7FAFF` to `#FFFFFF`

### Requirement: 圆角规范
The theme system SHALL enforce border radius values based on element type.

#### Scenario: Large card radius
- **WHEN** a large card is rendered
- **THEN** it MUST have `border-radius: 28px`

#### Scenario: Small card radius
- **WHEN** a small card is rendered
- **THEN** it MUST have `border-radius: 22px`

#### Scenario: Button radius
- **WHEN** a button is rendered
- **THEN** it MUST have `border-radius: 18px`

#### Scenario: Input radius
- **WHEN** an input field is rendered
- **THEN** it MUST have `border-radius: 20px`

#### Scenario: BottomBar radius
- **WHEN** the bottom navigation bar is rendered
- **THEN** it MUST have `border-radius: 30px` on top corners

### Requirement: 阴影规范
The theme system SHALL provide soft shadow values that avoid heavy Android-style shadows.

#### Scenario: Card shadow
- **WHEN** a card uses shadow
- **THEN** it MUST use `box-shadow: 0 8px 30px rgba(91,140,255,0.08)`

#### Scenario: Light shadow
- **WHEN** a component uses light shadow
- **THEN** it MUST use `box-shadow: 0 4px 16px rgba(0,0,0,0.04)`

### Requirement: 字体规范
The theme system SHALL provide typography standards with specific sizes and weights.

#### Scenario: Primary heading
- **WHEN** a primary heading is rendered
- **THEN** it MUST have `font-size: 32px`, `font-weight: 700`, `letter-spacing: -0.5px`

#### Scenario: Secondary heading
- **WHEN** a secondary heading is rendered
- **THEN** it MUST have `font-size: 22px`, `font-weight: 600`

#### Scenario: Card body text
- **WHEN** card body text is rendered
- **THEN** it MUST have `font-size: 15px`, `color: #6B7280`, `line-height: 1.6`
