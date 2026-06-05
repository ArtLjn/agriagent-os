# daily-advice-preview Specification

## Purpose
TBD - created by archiving change compact-daily-advice-preview. Update Purpose after archive.
## Requirements
### Requirement: 首页显示紧凑预览卡片
`HomeScreen` SHALL 在 `WeatherCardV2` 下方展示 `CompactAdviceCard`，高度不超过 110px，不显示完整建议列表。

#### Scenario: 有建议数据
- **WHEN** `dailyAdvice` 返回 `{preview: "今日有雨，注意防涝", items: [...]}`
- **THEN** 首页显示预览卡片，左侧灵宠 Emoji，右侧显示 "今日有雨，注意防涝" 和 "3 条农事建议"

#### Scenario: 无建议数据
- **WHEN** `dailyAdvice` 为 null 或 items 为空
- **THEN** 预览卡片显示 "暂无今日建议"，点击无反应或提示稍后重试

#### Scenario: 旧数据无 preview 字段
- **WHEN** `dailyAdvice.preview` 为空字符串
- **THEN** 预览卡片根据 `weatherCondition` 显示默认文案（如 "天气晴好，适合农作"）

### Requirement: 预览卡片点击进入详情页
点击 `CompactAdviceCard` SHALL 导航到 `AdviceDetailScreen`。

#### Scenario: 正常跳转
- **WHEN** 用户点击预览卡片
- **THEN** 导航到 `AdviceDetailScreen`，传递 `items`、`preview`、`weatherCondition` 参数

#### Scenario: 详情页数据加载
- **WHEN** 用户通过外部链接或深层导航进入 `AdviceDetailScreen` 无参数
- **THEN** 页面内部调用 `fetchDailyAdvice()` 获取数据，避免空白页

### Requirement: 详情页展示完整建议列表
`AdviceDetailScreen` SHALL 展示所有建议条目，包含天气氛围 Header 和建议列表。

#### Scenario: 展示多条建议
- **WHEN** `items` 有 3 条建议
- **THEN** 详情页显示 Header（灵宠 + preview + 日期）和 3 条建议卡片，按 priority 排序

#### Scenario: 建议条目展示
- **WHEN** 展示单条建议 `{title: "关风口", detail: "明早12°", priority: 1, icon: "🌡️"}`
- **THEN** 显示红色优先级竖条、标题 "关风口"、详情 "明早12°"、右侧 Emoji "🌡️"

#### Scenario: 空状态
- **WHEN** `items` 为空数组
- **THEN** 详情页显示 "暂无今日建议" 插图和 "咨询顾问" 按钮

### Requirement: 详情页底部咨询入口
`AdviceDetailScreen` SHALL 在底部提供跳转到 `AgentChatScreen` 的入口。

#### Scenario: 点击咨询
- **WHEN** 用户点击底部 "咨询农事顾问" 按钮
- **THEN** 导航到 `AgentChatScreen`

### Requirement: 灵宠 Emoji 根据天气状态变化
灵宠 Emoji SHALL 根据 `weatherCondition` 显示不同表情和背景色。

#### Scenario: 晴天
- **WHEN** `weatherCondition` 为 "sunny"
- **THEN** 显示 🌾，背景色 `#FDF6E3`

#### Scenario: 雨天
- **WHEN** `weatherCondition` 为 "rainy"
- **THEN** 显示 🌧️，背景色 `#E8F1FF`

#### Scenario: 雾天
- **WHEN** `weatherCondition` 为 "foggy"
- **THEN** 显示 🌫️，背景色 `#F0F4F8`

#### Scenario: 寒冷
- **WHEN** `weatherCondition` 为 "cold"
- **THEN** 显示 ❄️，背景色 `#E8F4FF`

