## Purpose

定义 report-history 能力的行为要求。

## Requirements

### Requirement: AI 助手 Tab 包含对话和报告两个视图
AgentChatScreen SHALL 在 header 下方提供 SegmentedControl（对话/报告），点击切换显示内容。默认选中"对话"视图。

#### Scenario: 默认显示对话视图
- **WHEN** 用户进入 AI 助手 Tab
- **THEN** SegmentedControl 默认选中"对话"，显示现有聊天界面

#### Scenario: 切换到报告视图
- **WHEN** 用户点击 SegmentedControl 的"报告"
- **THEN** 显示报告视图：顶部"生成新报告"按钮 + 历史报告列表

#### Scenario: 切换回对话视图
- **WHEN** 用户从报告视图切回对话视图
- **THEN** 对话消息和输入框状态完整保留

### Requirement: 报告视图包含生成入口和历史列表
报告视图 SHALL 在顶部提供"生成新报告"按钮（周报/月报切换），下方显示历史报告列表，按时间倒序排列。

#### Scenario: 生成新报告
- **WHEN** 用户在报告视图点击"生成新报告"
- **THEN** 弹出选择器（周报/月报），确认后调用后端生成，完成后列表自动刷新

#### Scenario: 查看历史报告
- **WHEN** 用户点击历史列表中的某条报告
- **THEN** 跳转到报告详情页，使用 MarkdownText 渲染内容

#### Scenario: 无历史报告
- **WHEN** 用户进入报告视图且无历史记录
- **THEN** 显示空状态提示"暂无报告，点击上方按钮生成第一份报告"

### Requirement: 报告详情页使用 Markdown 渲染
AgentReportScreen（报告详情页）SHALL 优先使用报告 `structured_data` 渲染结构化报告内容；当 `structured_data` 缺失或前端尚未支持对应 section 时，SHALL fallback 使用 `MarkdownText` 组件渲染报告 `content`。

#### Scenario: 报告包含结构化数据
- **WHEN** 报告详情记录包含 `structured_data.sections`
- **THEN** 前端 SHALL 优先使用结构化数据渲染报告详情
- **AND** 不依赖 Markdown 解析来展示主要报告模块

#### Scenario: 报告仅包含 Markdown 内容
- **WHEN** 历史报告缺少 `structured_data`
- **THEN** 前端 SHALL 使用 `MarkdownText` 渲染 `content`

#### Scenario: 报告包含 Markdown 格式
- **WHEN** 报告 content 包含标题、列表、粗体等 Markdown 语法
- **THEN** fallback 渲染 SHALL 正确显示为格式化文本

### Requirement: 后端报告历史列表接口
后端 SHALL 提供 `GET /agent/reports` 接口，返回当前 farm_id 下所有报告记录，按创建时间倒序，支持分页。返回项 SHALL 包含 id、report_type、created_at、content 摘要，并在存在时包含 `structured_data`。

#### Scenario: 获取报告列表
- **WHEN** 请求 `GET /agent/reports?page=1&size=10`
- **THEN** 返回报告列表，每条包含 id、report_type、created_at、content 摘要
- **AND** 对于新结构化报告，返回项 SHALL 包含 `structured_data`

#### Scenario: 无报告记录
- **WHEN** 请求 `GET /agent/reports` 且 farm_id 下无报告
- **THEN** 返回空列表 `{"items": [], "total": 0}`

#### Scenario: 旧报告兼容
- **WHEN** 历史报告记录没有结构化元数据
- **THEN** 返回项 SHALL 保留 `structured_data=null`
- **AND** 返回项 SHALL 继续包含可渲染的 `content`
