## Context

当前 admin-web 技术栈：React 19 + Ant Design 5（暗色主题）+ Vite 8 + react-router-dom 7 + Axios。

现有 9 个页面全部面向农场业务 CRUD（作物、茬口、日志、成本等），与移动端功能重复。后端已建成 `/admin/*` 系列 API（trace 查询、Gantt timeline、token 统计、skill/prompt/config 管理），但前端完全没有对接。

需要将 admin-web 重新定位为**开发者调试控制台**，新增 6 个开发工具页面，侧边栏按"业务管理"和"开发调试"分组。

后端 API 消费关系：
- Trace Monitor → `GET /admin/traces` + `GET /admin/traces/{id}/timeline` + `GET /admin/traces/{id}/nodes/{nid}`
- Token Dashboard → `GET /admin/stats/tokens` + `GET /admin/stats/tokens/daily`
- Chat Playground → `POST /agent/chat/stream`（SSE）+ trace timeline（复用 Trace Monitor 组件）
- Skill Registry → `GET /admin/skills`
- Prompt Inspector → `GET /admin/prompts` + `GET /admin/prompts/{name}/render` + `POST /admin/prompts/reload`
- Config & Keys → `GET /admin/config` + `POST /admin/config/validate-key` + `POST /admin/cache/clear`

关键参考：product-agent 的 `monitor.html`（~700 行）实现了 Gantt 图链路可视化，交互模式可直接复用。

## Goals / Non-Goals

**Goals:**
- Trace 链路 Gantt 图可视化：按 round 分组，节点可点击查看 input/output
- Token 用量图表：日/月趋势、按模型分组、配额状态
- Chat Playground：直接与 Agent 对话 + 对话后自动展示 trace
- Skill/Prompt/Config 管理页面：列表、测试、热加载
- 侧边栏分组：业务管理 vs 开发调试

**Non-Goals:**
- 不改后端 API（全部消费现有/在建端点）
- 不做用户认证 UI（当前 farm_id=1 硬编码）
- 不做实时 WebSocket trace 推送（查询式即可）
- 不重写现有业务页面（保留原样）
- 不做移动端适配（admin-web 仅桌面使用）

## Decisions

### D1: 图表库选择

**选择：Ant Design Charts（@ant-design/charts）。**

备选方案：
- A) ECharts — 功能强大但包体大（~800KB），与 Ant Design 风格不统一
- B) Recharts — 轻量但需要手动样式调优
- C) 纯 CSS/DOM 绘制 Gantt — 工作量大，不划算

理由：项目已全面使用 Ant Design，@ant-design/charts 风格一致、API 简洁、按需加载可控。Token Dashboard 的折线图/柱状图用其 Line/Bar 组件即可。Gantt 图因其特殊性，使用 Ant Design Timeline + 自定义渲染（参考 product-agent monitor.html 的 SVG Gantt 方案）。

### D2: Gantt 图实现方式

**选择：自定义 React 组件 + CSS absolute positioning，不引入甘特图库。**

备选方案：
- A) dhtmlxGantt / frappe-gantt — 功能过重，引入额外依赖
- B) Ant Design Timeline — 垂直布局不适合展示耗时对比
- C) 纯 SVG（product-agent 方案）— React 中用 CSS 更方便维护

理由：Gantt 图需求简单（按 round 分组、水平条形图、点击查看详情），不需要拖拽/编辑等复杂交互。参考 monitor.html 的布局逻辑，用 CSS flexbox + absolute positioning 实现时间轴。数据量小（单次请求 5-15 节点），无需虚拟滚动。

组件结构：
```
<GanttTimeline>
  <RoundRow round_index={0}>
    <NodeBar node_type="prompt_render" start_ms={0} duration_ms={5} />
    <NodeBar node_type="llm_call" start_ms={5} duration_ms={800} />
    <NodeBar node_type="skill_call" start_ms={805} duration_ms={400} />
  </RoundRow>
</GanttTimeline>
```

### D3: Chat Playground 架构

**选择：扩展现有 Agent 页面的 Chat Tab 为独立 Playground 页面，新增 trace overlay。**

现有 Agent 页面已实现 SSE 流式对话（fetch + ReadableStream），Playground 在此基础上：
- 增加系统配置区（可选 model、temperature）
- 对话完成后自动调用 `/admin/traces/{request_id}/timeline` 获取 trace
- 在对话区下方展开内嵌 GanttTimeline 组件（可折叠）
- 从 SSE 响应头或 body 中提取 request_id 用于关联 trace

理由：复用已有 SSE 通信代码，不重复造轮子。Playground 和 Agent 页面的区别在于 Playground 关注可观测性（trace + metadata），Agent 页面关注用户体验。

### D4: API 层设计

**选择：新增 `src/api/admin.ts` 统一管理所有 `/admin/*` 端点调用。**

```typescript
// admin.ts
export const adminApi = {
  traces: {
    list: (params) => client.get('/admin/traces', { params }),
    timeline: (requestId) => client.get(`/admin/traces/${requestId}/timeline`),
    nodeDetail: (requestId, nodeId) => client.get(`/admin/traces/${requestId}/nodes/${nodeId}`),
    cleanup: (before) => client.delete('/admin/traces', { params: { before } }),
  },
  tokens: {
    summary: (params) => client.get('/admin/stats/tokens', { params }),
    daily: (params) => client.get('/admin/stats/tokens/daily', { params }),
  },
  skills: {
    list: () => client.get('/admin/skills'),
  },
  prompts: {
    list: () => client.get('/admin/prompts'),
    render: (name, variables) => client.get(`/admin/prompts/${name}/render`, { params: { variables } }),
    reload: () => client.post('/admin/prompts/reload'),
  },
  config: {
    get: () => client.get('/admin/config'),
    validateKey: (service) => client.post('/admin/config/validate-key`, null, { params: { service } }),
    clearCache: () => client.post('/admin/cache/clear'),
  },
};
```

理由：所有 admin API 集中管理，类型安全，方便后续扩展。复用现有 `client.ts` 的 Axios 实例和拦截器。

### D5: 路由结构

```
/admin/* 业务页面（保留）
  /                    → Dashboard（保留）
  /crops               → Crops（保留）
  /cycles              → Cycles（保留）
  /cycles/:id          → CycleDetail（保留）
  /logs                → Logs（保留）
  /costs               → Costs（保留）
  /weather             → Weather（保留）
  /api-tester          → ApiTester（保留）

/dev/* 开发调试页面（新增）
  /dev/traces          → Trace Monitor
  /dev/tokens          → Token Dashboard
  /dev/playground      → Chat Playground
  /dev/skills          → Skill Registry
  /dev/prompts         → Prompt Inspector
  /dev/config          → Config & Keys
```

侧边栏分为两个 Menu Group：
- **业务管理**：Dashboard、作物模板、茬口管理、农事日志、成本记账、天气预报、API 测试
- **开发调试**：链路追踪、Token 看板、Playground、Skill 注册表、Prompt 检查器、配置管理

### D6: 节点类型颜色编码

统一节点类型颜色方案（与 Gantt 图和 trace 列表共用）：

| node_type | 颜色 | 说明 |
|-----------|------|------|
| prompt_render | 蓝色 (#1890ff) | Prompt 渲染 |
| llm_call | 紫色 (#722ed1) | LLM 调用 |
| skill_call | 绿色 (#52c41a) | Skill 执行 |
| error | 红色 (#ff4d4f) | 错误节点 |

## Risks / Trade-offs

- **[Gantt 图性能]** → 单次请求节点数 5-15 个，CSS 渲染无压力。极端情况（复杂多轮对话 50+ 节点）加虚拟滚动，暂不需要
- **[Playground trace 关联]** → 需要从 SSE 响应中提取 request_id，若后端 SSE 不返回该字段则需要额外 API 查询"最近 trace"，增加 1 次网络请求
- **[图表库包体]** → @ant-design/charts 基于 G2，按需引入。Token Dashboard 只需 Line + Bar，gzip 后约 100KB
- **[现有页面不受影响]** → 所有新增页面在 `/dev/*` 路由下，侧边栏分组明确，不改动现有业务页面代码
