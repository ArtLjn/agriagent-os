## Purpose

定义 ai-chat-ui-upgrade 能力的行为要求。

## Requirements

### Requirement: 页面背景
The AI chat screen SHALL use a gradient background instead of pure white.

#### Scenario: Chat background
- **WHEN** the AI chat screen is rendered
- **THEN** its background MUST use the gradient from `#F7FAFF` to `#FFFFFF`

### Requirement: 顶部标题栏
The chat header SHALL display the AI assistant name with an online status indicator.

#### Scenario: Header title
- **WHEN** the chat header is rendered
- **THEN** it MUST display "AI 农事助手"
- **AND** it MUST show an online status indicator with color `#3BB273`

### Requirement: AI 头像
The AI avatar SHALL be a distinctive rounded black sphere with eyes.

#### Scenario: AI avatar appearance
- **WHEN** the AI avatar is rendered
- **THEN** it MUST be a rounded black sphere with simple eyes
- **AND** it MUST resemble a friendly assistant character

### Requirement: AI 回复卡片
AI message bubbles SHALL use white cards with subtle borders.

#### Scenario: AI message card
- **WHEN** an AI message is displayed
- **THEN** its background MUST be `#FFFFFF`
- **AND** it MUST have `border: 1px solid #EEF2F7`

### Requirement: 用户气泡
User message bubbles SHALL use a blue-purple gradient.

#### Scenario: User message bubble
- **WHEN** a user message is displayed
- **THEN** its background MUST use the gradient from `#5B8CFF` to `#7A7DFF` at 135 degrees
- **AND** the text MUST be white

### Requirement: 输入框
The chat input field SHALL use a light background with large border radius.

#### Scenario: Input field appearance
- **WHEN** the input field is rendered
- **THEN** its background MUST be `#F3F6FB`
- **AND** its border radius MUST be `24px`

### Requirement: 发送按钮
The send button SHALL use a blue-purple gradient.

#### Scenario: Send button appearance
- **WHEN** the send button is rendered
- **THEN** its background MUST use the gradient from `#5B8CFF` to `#7A7DFF` at 135 degrees

### Requirement: 推荐问题胶囊
The chat screen SHALL display recommended questions as capsule-shaped chips at the top.

#### Scenario: Recommended questions
- **WHEN** the chat screen is opened
- **THEN** it MUST display capsule chips with suggested questions such as "帮我规划秋种", "今天适合施肥吗", "未来一周天气"
- **AND** tapping a chip MUST send that question to the AI
