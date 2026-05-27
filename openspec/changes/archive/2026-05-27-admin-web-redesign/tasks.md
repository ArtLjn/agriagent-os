## 1. 基础设施：API 层 + 路由 + 布局

- [ ] 1.1 创建 `src/api/admin.ts` — 封装所有 `/admin/*` 端点调用（traces/tokens/skills/prompts/config），复用现有 client.ts Axios 实例
- [ ] 1.2 安装 `@ant-design/charts` 依赖
- [ ] 1.3 修改 `src/App.tsx` — 新增 `/dev/*` 路由（/dev/traces, /dev/tokens, /dev/playground, /dev/skills, /dev/prompts, /dev/config）
- [ ] 1.4 修改 `src/layouts/AdminLayout.tsx` — 侧边栏分为"业务管理"和"开发调试"两个 Menu.ItemGroup，开发调试组包含 6 个新页面链接
- [ ] 1.5 定义节点类型颜色常量 — 创建 `src/constants/trace.ts`，导出 NODE_TYPE_COLORS（prompt_render=#1890ff, llm_call=#722ed1, skill_call=#52c41a, error=#ff4d4f）

## 2. GanttTimeline 通用组件

- [ ] 2.1 创建 `src/components/GanttTimeline/index.tsx` — 接收 timeline 数据（rounds + nodes），按 round 分行渲染
- [ ] 2.2 实现 RoundRow 子组件 — 每轮一行，左侧标签 `Round 0`/`Round 1`，右侧水平条形图区域
- [ ] 2.3 实现 NodeBar 子组件 — 接收 node_type/start_ms/duration_ms/status，用 CSS absolute positioning 渲染条形，颜色按 NODE_TYPE_COLORS 映射
- [ ] 2.4 实现 Tooltip 悬停效果 — 鼠标悬停显示 node_name + duration_ms + status
- [ ] 2.5 实现节点点击回调 — 点击 NodeBar 触发 `onNodeClick(node)` 回调，供父组件打开 Drawer

## 3. Trace Monitor 页面

- [ ] 3.1 创建 `src/pages/TraceMonitor/index.tsx` — 顶部搜索筛选区（request_id/session_id/farm_id 输入框 + 查询按钮）
- [ ] 3.2 实现 trace 列表表格 — 列：request_id（前 8 位）、farm_id、节点数、总耗时、创建时间，点击行展开 GanttTimeline
- [ ] 3.3 实现内嵌 GanttTimeline — 点击 trace 行后，在行下方展开 GanttTimeline 组件展示 timeline 数据
- [ ] 3.4 实现节点详情 Drawer — 点击 Gantt 节点后右侧打开 Drawer，调用 nodeDetail API 展示完整 input/output JSON
- [ ] 3.5 实现清理操作 — 底部"清理历史"按钮，日期选择器 + 确认弹窗，调用 DELETE /admin/traces

## 4. Token Dashboard 页面

- [ ] 4.1 创建 `src/pages/TokenDashboard/index.tsx` — 顶部 4 个统计卡片（总 tokens、总请求数、今日用量、配额剩余）
- [ ] 4.2 实现配额进度条 — 根据用量/配额比例渲染进度条，颜色：绿(<80%) / 橙(80-100%) / 红(>=100%)
- [ ] 4.3 实现趋势折线图 — 使用 @ant-design/charts Line 组件，X 轴日期，Y 轴 total_tokens，支持切换 7 天/30 天
- [ ] 4.4 实现模型分组柱状图 — 使用 @ant-design/charts Bar 组件，按模型分组展示 prompt_tokens + completion_tokens
- [ ] 4.5 实现明细表格 — 点击折线图某天后下方展示该天明细（模型、调用类型、tokens、请求数）

## 5. Chat Playground 页面

- [ ] 5.1 创建 `src/pages/Playground/index.tsx` — 左右布局：左侧参数配置面板（farm_id/session_id 输入），右侧对话区
- [ ] 5.2 实现对话功能 — 复用现有 Agent 页面的 SSE 流式对话逻辑（fetch + ReadableStream），支持 Markdown 渲染
- [ ] 5.3 实现清空对话按钮 — 清空消息列表，重新生成 session_id
- [ ] 5.4 实现 trace overlay — AI 回复完成后，自动调用 timeline API，在消息下方展开可折叠的 GanttTimeline 组件
- [ ] 5.5 处理 trace 不可用情况 — timeline 为空时显示"暂无执行链路数据"提示

## 6. Skill Registry 页面

- [ ] 6.1 创建 `src/pages/SkillRegistry/index.tsx` — 调用 GET /admin/skills，以卡片网格展示 Skill 列表
- [ ] 6.2 实现 Skill 卡片 — 展示 name、description、status 标签，点击展开 parameters_schema JSON
- [ ] 6.3 实现 schema JSON 格式化展示 — 使用 Ant Design Collapse 或 Modal 展示完整 JSON Schema

## 7. Prompt Inspector 页面

- [ ] 7.1 创建 `src/pages/PromptInspector/index.tsx` — 调用 GET /admin/prompts，表格展示模板列表（name/version/active/source）
- [ ] 7.2 实现渲染预览功能 — 点击"渲染预览"弹出 Modal，输入变量值，调用 render API 展示渲染结果
- [ ] 7.3 实现热加载按钮 — "重新加载模板"按钮，调用 POST /admin/prompts/reload，显示结果提示

## 8. Config & Keys 页面

- [ ] 8.1 创建 `src/pages/ConfigKeys/index.tsx` — 调用 GET /admin/config，JSON 树展示配置（API key 脱敏）
- [ ] 8.2 实现 Key 验证按钮 — 每个服务旁显示"验证"按钮，调用 validate-key API，展示结果（有效/无效 + 延迟）
- [ ] 8.3 实现清空缓存按钮 — "清空缓存"按钮 + 确认弹窗，调用 POST /admin/cache/clear

## 9. 端到端验证

- [ ] 9.1 验证 Trace Monitor：发送对话后，/dev/traces 页面出现新 trace 记录，点击可查看 Gantt 图和节点详情
- [ ] 9.2 验证 Token Dashboard：对话后 /dev/tokens 页面更新统计数据和图表
- [ ] 9.3 验证 Playground：在 /dev/playground 发送消息，AI 流式回复，回复完成后自动展示 trace 时间线
- [ ] 9.4 验证 Skill Registry：/dev/skills 页面展示所有已注册 Skill 的名称和 schema
- [ ] 9.5 验证 Prompt Inspector：渲染预览可正常展示 prompt，热加载按钮生效
- [ ] 9.6 验证 Config & Keys：配置展示 key 脱敏，验证按钮显示连通性结果
- [ ] 9.7 验证侧边栏分组：业务管理和开发调试两组正确展示，路由导航正常
- [ ] 9.8 运行 `cd admin-web && npm run build` 确保构建通过
