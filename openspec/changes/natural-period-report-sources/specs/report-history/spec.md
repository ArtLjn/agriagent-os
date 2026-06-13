## MODIFIED Requirements

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
