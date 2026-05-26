## Why

当前 admin-web 是用户面向的 CRUD 管理后台（作物/茬口/日志/成本），与移动端功能高度重复。后端已建成完整的 Admin Trace API（链路追踪、Token 计量、Skill/Prompt/Config 管理）但前端完全没有对接——开发者调试只能看日志和 curl，无法可视化 Agent 执行链路。

需要将 admin-web 重新定位为**开发者调试控制台**，聚焦 Agent 可观测性：链路追踪 Gantt 图、Token 用量看板、Chat Playground、Skill/Prompt 检查器、运行时配置管理。

## What Changes

- 新增 **Trace Monitor 页**：Gantt 时间线图（按 round 分组展示 LLM/Skill/Prompt 节点），节点可点击查看完整 input/output
- 新增 **Token Dashboard 页**：日/月 Token 用量图表、按模型分组统计、配额状态指示器
- 新增 **Chat Playground 页**：可直接在 admin-web 与 Agent 对话（SSE 流式），对话完成后自动展示该请求的 trace 时间线
- 新增 **Skill Registry 页**：展示所有注册 Skill 的名称/描述/参数 schema/状态，支持在线测试
- 新增 **Prompt Inspector 页**：列出所有 prompt 模板、渲染预览、一键热加载
- 新增 **Config & Keys 页**：运行时配置查看（key 脱敏）、API key 连通性测试、缓存清空
- 保留现有业务页面（Dashboard/Crops/Cycles/Logs/Costs/Weather/ApiTester），侧边栏重组为"业务管理"和"开发调试"两个分组
- 新增前端 API 层（`src/api/admin.ts`、`src/api/trace.ts`）对接后端 `/admin/*` 端点

## Capabilities

### New Capabilities
- `trace-monitor-ui`: Trace 链路监控前端——Gantt 时间线可视化、节点详情查看、trace 列表查询筛选
- `token-dashboard-ui`: Token 用量看板前端——用量图表、按模型/日期分组、配额状态
- `chat-playground-ui`: Chat Playground 前端——SSE 流式对话、对话完成后内嵌 trace 时间线、历史会话查看
- `admin-tooling-ui`: Admin 工具前端——Skill 列表/测试、Prompt 模板检查/热加载、Config 查看/Key 验证/缓存管理

### Modified Capabilities
- (无 spec 级别变更，现有业务页面保持不变)

## Impact

- **前端代码**：`admin-web/src/` 新增 6 个页面组件、2 个 API 模块、1 个 Gantt 图组件、侧边栏布局调整
- **后端 API**：完全消费 `admin-trace-system` change 已定义的 API 端点，无后端改动
- **依赖**：可能新增图表库（Ant Design Charts 或 ECharts，用于 Token Dashboard 图表）
- **构建**：`admin-web/` 构建产物增大，但不影响移动端
