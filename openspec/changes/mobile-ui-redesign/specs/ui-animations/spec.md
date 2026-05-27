## ADDED Requirements

### Requirement: 卡片进入动画
Cards SHALL use fade-in and slide-up animation when entering the screen.

#### Scenario: Card entrance animation
- **WHEN** a card appears on screen
- **THEN** it MUST animate with fade-in + translateY
- **AND** the animation duration MUST be `0.45s`

### Requirement: AI 卡片呼吸动画
AI-related cards SHALL have a subtle breathing/floating animation.

#### Scenario: AI card breathing
- **WHEN** an AI card is displayed
- **THEN** it MUST have a continuous subtle floating animation
- **AND** the vertical movement MUST be within `4px`

### Requirement: 按钮点击反馈
Buttons SHALL provide scale feedback when tapped.

#### Scenario: Button tap feedback
- **WHEN** a button is pressed
- **THEN** it MUST scale to `0.96`
- **AND** it MUST return to scale `1.0` on release

### Requirement: 性能优化
All animations SHALL use native drivers for smooth performance.

#### Scenario: Native driver usage
- **WHEN** an animation is configured
- **THEN** it MUST set `useNativeDriver: true`
- **AND** complex JavaScript-driven animations MUST be avoided on low-end devices
