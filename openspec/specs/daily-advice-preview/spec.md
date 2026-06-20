# daily-advice-preview Specification

## Purpose
TBD - created by archiving change compact-daily-advice-preview. Update Purpose after archive.
## Requirements
### Requirement: 首页显示紧凑预览卡片
`HomeScreen` SHALL 在经营态势卡下方展示 `AI 今日建议` 列表，最多显示 `DailyAdviceResponse.items` 的前三条 `compact` 信息，不显示完整详情字段。

#### Scenario: 有建议数据
- **WHEN** `GET /agent/daily` 返回 3 条 items
- **THEN** 首页显示 3 条建议，每条使用 `compact.icon`、`compact.title` 和 `compact.subtitle`

#### Scenario: 无建议数据
- **WHEN** `GET /agent/daily` 返回 empty 模式响应
- **THEN** 首页显示一条“暂无紧急建议”类 compact 建议，点击可进入详情页查看解释和可执行步骤

#### Scenario: 旧数据无 compact 字段
- **WHEN** 客户端收到旧格式 `{title, detail, priority, icon}`
- **THEN** 首页使用旧字段构造兼容 compact 展示，其中旧 `detail` 是字符串说明

### Requirement: 预览卡片点击进入详情页
点击首页任一 `AI 今日建议` 行 SHALL 导航到 `AdviceDetailScreen`，并传递同一接口响应中的 item 数据，不发起单条建议详情请求。

#### Scenario: 正常跳转
- **WHEN** 用户点击首页第一条建议箭头
- **THEN** App 导航到 `AdviceDetailScreen`，并传入 `DailyAdviceResponse.items[0]`

#### Scenario: 不二次请求
- **WHEN** 详情页由首页点击进入
- **THEN** 详情页 SHALL 直接使用传入 item 的 `detail_view` 渲染，不调用 `/agent/daily/items/{id}`

#### Scenario: 深层导航兜底
- **WHEN** 用户通过深层导航进入详情页但没有传入 item
- **THEN** 页面可调用 `GET /agent/daily` 获取当天响应，并默认展示第一条 item

### Requirement: 详情页展示完整建议列表
`AdviceDetailScreen` SHALL 展示单条建议的完整详情，包含顶部卡片、AI 判断依据、执行步骤、关联事项和底部动作。

#### Scenario: 展示单条建议详情
- **WHEN** 详情页收到一个包含 `detail_view` 的 item
- **THEN** 顶部卡片使用 `detail_view.title`、`detail_view.description` 和 `detail_view.hero_badges`，判断依据使用 `detail_view.evidence`，执行步骤使用 `detail_view.steps`

#### Scenario: 关联事项为空
- **WHEN** `detail_view.related` 为空数组
- **THEN** 详情页不显示空白关联事项列表，或显示“暂无关联事项”的轻量空状态

#### Scenario: 操作按钮
- **WHEN** `detail_view.actions` 包含 `create_work_order` 和 `ask_agent`
- **THEN** 底部区域展示“生成作业单”和“问问芽芽”两个操作入口

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

