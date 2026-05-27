## ADDED Requirements

### Requirement: Chat Playground 对话界面
系统 SHALL 提供 `/dev/playground` 页面，支持直接在 admin-web 与 Agent 进行 SSE 流式对话。

#### Scenario: 发送消息
- **WHEN** 用户在输入框输入消息并发送
- **THEN** 调用 `POST /agent/chat/stream`（SSE），逐 token 流式展示 AI 回复（复用现有 SSE 逻辑）

#### Scenario: 对话历史展示
- **WHEN** Playground 页面有多轮对话
- **THEN** 消息列表按时间顺序展示，用户消息和 AI 回复样式区分，AI 回复支持 Markdown 渲染

#### Scenario: 清空对话
- **WHEN** 用户点击"清空对话"按钮
- **THEN** 清空当前消息列表和 session_id，生成新的 session_id

### Requirement: 对话完成后展示 Trace 时间线
系统 SHALL 在每次 AI 回复完成后，自动获取并展示该请求的 trace 时间线。

#### Scenario: 回复完成后自动加载 trace
- **WHEN** SSE 流结束，AI 回复完成
- **THEN** 自动调用 `GET /admin/traces?request_id={id}/timeline`，在消息下方展开可折叠的 Gantt 时间线（复用 trace-monitor-ui 的 GanttTimeline 组件）

#### Scenario: Trace 加载中
- **WHEN** 正在获取 trace 数据
- **THEN** 在消息下方显示 loading spinner + "正在加载执行链路..."

#### Scenario: Trace 不可用
- **WHEN** trace 数据为空（后端 trace 系统未启用或数据未写入）
- **THEN** 显示提示"暂无执行链路数据"

### Requirement: Playground 参数配置
系统 SHALL 在 Playground 页面提供对话参数配置区域。

#### Scenario: 选择 farm_id
- **WHEN** 用户在配置区选择 farm_id
- **THEN** 后续对话请求使用该 farm_id

#### Scenario: 输入 session_id
- **WHEN** 用户输入自定义 session_id
- **THEN** 后续对话使用该 session_id（方便复现特定会话）
