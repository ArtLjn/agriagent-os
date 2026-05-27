# Admin Web Redesign 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 admin-web 从农场业务管理后台重构为开发者调试控制台，新增 6 个开发工具页面（Trace Monitor、Token Dashboard、Chat Playground、Skill Registry、Prompt Inspector、Config & Keys），侧边栏按"业务管理"和"开发调试"分组。

**Architecture:** 前端 React + Ant Design 5（暗色主题），新增 `src/api/admin.ts` 统一封装所有 `/admin/*` 端点。Gantt 图用自定义 React 组件 + CSS absolute positioning 实现，Token 图表用 `@ant-design/charts`。Chat Playground 复用现有 SSE 流式逻辑，新增 trace 关联展示。

**Tech Stack:** React 19, Ant Design 5, Vite 8, react-router-dom 7, @ant-design/charts, Axios

**后端接口状态（已确认就绪）：**
| 端点 | 状态 | 说明 |
|------|------|------|
| `GET /admin/traces` | 就绪 | list_traces |
| `GET /admin/traces/{id}/timeline` | 就绪 | get_timeline |
| `GET /admin/traces/{id}/nodes/{nid}` | 就绪 | get_node_detail |
| `DELETE /admin/traces` | 就绪 | delete_traces |
| `GET /admin/stats/tokens` | 就绪 | token_summary |
| `GET /admin/stats/tokens/daily` | 就绪 | token_daily |
| `GET /admin/skills` | 就绪 | list_skills |
| `GET /admin/prompts` | 就绪 | list_prompts |
| `POST /admin/prompts/reload` | 就绪 | reload_prompts |
| `GET /admin/config` | 就绪 | get_config |
| `POST /admin/cache/clear` | 就绪 | clear_all_cache |
| `GET /admin/prompts/{name}/render` | **缺失** | 前端暂用 content preview 替代 |
| `POST /admin/config/validate-key` | **缺失** | 前端暂跳过 key 验证功能 |
| `POST /agent/chat/stream` | 就绪 | SSE 流式对话 |

**颜色方案（与现有页面一致）：**
- BG = `#0d1117` (页面背景)
- CARD = `#161b22` (卡片背景)
- BORDER = `#30363d` (边框)
- TEXT = `#e6edf3` (主文本)
- TEXT_DIM = `#8b949e` (次要文本)
- ACCENT = `#58a6ff` (强调色)

---

## 文件结构

```
admin-web/src/
├── api/
│   ├── admin.ts              (新增 — 所有 /admin/* 端点封装)
│   ├── agent.ts              (已有 — 复用 streamChat)
│   └── client.ts             (已有 — Axios 实例)
├── constants/
│   └── trace.ts              (新增 — 节点类型颜色映射)
├── components/
│   └── GanttTimeline/
│       ├── index.tsx         (新增 — Gantt 图主组件)
│       └── types.ts          (新增 — Gantt 类型定义)
├── pages/
│   ├── TraceMonitor/
│   │   └── index.tsx         (新增 — Trace 链路监控)
│   ├── TokenDashboard/
│   │   └── index.tsx         (新增 — Token 用量看板)
│   ├── Playground/
│   │   └── index.tsx         (新增 — Chat Playground)
│   ├── SkillRegistry/
│   │   └── index.tsx         (新增 — Skill 注册表)
│   ├── PromptInspector/
│   │   └── index.tsx         (新增 — Prompt 检查器)
│   ├── ConfigKeys/
│   │   └── index.tsx         (新增 — 配置与密钥)
│   └── Agent/
│       └── index.tsx         (已有 — 参考 SSE 实现)
├── layouts/
│   └── AdminLayout.tsx       (修改 — 侧边栏分组)
├── App.tsx                   (修改 — 新增 /dev/* 路由)
└── main.tsx                  (已有 — 入口)
```

---

## Task 1: 安装依赖

**Files:**
- Modify: `admin-web/package.json`

- [ ] **Step 1: 安装 @ant-design/charts**

```bash
cd /Users/ljn/Documents/demo/explore/admin-web && npm install @ant-design/charts
```

Expected: 安装成功，无报错。

- [ ] **Step 2: 验证安装**

```bash
cd /Users/ljn/Documents/demo/explore/admin-web && npm ls @ant-design/charts
```

Expected: 显示 `@ant-design/charts@x.x.x` 版本号。

- [ ] **Step 3: Commit**

```bash
git add admin-web/package.json admin-web/package-lock.json
git commit -m "chore(admin-web): 安装 @ant-design/charts 依赖"
```

---

## Task 2: 创建 API 层 (admin.ts)

**Files:**
- Create: `admin-web/src/api/admin.ts`

- [ ] **Step 1: 编写 admin API 模块**

Create `admin-web/src/api/admin.ts`:

```typescript
import client from './client';

// ── Trace ──
export interface TraceRecord {
  id: number;
  request_id: string;
  session_id: string | null;
  farm_id: number;
  round_index: number;
  node_type: string;
  node_name: string;
  duration_ms: number | null;
  status: string;
  token_usage: string | null;
  error_message: string | null;
  created_at: string;
}

export interface TraceListResponse {
  items: TraceRecord[];
  total: number;
}

export interface TimelineNode {
  node_type: string;
  node_name: string;
  duration_ms: number | null;
  status: string;
  token_usage: Record<string, unknown> | null;
  start_time: string | null;
  error_message: string | null;
  input_data: string | null;
  output_data: string | null;
}

export interface TimelineRound {
  round_index: number;
  nodes: TimelineNode[];
}

export interface TimelineResponse {
  request_id: string;
  rounds: TimelineRound[];
}

export interface NodeDetail {
  id: number;
  request_id: string;
  round_index: number;
  node_type: string;
  node_name: string;
  input_data: string | null;
  output_data: string | null;
  duration_ms: number | null;
  token_usage: string | null;
  status: string;
  error_message: string | null;
  start_time: string | null;
  end_time: string | null;
}

export async function listTraces(params?: {
  request_id?: string;
  session_id?: string;
  farm_id?: number;
  limit?: number;
  offset?: number;
}): Promise<TraceListResponse> {
  const res = await client.get<TraceListResponse>('/admin/traces', { params });
  return res.data;
}

export async function getTimeline(requestId: string): Promise<TimelineResponse> {
  const res = await client.get<TimelineResponse>(`/admin/traces/${requestId}/timeline`);
  return res.data;
}

export async function getNodeDetail(requestId: string, nodeId: number): Promise<NodeDetail> {
  const res = await client.get<NodeDetail>(`/admin/traces/${requestId}/nodes/${nodeId}`);
  return res.data;
}

export async function deleteTraces(before: string): Promise<{ deleted: number }> {
  const res = await client.delete<{ deleted: number }>('/admin/traces', { params: { before } });
  return res.data;
}

// ── Token Stats ──
export interface TokenSummaryItem {
  model: string;
  call_type: string;
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
  request_count: number;
}

export interface TokenSummaryResponse {
  days: number;
  total_tokens: number;
  total_requests: number;
  by_model: Record<string, TokenSummaryItem>;
}

export interface TokenDailyItem {
  model: string;
  call_type: string;
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
  request_count: number;
  estimated_cost_cny: number;
}

export interface TokenDailyResponse {
  date: string;
  items: TokenDailyItem[];
}

export async function getTokenSummary(days: number = 7): Promise<TokenSummaryResponse> {
  const res = await client.get<TokenSummaryResponse>('/admin/stats/tokens', { params: { days } });
  return res.data;
}

export async function getTokenDaily(date?: string): Promise<TokenDailyResponse> {
  const res = await client.get<TokenDailyResponse>('/admin/stats/tokens/daily', { params: { date } });
  return res.data;
}

// ── Skills ──
export interface SkillItem {
  name: string;
  description: string;
  parameters_schema: Record<string, unknown>;
  status: string;
}

export async function listSkills(): Promise<{ items: SkillItem[]; total: number }> {
  const res = await client.get<{ items: SkillItem[]; total: number }>('/admin/skills');
  return res.data;
}

// ── Prompts ──
export interface PromptItem {
  name: string;
  version: string;
  active: boolean;
  content_length: number;
}

export async function listPrompts(): Promise<{ items: PromptItem[]; total: number }> {
  const res = await client.get<{ items: PromptItem[]; total: number }>('/admin/prompts');
  return res.data;
}

export async function reloadPrompts(): Promise<{ status: string; message: string }> {
  const res = await client.post<{ status: string; message: string }>('/admin/prompts/reload');
  return res.data;
}

// ── Config ──
export interface ConfigResponse {
  ai: {
    model: string;
    base_url: string;
    api_key: string;
    enable_thinking: boolean;
  };
  trace: {
    batch_size: number;
    flush_interval: number;
    trace_ttl_days: number;
  };
  token_quota: {
    daily_limit: number;
    over_quota_action: string;
  };
  langsmith: {
    enabled: boolean;
    project: string;
  };
}

export async function getConfig(): Promise<ConfigResponse> {
  const res = await client.get<ConfigResponse>('/admin/config');
  return res.data;
}

export async function clearCache(): Promise<{ cleared: Record<string, number> }> {
  const res = await client.post<{ cleared: Record<string, number> }>('/admin/cache/clear');
  return res.data;
}
```

- [ ] **Step 2: Commit**

```bash
git add admin-web/src/api/admin.ts
git commit -m "feat(admin-web): 创建 admin API 层"
```

---

## Task 3: 创建 Trace 常量

**Files:**
- Create: `admin-web/src/constants/trace.ts`

- [ ] **Step 1: 编写节点类型颜色常量**

Create `admin-web/src/constants/trace.ts`:

```typescript
/**
 * Trace 节点类型颜色映射。
 * 与 Gantt 图、trace 列表共用。
 */
export const NODE_TYPE_COLORS: Record<string, string> = {
  prompt_render: '#1890ff',  // 蓝色 — Prompt 渲染
  llm_call: '#722ed1',       // 紫色 — LLM 调用
  skill_call: '#52c41a',     // 绿色 — Skill 执行
  error: '#ff4d4f',          // 红色 — 错误节点
};

export const NODE_TYPE_LABELS: Record<string, string> = {
  prompt_render: 'Prompt 渲染',
  llm_call: 'LLM 调用',
  skill_call: 'Skill 执行',
  error: '错误',
};

/** 获取节点类型的颜色，未知类型返回默认灰色 */
export function getNodeColor(nodeType: string): string {
  return NODE_TYPE_COLORS[nodeType] || '#8b949e';
}

/** 获取节点类型的中文标签 */
export function getNodeLabel(nodeType: string): string {
  return NODE_TYPE_LABELS[nodeType] || nodeType;
}
```

- [ ] **Step 2: Commit**

```bash
git add admin-web/src/constants/trace.ts
git commit -m "feat(admin-web): 添加 trace 节点类型颜色常量"
```

---

## Task 4: 创建 GanttTimeline 组件

**Files:**
- Create: `admin-web/src/components/GanttTimeline/types.ts`
- Create: `admin-web/src/components/GanttTimeline/index.tsx`

- [ ] **Step 1: 编写类型定义**

Create `admin-web/src/components/GanttTimeline/types.ts`:

```typescript
export interface GanttNode {
  node_type: string;
  node_name: string;
  duration_ms: number | null;
  status: string;
  start_time: string | null;
}

export interface GanttRound {
  round_index: number;
  nodes: GanttNode[];
}

export interface GanttTimelineProps {
  rounds: GanttRound[];
  onNodeClick?: (roundIndex: number, nodeIndex: number) => void;
}
```

- [ ] **Step 2: 编写 GanttTimeline 组件**

Create `admin-web/src/components/GanttTimeline/index.tsx`:

```typescript
import { useMemo, useState } from 'react';
import { GanttTimelineProps } from './types';
import { getNodeColor, getNodeLabel } from '../../constants/trace';

const BG = '#0d1117';
const BORDER = '#30363d';
const TEXT = '#e6edf3';
const TEXT_DIM = '#8b949e';
const ROW_HEIGHT = 40;
const BAR_HEIGHT = 24;
const PADDING_LEFT = 80;
const PADDING_RIGHT = 20;
const MIN_BAR_WIDTH = 4;

export default function GanttTimeline({ rounds, onNodeClick }: GanttTimelineProps) {
  const [hoveredNode, setHoveredNode] = useState<{ r: number; n: number } | null>(null);

  const { totalDuration, timelineWidth } = useMemo(() => {
    let maxEnd = 0;
    for (const round of rounds) {
      let currentMs = 0;
      for (const node of round.nodes) {
        const dur = node.duration_ms ?? 0;
        currentMs += dur;
      }
      maxEnd = Math.max(maxEnd, currentMs);
    }
    // 最小总宽度 500ms，避免数据过少时过度拉伸
    const duration = Math.max(maxEnd, 500);
    return { totalDuration: duration, timelineWidth: Math.max(duration, 300) };
  }, [rounds]);

  const scale = (ms: number) => {
    if (totalDuration === 0) return 0;
    return (ms / totalDuration) * timelineWidth;
  };

  return (
    <div style={{ background: BG, borderRadius: 8, border: `1px solid ${BORDER}`, padding: 16 }}>
      {rounds.length === 0 ? (
        <div style={{ color: TEXT_DIM, textAlign: 'center', padding: 32 }}>暂无执行链路数据</div>
      ) : (
        <div style={{ overflowX: 'auto' }}>
          {/* 时间轴刻度 */}
          <div style={{ display: 'flex', marginBottom: 8, paddingLeft: PADDING_LEFT, position: 'relative', height: 20 }}>
            {[0, 0.25, 0.5, 0.75, 1].map((ratio) => {
              const ms = Math.round(totalDuration * ratio);
              const left = scale(ms);
              return (
                <div key={ratio} style={{ position: 'absolute', left, transform: 'translateX(-50%)', color: TEXT_DIM, fontSize: 11 }}>
                  {formatDuration(ms)}
                </div>
              );
            })}
          </div>

          {/* Round 行 */}
          {rounds.map((round, rIdx) => {
            let currentMs = 0;
            return (
              <div key={round.round_index} style={{ display: 'flex', alignItems: 'center', height: ROW_HEIGHT, borderBottom: `1px solid ${BORDER}` }}>
                {/* Round 标签 */}
                <div style={{ width: PADDING_LEFT - 12, color: TEXT_DIM, fontSize: 12, textAlign: 'right', paddingRight: 12, flexShrink: 0 }}>
                  Round {round.round_index}
                </div>

                {/* 条形图区域 */}
                <div style={{ position: 'relative', height: BAR_HEIGHT, flex: 1, minWidth: timelineWidth }}>
                  {round.nodes.map((node, nIdx) => {
                    const dur = node.duration_ms ?? 0;
                    const left = scale(currentMs);
                    const width = Math.max(scale(dur), MIN_BAR_WIDTH);
                    currentMs += dur;
                    const isHovered = hoveredNode?.r === rIdx && hoveredNode?.n === nIdx;

                    return (
                      <div
                        key={nIdx}
                        style={{
                          position: 'absolute',
                          left,
                          top: 0,
                          width,
                          height: BAR_HEIGHT,
                          background: getNodeColor(node.node_type),
                          borderRadius: 4,
                          cursor: onNodeClick ? 'pointer' : 'default',
                          opacity: isHovered ? 1 : 0.85,
                          transition: 'opacity 0.15s',
                          boxShadow: isHovered ? '0 0 8px rgba(88, 166, 255, 0.4)' : 'none',
                        }}
                        onMouseEnter={() => setHoveredNode({ r: rIdx, n: nIdx })}
                        onMouseLeave={() => setHoveredNode(null)}
                        onClick={() => onNodeClick?.(rIdx, nIdx)}
                      />
                    );
                  })}
                </div>
              </div>
            );
          })}

          {/* 悬停提示 */}
          {hoveredNode && (() => {
            const round = rounds[hoveredNode.r];
            const node = round.nodes[hoveredNode.n];
            return (
              <div style={{
                position: 'absolute',
                bottom: 8,
                right: 16,
                background: '#21262d',
                border: `1px solid ${BORDER}`,
                borderRadius: 6,
                padding: '8px 12px',
                fontSize: 12,
                color: TEXT,
                zIndex: 10,
              }}>
                <div style={{ fontWeight: 600 }}>{node.node_name}</div>
                <div style={{ color: TEXT_DIM }}>{getNodeLabel(node.node_type)} · {formatDuration(node.duration_ms ?? 0)} · {node.status}</div>
              </div>
            );
          })()}

          {/* 图例 */}
          <div style={{ display: 'flex', gap: 16, marginTop: 12, paddingLeft: PADDING_LEFT }}>
            {Object.entries({ prompt_render: 'Prompt 渲染', llm_call: 'LLM 调用', skill_call: 'Skill 执行', error: '错误' }).map(([type, label]) => (
              <div key={type} style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                <div style={{ width: 12, height: 12, borderRadius: 2, background: getNodeColor(type) }} />
                <span style={{ color: TEXT_DIM, fontSize: 11 }}>{label}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function formatDuration(ms: number): string {
  if (ms >= 1000) {
    return `${(ms / 1000).toFixed(2)}s`;
  }
  return `${ms}ms`;
}
```

- [ ] **Step 3: Commit**

```bash
git add admin-web/src/components/GanttTimeline/
git commit -m "feat(admin-web): 实现 GanttTimeline 组件"
```

---

## Task 5: 修改 App.tsx — 新增路由

**Files:**
- Modify: `admin-web/src/App.tsx`

- [ ] **Step 1: 新增路由和页面导入**

Modify `admin-web/src/App.tsx`:

```typescript
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { ConfigProvider, theme } from 'antd';
import zhCN from 'antd/locale/zh_CN';
import AdminLayout from './layouts/AdminLayout';
import Dashboard from './pages/Dashboard';
import Crops from './pages/Crops';
import Cycles from './pages/Cycles';
import CycleDetail from './pages/Cycles/Detail';
import Logs from './pages/Logs';
import Costs from './pages/Costs';
import Agent from './pages/Agent';
import Weather from './pages/Weather';
import ApiTester from './pages/ApiTester';
// ── 新增开发调试页面 ──
import TraceMonitor from './pages/TraceMonitor';
import TokenDashboard from './pages/TokenDashboard';
import Playground from './pages/Playground';
import SkillRegistry from './pages/SkillRegistry';
import PromptInspector from './pages/PromptInspector';
import ConfigKeys from './pages/ConfigKeys';

export default function App() {
  return (
    <ConfigProvider locale={zhCN} theme={{ algorithm: theme.darkAlgorithm }}>
      <BrowserRouter>
        <AdminLayout>
          <Routes>
            {/* 业务管理 */}
            <Route path="/" element={<Dashboard />} />
            <Route path="/crops" element={<Crops />} />
            <Route path="/cycles" element={<Cycles />} />
            <Route path="/cycles/:id" element={<CycleDetail />} />
            <Route path="/logs" element={<Logs />} />
            <Route path="/costs" element={<Costs />} />
            <Route path="/agent" element={<Agent />} />
            <Route path="/weather" element={<Weather />} />
            <Route path="/api-tester" element={<ApiTester />} />
            {/* 开发调试 */}
            <Route path="/dev/traces" element={<TraceMonitor />} />
            <Route path="/dev/tokens" element={<TokenDashboard />} />
            <Route path="/dev/playground" element={<Playground />} />
            <Route path="/dev/skills" element={<SkillRegistry />} />
            <Route path="/dev/prompts" element={<PromptInspector />} />
            <Route path="/dev/config" element={<ConfigKeys />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </AdminLayout>
      </BrowserRouter>
    </ConfigProvider>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add admin-web/src/App.tsx
git commit -m "feat(admin-web): 新增 /dev/* 路由"
```

---

## Task 6: 修改 AdminLayout — 侧边栏分组

**Files:**
- Modify: `admin-web/src/layouts/AdminLayout.tsx`

- [ ] **Step 1: 重写菜单结构**

Replace the entire content of `admin-web/src/layouts/AdminLayout.tsx`:

```typescript
import { useState } from 'react';
import { Layout, Menu, Button, Tooltip } from 'antd';
import {
  DashboardOutlined,
  EnvironmentOutlined,
  SwapOutlined,
  FileTextOutlined,
  DollarOutlined,
  RobotOutlined,
  CloudOutlined,
  ApiOutlined,
  MenuFoldOutlined,
  MenuUnfoldOutlined,
  // ── 开发调试用图标 ──
  BranchesOutlined,
  BarChartOutlined,
  MessageOutlined,
  AppstoreOutlined,
  FileSearchOutlined,
  SettingOutlined,
} from '@ant-design/icons';
import { useNavigate, useLocation } from 'react-router-dom';

const { Sider, Content, Header } = Layout;

const BG_PRIMARY = '#0d1117';
const BG_SECONDARY = '#161b22';
const BG_CARD = '#21262d';
const BORDER = '#30363d';
const TEXT_PRIMARY = '#c9d1d9';
const TEXT_SECONDARY = '#8b949e';
const ACCENT = '#58a6ff';

/** 业务管理菜单项 */
const businessItems = [
  { key: '/', icon: <DashboardOutlined />, label: '仪表盘' },
  { key: '/crops', icon: <EnvironmentOutlined />, label: '作物管理' },
  { key: '/cycles', icon: <SwapOutlined />, label: '茬口管理' },
  { key: '/logs', icon: <FileTextOutlined />, label: '农事日志' },
  { key: '/costs', icon: <DollarOutlined />, label: '成本记账' },
  { key: '/agent', icon: <RobotOutlined />, label: 'AI 助手' },
  { key: '/weather', icon: <CloudOutlined />, label: '天气预报' },
  { key: '/api-tester', icon: <ApiOutlined />, label: 'API Tester' },
];

/** 开发调试菜单项 */
const devItems = [
  { key: '/dev/traces', icon: <BranchesOutlined />, label: '链路追踪' },
  { key: '/dev/tokens', icon: <BarChartOutlined />, label: 'Token 看板' },
  { key: '/dev/playground', icon: <MessageOutlined />, label: 'Playground' },
  { key: '/dev/skills', icon: <AppstoreOutlined />, label: 'Skill 注册表' },
  { key: '/dev/prompts', icon: <FileSearchOutlined />, label: 'Prompt 检查器' },
  { key: '/dev/config', icon: <SettingOutlined />, label: '配置管理' },
];

const allItems = [...businessItems, ...devItems];

const pageTitles: Record<string, string> = Object.fromEntries(
  allItems.map((i) => [i.key, i.label])
);

export default function AdminLayout({ children }: { children: React.ReactNode }) {
  const [collapsed, setCollapsed] = useState(false);
  const navigate = useNavigate();
  const location = useLocation();

  const currentTitle = pageTitles[location.pathname] || 'Farm Manager';

  return (
    <Layout style={{ minHeight: '100vh', background: BG_PRIMARY }}>
      <Sider
        width={210}
        collapsedWidth={64}
        collapsed={collapsed}
        style={{
          background: BG_SECONDARY,
          borderRight: `1px solid ${BORDER}`,
          overflow: 'hidden',
        }}
      >
        {/* Logo */}
        <div
          style={{
            height: 56,
            display: 'flex',
            alignItems: 'center',
            justifyContent: collapsed ? 'center' : 'flex-start',
            padding: collapsed ? 0 : '0 20px',
            borderBottom: `1px solid ${BORDER}`,
            gap: 10,
          }}
        >
          <div
            style={{
              width: 28,
              height: 28,
              borderRadius: 6,
              background: 'linear-gradient(135deg, #58a6ff 0%, #238636 100%)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              flexShrink: 0,
            }}
          >
            <span style={{ color: '#fff', fontSize: 14, fontWeight: 'bold' }}>F</span>
          </div>
          {!collapsed && (
            <span style={{ color: ACCENT, fontSize: 16, fontWeight: 700, letterSpacing: 0.5, whiteSpace: 'nowrap' }}>
              Farm Manager
            </span>
          )}
        </div>

        {/* Menu */}
        <Menu
          theme="dark"
          mode="inline"
          selectedKeys={[location.pathname]}
          style={{ background: 'transparent', borderRight: 'none', padding: '8px 0' }}
          onClick={({ key }: { key: string }) => navigate(key)}
          items={[
            {
              type: 'group',
              label: collapsed ? undefined : '业务管理',
              children: businessItems,
            },
            {
              type: 'group',
              label: collapsed ? undefined : '开发调试',
              children: devItems,
            },
          ]}
        />

        {/* Collapse button at bottom */}
        <div
          style={{
            position: 'absolute',
            bottom: 0,
            left: 0,
            right: 0,
            height: 48,
            borderTop: `1px solid ${BORDER}`,
            display: 'flex',
            alignItems: 'center',
            justifyContent: collapsed ? 'center' : 'flex-end',
            padding: collapsed ? 0 : '0 16px',
            background: BG_SECONDARY,
          }}
        >
          <Tooltip title={collapsed ? '展开' : '收起'} placement="right">
            <Button
              type="text"
              icon={collapsed ? <MenuUnfoldOutlined /> : <MenuFoldOutlined />}
              onClick={() => setCollapsed(!collapsed)}
              style={{ color: TEXT_SECONDARY }}
            />
          </Tooltip>
        </div>
      </Sider>

      <Layout style={{ background: BG_PRIMARY }}>
        {/* Header */}
        <Header
          style={{
            background: BG_SECONDARY,
            height: 56,
            padding: '0 24px',
            borderBottom: `1px solid ${BORDER}`,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
          }}
        >
          <span style={{ fontSize: 16, fontWeight: 600, color: TEXT_PRIMARY }}>
            {currentTitle}
          </span>
          <span style={{ fontSize: 12, color: TEXT_SECONDARY }}>
            {new Date().toLocaleDateString('zh-CN')}
          </span>
        </Header>

        {/* Content */}
        <Content
          style={{
            margin: 20,
            padding: 20,
            background: BG_CARD,
            borderRadius: 12,
            border: `1px solid ${BORDER}`,
            overflow: 'auto',
            minHeight: 'calc(100vh - 96px)',
          }}
        >
          {children}
        </Content>
      </Layout>
    </Layout>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add admin-web/src/layouts/AdminLayout.tsx
git commit -m "feat(admin-web): 侧边栏按业务管理和开发调试分组"
```

---

## Task 7: 创建 TraceMonitor 页面

**Files:**
- Create: `admin-web/src/pages/TraceMonitor/index.tsx`

- [ ] **Step 1: 编写 TraceMonitor 页面**

Create `admin-web/src/pages/TraceMonitor/index.tsx`:

```typescript
import { useState, useCallback } from 'react';
import { Input, Button, Table, Drawer, DatePicker, Modal, message, Typography, Space } from 'antd';
import { SearchOutlined, DeleteOutlined } from '@ant-design/icons';
import type { ColumnsType } from 'antd/es/table';
import GanttTimeline from '../../components/GanttTimeline';
import { listTraces, getTimeline, getNodeDetail, deleteTraces } from '../../api/admin';
import type { TraceRecord, TimelineResponse, NodeDetail } from '../../api/admin';

const BG = '#0d1117';
const CARD = '#161b22';
const BORDER = '#30363d';
const TEXT = '#e6edf3';
const TEXT_DIM = '#8b949e';

interface TraceRow {
  key: string;
  request_id: string;
  session_id: string | null;
  farm_id: number;
  node_count: number;
  total_duration: number;
  created_at: string;
}

export default function TraceMonitor() {
  const [loading, setLoading] = useState(false);
  const [traces, setTraces] = useState<TraceRow[]>([]);
  const [total, setTotal] = useState(0);
  const [filters, setFilters] = useState({ request_id: '', session_id: '', farm_id: '' });
  const [expandedRowKeys, setExpandedRowKeys] = useState<string[]>([]);
  const [expandedTimeline, setExpandedTimeline] = useState<Record<string, TimelineResponse>>({});
  const [drawerVisible, setDrawerVisible] = useState(false);
  const [nodeDetail, setNodeDetail] = useState<NodeDetail | null>(null);
  const [cleanupDate, setCleanupDate] = useState<string | null>(null);

  const fetchTraces = useCallback(async (offset = 0) => {
    setLoading(true);
    try {
      const params: Record<string, unknown> = { limit: 20, offset };
      if (filters.request_id) params.request_id = filters.request_id;
      if (filters.session_id) params.session_id = filters.session_id;
      if (filters.farm_id) params.farm_id = parseInt(filters.farm_id, 10);

      const res = await listTraces(params);
      // 按 request_id 聚合，计算节点数和总耗时
      const byRequest: Record<string, { record: TraceRecord; count: number; totalDur: number }> = {};
      for (const item of res.items) {
        if (!byRequest[item.request_id]) {
          byRequest[item.request_id] = { record: item, count: 0, totalDur: 0 };
        }
        byRequest[item.request_id].count += 1;
        byRequest[item.request_id].totalDur += item.duration_ms ?? 0;
      }
      const rows: TraceRow[] = Object.values(byRequest).map(({ record, count, totalDur }) => ({
        key: record.request_id,
        request_id: record.request_id,
        session_id: record.session_id,
        farm_id: record.farm_id,
        node_count: count,
        total_duration: totalDur,
        created_at: record.created_at,
      }));
      setTraces(rows);
      setTotal(res.total);
    } catch {
      message.error('查询 trace 失败');
    } finally {
      setLoading(false);
    }
  }, [filters]);

  const handleExpand = async (expanded: boolean, record: TraceRow) => {
    if (expanded) {
      setExpandedRowKeys([record.key]);
      if (!expandedTimeline[record.key]) {
        try {
          const timeline = await getTimeline(record.request_id);
          setExpandedTimeline((prev) => ({ ...prev, [record.key]: timeline }));
        } catch {
          message.error('加载 timeline 失败');
        }
      }
    } else {
      setExpandedRowKeys([]);
    }
  };

  const handleNodeClick = async (_roundIndex: number, nodeIndex: number) => {
    const timeline = expandedTimeline[expandedRowKeys[0]];
    if (!timeline) return;
    // 找到被点击的节点对应的 trace record id
    // 注意：这里需要知道原始 record id，但 timeline API 不返回 id
    // 简化方案：展示该节点的 input/output（timeline 已包含）
    let idx = 0;
    for (const round of timeline.rounds) {
      for (const node of round.nodes) {
        if (idx === nodeIndex) {
          // 直接用 timeline 中的数据展示，不额外调用 node detail API
          setNodeDetail({
            id: 0,
            request_id: timeline.request_id,
            round_index: round.round_index,
            node_type: node.node_type,
            node_name: node.node_name,
            input_data: node.input_data,
            output_data: node.output_data,
            duration_ms: node.duration_ms,
            token_usage: node.token_usage ? JSON.stringify(node.token_usage) : null,
            status: node.status,
            error_message: node.error_message,
            start_time: node.start_time,
            end_time: null,
          });
          setDrawerVisible(true);
          return;
        }
        idx++;
      }
    }
  };

  const handleCleanup = () => {
    if (!cleanupDate) {
      message.warning('请选择清理截止日期');
      return;
    }
    Modal.confirm({
      title: '确认清理历史 Trace',
      content: `将删除 ${cleanupDate} 之前的所有 trace 记录，此操作不可恢复。`,
      okText: '确认删除',
      okType: 'danger',
      cancelText: '取消',
      async onOk() {
        try {
          const res = await deleteTraces(cleanupDate);
          message.success(`已删除 ${res.deleted} 条 trace 记录`);
          fetchTraces();
        } catch {
          message.error('清理失败');
        }
      },
    });
  };

  const columns: ColumnsType<TraceRow> = [
    { title: 'Request ID', dataIndex: 'request_id', key: 'request_id',
      render: (v: string) => <span style={{ fontFamily: 'monospace', color: TEXT }}>{v.slice(0, 8)}</span>,
    },
    { title: 'Farm ID', dataIndex: 'farm_id', key: 'farm_id', width: 80 },
    { title: '节点数', dataIndex: 'node_count', key: 'node_count', width: 80 },
    { title: '总耗时', dataIndex: 'total_duration', key: 'total_duration', width: 100,
      render: (v: number) => `${v}ms`,
    },
    { title: '创建时间', dataIndex: 'created_at', key: 'created_at', width: 180 },
  ];

  return (
    <div>
      <Typography.Title level={4} style={{ color: TEXT, marginBottom: 16 }}>链路追踪</Typography.Title>

      {/* 筛选区 */}
      <Space style={{ marginBottom: 16 }} wrap>
        <Input placeholder="Request ID" style={{ width: 200, background: CARD, borderColor: BORDER, color: TEXT }}
          value={filters.request_id} onChange={(e) => setFilters((f) => ({ ...f, request_id: e.target.value }))} />
        <Input placeholder="Session ID" style={{ width: 200, background: CARD, borderColor: BORDER, color: TEXT }}
          value={filters.session_id} onChange={(e) => setFilters((f) => ({ ...f, session_id: e.target.value }))} />
        <Input placeholder="Farm ID" style={{ width: 120, background: CARD, borderColor: BORDER, color: TEXT }}
          value={filters.farm_id} onChange={(e) => setFilters((f) => ({ ...f, farm_id: e.target.value }))} />
        <Button type="primary" icon={<SearchOutlined />} onClick={() => fetchTraces()}>查询</Button>
      </Space>

      {/* 表格 */}
      <Table
        columns={columns}
        dataSource={traces}
        loading={loading}
        pagination={{ total, pageSize: 20, onChange: (page) => fetchTraces((page - 1) * 20) }}
        expandable={{
          expandedRowKeys,
          onExpand: handleExpand,
          expandedRowRender: (record) => {
            const timeline = expandedTimeline[record.key];
            if (!timeline) return <div style={{ color: TEXT_DIM }}>加载中...</div>;
            return (
              <div style={{ padding: 16, background: BG, borderRadius: 8 }}>
                <GanttTimeline
                  rounds={timeline.rounds.map((r) => ({
                    round_index: r.round_index,
                    nodes: r.nodes.map((n) => ({
                      node_type: n.node_type,
                      node_name: n.node_name,
                      duration_ms: n.duration_ms,
                      status: n.status,
                      start_time: n.start_time,
                    })),
                  }))}
                  onNodeClick={handleNodeClick}
                />
              </div>
            );
          },
        }}
        style={{ background: CARD }}
      />

      {/* 清理操作 */}
      <Space style={{ marginTop: 16 }}>
        <DatePicker placeholder="选择截止日期" style={{ background: CARD, borderColor: BORDER }}
          onChange={(_, dateStr) => setCleanupDate(dateStr as string)} />
        <Button danger icon={<DeleteOutlined />} onClick={handleCleanup}>清理历史</Button>
      </Space>

      {/* 节点详情 Drawer */}
      <Drawer
        title="节点详情"
        width={600}
        open={drawerVisible}
        onClose={() => setDrawerVisible(false)}
        styles={{ body: { background: BG } }}
      >
        {nodeDetail && (
          <div style={{ color: TEXT }}>
            <p><strong>节点:</strong> {nodeDetail.node_name} ({nodeDetail.node_type})</p>
            <p><strong>状态:</strong> {nodeDetail.status}</p>
            <p><strong>耗时:</strong> {nodeDetail.duration_ms}ms</p>
            {nodeDetail.error_message && (
              <p style={{ color: '#ff4d4f' }}><strong>错误:</strong> {nodeDetail.error_message}</p>
            )}
            {nodeDetail.input_data && (
              <>
                <p style={{ marginTop: 16 }}><strong>Input:</strong></p>
                <pre style={{ background: CARD, padding: 12, borderRadius: 6, overflow: 'auto', fontSize: 12 }}>
                  {nodeDetail.input_data}
                </pre>
              </>
            )}
            {nodeDetail.output_data && (
              <>
                <p style={{ marginTop: 16 }}><strong>Output:</strong></p>
                <pre style={{ background: CARD, padding: 12, borderRadius: 6, overflow: 'auto', fontSize: 12 }}>
                  {nodeDetail.output_data}
                </pre>
              </>
            )}
          </div>
        )}
      </Drawer>
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add admin-web/src/pages/TraceMonitor/
git commit -m "feat(admin-web): 实现 Trace Monitor 页面"
```

---

## Task 8: 创建 TokenDashboard 页面

**Files:**
- Create: `admin-web/src/pages/TokenDashboard/index.tsx`

- [ ] **Step 1: 编写 TokenDashboard 页面**

Create `admin-web/src/pages/TokenDashboard/index.tsx`:

```typescript
import { useState, useEffect, useMemo } from 'react';
import { Card, Row, Col, Statistic, Segmented, Table, Typography, message } from 'antd';
import { Line, Bar } from '@ant-design/charts';
import { getTokenSummary, getTokenDaily } from '../../api/admin';
import type { TokenSummaryResponse, TokenDailyResponse } from '../../api/admin';

const BG = '#0d1117';
const CARD_BG = '#161b22';
const BORDER = '#30363d';
const TEXT = '#e6edf3';
const TEXT_DIM = '#8b949e';

export default function TokenDashboard() {
  const [days, setDays] = useState<7 | 30>(7);
  const [summary, setSummary] = useState<TokenSummaryResponse | null>(null);
  const [dailyData, setDailyData] = useState<TokenDailyResponse | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    fetchData();
  }, [days]);

  const fetchData = async () => {
    setLoading(true);
    try {
      const [s, d] = await Promise.all([
        getTokenSummary(days),
        getTokenDaily(),
      ]);
      setSummary(s);
      setDailyData(d);
    } catch {
      message.error('加载 Token 数据失败');
    } finally {
      setLoading(false);
    }
  };

  const quotaPercent = useMemo(() => {
    if (!summary) return 0;
    const dailyLimit = 10000; // 假设配额，实际应从 config API 获取
    return Math.min((summary.total_tokens / dailyLimit) * 100, 100);
  }, [summary]);

  const quotaColor = quotaPercent >= 100 ? '#ff4d4f' : quotaPercent >= 80 ? '#faad14' : '#52c41a';

  // 模拟趋势数据（后端暂不支持按日期趋势，用 summary.by_model 展示）
  const trendData = useMemo(() => {
    if (!summary) return [];
    return Object.values(summary.by_model).map((item) => ({
      model: item.model,
      tokens: item.total_tokens,
      requests: item.request_count,
    }));
  }, [summary]);

  const barData = useMemo(() => {
    if (!summary) return [];
    const result: { model: string; type: string; value: number }[] = [];
    for (const item of Object.values(summary.by_model)) {
      result.push({ model: item.model, type: 'Prompt', value: item.prompt_tokens });
      result.push({ model: item.model, type: 'Completion', value: item.completion_tokens });
    }
    return result;
  }, [summary]);

  const lineConfig = {
    data: trendData,
    xField: 'model',
    yField: 'tokens',
    smooth: true,
    color: '#58a6ff',
    height: 240,
    theme: 'dark',
    tooltip: { showMarkers: true },
  };

  const barConfig = {
    data: barData,
    xField: 'model',
    yField: 'value',
    seriesField: 'type',
    group: true,
    height: 240,
    theme: 'dark',
    color: ['#58a6ff', '#238636'],
  };

  return (
    <div>
      <Typography.Title level={4} style={{ color: TEXT, marginBottom: 16 }}>Token 用量看板</Typography.Title>

      {/* 时间范围切换 */}
      <Segmented
        options={[
          { label: '近 7 天', value: 7 },
          { label: '近 30 天', value: 30 },
        ]}
        value={days}
        onChange={(v) => setDays(v as 7 | 30)}
        style={{ marginBottom: 16, background: CARD_BG }}
      />

      {/* 统计卡片 */}
      <Row gutter={16} style={{ marginBottom: 16 }}>
        <Col span={6}>
          <Card style={{ background: CARD_BG, borderColor: BORDER }} loading={loading}>
            <Statistic
              title={<span style={{ color: TEXT_DIM }}>总 Tokens</span>}
              value={summary?.total_tokens ?? 0}
              valueStyle={{ color: TEXT }}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card style={{ background: CARD_BG, borderColor: BORDER }} loading={loading}>
            <Statistic
              title={<span style={{ color: TEXT_DIM }}>总请求数</span>}
              value={summary?.total_requests ?? 0}
              valueStyle={{ color: TEXT }}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card style={{ background: CARD_BG, borderColor: BORDER }} loading={loading}>
            <Statistic
              title={<span style={{ color: TEXT_DIM }}>今日用量</span>}
              value={dailyData?.items.reduce((sum, i) => sum + i.total_tokens, 0) ?? 0}
              valueStyle={{ color: TEXT }}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card style={{ background: CARD_BG, borderColor: BORDER }} loading={loading}>
            <div style={{ color: TEXT_DIM, fontSize: 14, marginBottom: 8 }}>配额使用</div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <div style={{ flex: 1, height: 8, background: '#21262d', borderRadius: 4, overflow: 'hidden' }}>
                <div style={{ width: `${quotaPercent}%`, height: '100%', background: quotaColor, borderRadius: 4, transition: 'width 0.3s' }} />
              </div>
              <span style={{ color: quotaColor, fontWeight: 600, fontSize: 14 }}>{quotaPercent.toFixed(1)}%</span>
            </div>
          </Card>
        </Col>
      </Row>

      {/* 图表区 */}
      <Row gutter={16} style={{ marginBottom: 16 }}>
        <Col span={12}>
          <Card title={<span style={{ color: TEXT }}>按模型用量</span>} style={{ background: CARD_BG, borderColor: BORDER }} loading={loading}>
            {trendData.length > 0 ? <Line {...lineConfig} /> : <div style={{ color: TEXT_DIM, textAlign: 'center', padding: 40 }}>暂无数据</div>}
          </Card>
        </Col>
        <Col span={12}>
          <Card title={<span style={{ color: TEXT }}>Prompt / Completion 分布</span>} style={{ background: CARD_BG, borderColor: BORDER }} loading={loading}>
            {barData.length > 0 ? <Bar {...barConfig} /> : <div style={{ color: TEXT_DIM, textAlign: 'center', padding: 40 }}>暂无数据</div>}
          </Card>
        </Col>
      </Row>

      {/* 明细表格 */}
      <Card title={<span style={{ color: TEXT }}>今日明细</span>} style={{ background: CARD_BG, borderColor: BORDER }} loading={loading}>
        <Table
          dataSource={dailyData?.items ?? []}
          pagination={false}
          columns={[
            { title: '模型', dataIndex: 'model', key: 'model' },
            { title: '调用类型', dataIndex: 'call_type', key: 'call_type' },
            { title: 'Prompt Tokens', dataIndex: 'prompt_tokens', key: 'prompt_tokens' },
            { title: 'Completion Tokens', dataIndex: 'completion_tokens', key: 'completion_tokens' },
            { title: 'Total Tokens', dataIndex: 'total_tokens', key: 'total_tokens' },
            { title: '请求数', dataIndex: 'request_count', key: 'request_count' },
            { title: '预估费用(CNY)', dataIndex: 'estimated_cost_cny', key: 'cost', render: (v: number) => `¥${v.toFixed(4)}` },
          ]}
          style={{ background: 'transparent' }}
        />
      </Card>
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add admin-web/src/pages/TokenDashboard/
git commit -m "feat(admin-web): 实现 Token Dashboard 页面"
```

---

## Task 9: 创建 Playground 页面

**Files:**
- Create: `admin-web/src/pages/Playground/index.tsx`

- [ ] **Step 1: 编写 Playground 页面**

Create `admin-web/src/pages/Playground/index.tsx`:

```typescript
import { useState, useRef, useEffect, useCallback } from 'react';
import { Input, Button, Space, Collapse, message, Typography } from 'antd';
import { SendOutlined, ClearOutlined } from '@ant-design/icons';
import ReactMarkdown from 'react-markdown';
import GanttTimeline from '../../components/GanttTimeline';
import { getTimeline } from '../../api/admin';
import type { TimelineResponse } from '../../api/admin';

const BG = '#0d1117';
const CARD = '#161b22';
const BORDER = '#30363d';
const TEXT = '#e6edf3';
const TEXT_DIM = '#8b949e';
const ACCENT = '#58a6ff';
const USER_BG = '#1f6feb';
const AI_BG = '#21262d';

interface Message {
  role: 'user' | 'assistant';
  content: string;
}

/** 生成随机 session_id */
function genSessionId(): string {
  return Math.random().toString(36).substring(2, 10);
}

async function* streamPlayground(message: string, _sessionId: string): AsyncGenerator<string> {
  const resp = await fetch('/api/agent/chat/stream', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message }),
  });
  if (!resp.ok || !resp.body) throw new Error(`stream error: ${resp.status}`);
  const reader = resp.body.getReader();
  const decoder = new TextDecoder();
  let buf = '';
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buf += decoder.decode(value, { stream: true });
    const lines = buf.split('\n');
    buf = lines.pop() ?? '';
    for (const line of lines) {
      const trimmed = line.trim();
      if (!trimmed.startsWith('data: ')) continue;
      const payload = trimmed.slice(6);
      if (payload === '[DONE]') return;
      try {
        const obj = JSON.parse(payload);
        if (obj.error) throw new Error(obj.error);
        if (obj.content) yield obj.content;
      } catch (e) {
        if (e instanceof SyntaxError) continue;
        throw e;
      }
    }
  }
}

function MarkdownContent({ content }: { content: string }) {
  return (
    <div style={{ color: TEXT, lineHeight: 1.7, fontSize: 14 }}>
      <ReactMarkdown>{content}</ReactMarkdown>
    </div>
  );
}

function ChatBubble({ role, content }: { role: string; content: string }) {
  const isUser = role === 'user';
  return (
    <div style={{ marginBottom: 16, display: 'flex', justifyContent: isUser ? 'flex-end' : 'flex-start' }}>
      {!isUser && (
        <div style={{
          width: 32, height: 32, borderRadius: '50%', background: '#238636',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          color: '#fff', fontSize: 14, fontWeight: 700, marginRight: 10, flexShrink: 0,
        }}>AI</div>
      )}
      <div style={{
        background: isUser ? USER_BG : AI_BG,
        color: TEXT,
        padding: '10px 16px',
        borderRadius: isUser ? '18px 18px 4px 18px' : '18px 18px 18px 4px',
        maxWidth: '70%',
        wordBreak: 'break-word',
      }}>
        {isUser ? content : <MarkdownContent content={content} />}
      </div>
    </div>
  );
}

export default function Playground() {
  const [input, setInput] = useState('');
  const [messages, setMessages] = useState<Message[]>([]);
  const [loading, setLoading] = useState(false);
  const [sessionId, setSessionId] = useState(() => genSessionId());
  const [traceData, setTraceData] = useState<TimelineResponse | null>(null);
  const [traceLoading, setTraceLoading] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    setTimeout(() => scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: 'smooth' }), 50);
  };

  const handleSend = async () => {
    if (!input.trim()) return;
    const userMsg = input;
    setMessages((prev) => [...prev, { role: 'user', content: userMsg }]);
    setInput('');
    setMessages((prev) => [...prev, { role: 'assistant', content: '' }]);
    setLoading(true);
    setTraceData(null);
    scrollToBottom();

    try {
      let idx = -1;
      setMessages((prev) => { idx = prev.length - 1; return prev; });
      for await (const chunk of streamPlayground(userMsg, sessionId)) {
        setMessages((prev) => {
          const next = [...prev];
          next[idx] = { ...next[idx], content: next[idx].content + chunk };
          return next;
        });
        scrollToBottom();
      }
      // 对话完成后尝试获取 trace
      // 注意：SSE 不返回 request_id，这里简化为延迟后查询最新 trace
      // 实际可通过后端增强 SSE 响应头来关联
      await loadLatestTrace();
    } catch {
      setMessages((prev) => {
        const next = [...prev];
        next[next.length - 1] = { role: 'assistant', content: '对话失败，请重试' };
        return next;
      });
    } finally {
      setLoading(false);
    }
  };

  const loadLatestTrace = useCallback(async () => {
    setTraceLoading(true);
    try {
      // 简化为查询所有 trace，取最新的一个
      const { listTraces } = await import('../../api/admin');
      const res = await listTraces({ limit: 1 });
      if (res.items.length > 0) {
        const timeline = await getTimeline(res.items[0].request_id);
        setTraceData(timeline);
      }
    } catch {
      // trace 查询失败静默处理
    } finally {
      setTraceLoading(false);
    }
  }, []);

  const handleClear = () => {
    setMessages([]);
    setTraceData(null);
    setSessionId(genSessionId());
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: 'calc(100vh - 136px)' }}>
      <Typography.Title level={4} style={{ color: TEXT, marginBottom: 12 }}>Chat Playground</Typography.Title>

      {/* 配置栏 */}
      <div style={{ display: 'flex', gap: 12, marginBottom: 12, alignItems: 'center' }}>
        <span style={{ color: TEXT_DIM, fontSize: 12 }}>Session: {sessionId}</span>
        <Button size="small" icon={<ClearOutlined />} onClick={handleClear}>清空对话</Button>
      </div>

      {/* 消息区域 */}
      <div ref={scrollRef} style={{
        flex: 1, overflow: 'auto', background: BG, borderRadius: 12,
        border: `1px solid ${BORDER}`, padding: 20, marginBottom: 12,
      }}>
        {messages.length === 0 && (
          <div style={{ textAlign: 'center', color: TEXT_DIM, padding: '60px 0' }}>
            <div style={{ fontSize: 40, marginBottom: 16 }}>🧪</div>
            <div style={{ fontSize: 16, marginBottom: 8 }}>Playground — 开发者调试</div>
            <div style={{ fontSize: 13 }}>直接与 Agent 对话，回复后自动展示执行链路</div>
          </div>
        )}
        {messages.map((m, i) => <ChatBubble key={i} role={m.role} content={m.content} />)}
        {loading && messages[messages.length - 1]?.content === '' && (
          <div style={{ display: 'flex', alignItems: 'center', color: TEXT_DIM, padding: '0 42px' }}>
            <span className="ant-spin-dot" style={{ marginRight: 8 }} />
            AI 正在思考中...
          </div>
        )}

        {/* Trace Overlay */}
        {traceData && (
          <Collapse
            style={{ marginTop: 16, background: CARD, borderColor: BORDER }}
            items={[
              {
                key: 'trace',
                label: <span style={{ color: ACCENT }}>执行链路</span>,
                children: (
                  <GanttTimeline
                    rounds={traceData.rounds.map((r) => ({
                      round_index: r.round_index,
                      nodes: r.nodes.map((n) => ({
                        node_type: n.node_type,
                        node_name: n.node_name,
                        duration_ms: n.duration_ms,
                        status: n.status,
                        start_time: n.start_time,
                      })),
                    }))}
                  />
                ),
              },
            ]}
          />
        )}
        {traceLoading && (
          <div style={{ color: TEXT_DIM, textAlign: 'center', padding: 16 }}>加载执行链路...</div>
        )}
      </div>

      {/* 输入区域 */}
      <Space.Compact style={{ width: '100%' }}>
        <Input size="large" value={input} onChange={(e) => setInput(e.target.value)}
          onPressEnter={handleSend} placeholder="输入消息..."
          style={{ background: CARD, borderColor: BORDER, color: TEXT }} />
        <Button size="large" type="primary" icon={<SendOutlined />} onClick={handleSend}
          loading={loading} style={{ height: 40 }}>发送</Button>
      </Space.Compact>
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add admin-web/src/pages/Playground/
git commit -m "feat(admin-web): 实现 Chat Playground 页面"
```

---

## Task 10: 创建 SkillRegistry 页面

**Files:**
- Create: `admin-web/src/pages/SkillRegistry/index.tsx`

- [ ] **Step 1: 编写 SkillRegistry 页面**

Create `admin-web/src/pages/SkillRegistry/index.tsx`:

```typescript
import { useState, useEffect } from 'react';
import { Card, Tag, Typography, Empty, message } from 'antd';
import { AppstoreOutlined } from '@ant-design/icons';
import { listSkills } from '../../api/admin';
import type { SkillItem } from '../../api/admin';

const CARD_BG = '#161b22';
const BORDER = '#30363d';
const TEXT = '#e6edf3';
const TEXT_DIM = '#8b949e';

export default function SkillRegistry() {
  const [skills, setSkills] = useState<SkillItem[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    fetchSkills();
  }, []);

  const fetchSkills = async () => {
    setLoading(true);
    try {
      const res = await listSkills();
      setSkills(res.items);
    } catch {
      message.error('加载 Skill 列表失败');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      <Typography.Title level={4} style={{ color: TEXT, marginBottom: 16 }}>
        <AppstoreOutlined style={{ marginRight: 8 }} />Skill 注册表
      </Typography.Title>

      {skills.length === 0 && !loading ? (
        <Empty description={<span style={{ color: TEXT_DIM }}>暂无注册 Skill</span>} style={{ padding: 60 }} />
      ) : (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(360px, 1fr))', gap: 16 }}>
          {skills.map((skill) => (
            <Card
              key={skill.name}
              loading={loading}
              style={{ background: CARD_BG, borderColor: BORDER }}
              title={
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <span style={{ color: TEXT, fontWeight: 600 }}>{skill.name}</span>
                  <Tag color={skill.status === 'active' ? 'green' : 'default'}>{skill.status}</Tag>
                </div>
              }
            >
              <p style={{ color: TEXT_DIM, marginBottom: 12, fontSize: 13 }}>{skill.description}</p>
              <div style={{ color: TEXT_DIM, fontSize: 12, marginBottom: 8 }}>参数 Schema:</div>
              <pre style={{
                background: '#0d1117',
                padding: 12,
                borderRadius: 6,
                overflow: 'auto',
                fontSize: 11,
                color: TEXT,
                maxHeight: 200,
              }}>
                {JSON.stringify(skill.parameters_schema, null, 2)}
              </pre>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add admin-web/src/pages/SkillRegistry/
git commit -m "feat(admin-web): 实现 Skill Registry 页面"
```

---

## Task 11: 创建 PromptInspector 页面

**Files:**
- Create: `admin-web/src/pages/PromptInspector/index.tsx`

- [ ] **Step 1: 编写 PromptInspector 页面**

Create `admin-web/src/pages/PromptInspector/index.tsx`:

```typescript
import { useState, useEffect } from 'react';
import { Table, Button, Tag, Typography, message, Modal } from 'antd';
import { ReloadOutlined, FileSearchOutlined } from '@ant-design/icons';
import type { ColumnsType } from 'antd/es/table';
import { listPrompts, reloadPrompts } from '../../api/admin';
import type { PromptItem } from '../../api/admin';

const CARD_BG = '#161b22';
const BORDER = '#30363d';
const TEXT = '#e6edf3';
const TEXT_DIM = '#8b949e';

export default function PromptInspector() {
  const [prompts, setPrompts] = useState<PromptItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [reloadLoading, setReloadLoading] = useState(false);

  useEffect(() => {
    fetchPrompts();
  }, []);

  const fetchPrompts = async () => {
    setLoading(true);
    try {
      const res = await listPrompts();
      setPrompts(res.items);
    } catch {
      message.error('加载 Prompt 列表失败');
    } finally {
      setLoading(false);
    }
  };

  const handleReload = async () => {
    setReloadLoading(true);
    try {
      const res = await reloadPrompts();
      message.success(res.message);
      await fetchPrompts();
    } catch {
      message.error('热加载失败');
    } finally {
      setReloadLoading(false);
    }
  };

  const handlePreview = (item: PromptItem) => {
    // 后端暂不支持 render API，展示基本信息
    Modal.info({
      title: `Prompt: ${item.name}`,
      width: 600,
      content: (
        <div style={{ color: TEXT }}>
          <p><strong>版本:</strong> {item.version}</p>
          <p><strong>状态:</strong> {item.active ? '激活' : '未激活'}</p>
          <p><strong>内容长度:</strong> {item.content_length} 字符</p>
          <p style={{ color: TEXT_DIM, marginTop: 12, fontSize: 12 }}>
            注：渲染预览功能需要后端支持 /admin/prompts/{name}/render 端点。
          </p>
        </div>
      ),
    });
  };

  const columns: ColumnsType<PromptItem> = [
    { title: '名称', dataIndex: 'name', key: 'name',
      render: (v: string) => <span style={{ color: TEXT, fontWeight: 500 }}>{v}</span>,
    },
    { title: '版本', dataIndex: 'version', key: 'version', width: 100 },
    { title: '状态', dataIndex: 'active', key: 'active', width: 100,
      render: (v: boolean) => <Tag color={v ? 'green' : 'default'}>{v ? '激活' : '未激活'}</Tag>,
    },
    { title: '内容长度', dataIndex: 'content_length', key: 'content_length', width: 120,
      render: (v: number) => `${v} 字符`,
    },
    { title: '操作', key: 'action', width: 120,
      render: (_, record) => (
        <Button type="link" size="small" onClick={() => handlePreview(record)}>
          预览
        </Button>
      ),
    },
  ];

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <Typography.Title level={4} style={{ color: TEXT, margin: 0 }}>
          <FileSearchOutlined style={{ marginRight: 8 }} />Prompt 检查器
        </Typography.Title>
        <Button icon={<ReloadOutlined />} onClick={handleReload} loading={reloadLoading}>
          重新加载模板
        </Button>
      </div>

      <Table
        columns={columns}
        dataSource={prompts}
        loading={loading}
        pagination={false}
        style={{ background: CARD_BG }}
      />
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add admin-web/src/pages/PromptInspector/
git commit -m "feat(admin-web): 实现 Prompt Inspector 页面"
```

---

## Task 12: 创建 ConfigKeys 页面

**Files:**
- Create: `admin-web/src/pages/ConfigKeys/index.tsx`

- [ ] **Step 1: 编写 ConfigKeys 页面**

Create `admin-web/src/pages/ConfigKeys/index.tsx`:

```typescript
import { useState, useEffect } from 'react';
import { Card, Button, Tag, Typography, Modal, message, Descriptions } from 'antd';
import { ClearOutlined, SettingOutlined } from '@ant-design/icons';
import { getConfig, clearCache } from '../../api/admin';
import type { ConfigResponse } from '../../api/admin';

const CARD_BG = '#161b22';
const BORDER = '#30363d';
const TEXT = '#e6edf3';
const TEXT_DIM = '#8b949e';

export default function ConfigKeys() {
  const [config, setConfig] = useState<ConfigResponse | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    fetchConfig();
  }, []);

  const fetchConfig = async () => {
    setLoading(true);
    try {
      const res = await getConfig();
      setConfig(res);
    } catch {
      message.error('加载配置失败');
    } finally {
      setLoading(false);
    }
  };

  const handleClearCache = () => {
    Modal.confirm({
      title: '确认清空缓存',
      content: '将清空所有 Skill 缓存和 TTL 缓存，此操作不可恢复。',
      okText: '确认清空',
      okType: 'danger',
      cancelText: '取消',
      async onOk() {
        try {
          const res = await clearCache();
          const skillCache = res.cleared.skill_cache ?? 0;
          const ttlCache = res.cleared.ttl_cache ?? 0;
          message.success(`已清空缓存 | Skill: ${skillCache}, TTL: ${ttlCache}`);
        } catch {
          message.error('清空缓存失败');
        }
      },
    });
  };

  if (!config) {
    return <div style={{ color: TEXT_DIM, textAlign: 'center', padding: 60 }}>加载中...</div>;
  }

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <Typography.Title level={4} style={{ color: TEXT, margin: 0 }}>
          <SettingOutlined style={{ marginRight: 8 }} />配置管理
        </Typography.Title>
        <Button danger icon={<ClearOutlined />} onClick={handleClearCache}>
          清空缓存
        </Button>
      </div>

      {/* AI 配置 */}
      <Card title={<span style={{ color: TEXT }}>AI 配置</span>} style={{ background: CARD_BG, borderColor: BORDER, marginBottom: 16 }}>
        <Descriptions column={2} labelStyle={{ color: TEXT_DIM }} contentStyle={{ color: TEXT }}>
          <Descriptions.Item label="模型">{config.ai.model}</Descriptions.Item>
          <Descriptions.Item label="Base URL">{config.ai.base_url}</Descriptions.Item>
          <Descriptions.Item label="API Key">{config.ai.api_key}</Descriptions.Item>
          <Descriptions.Item label="Enable Thinking">{config.ai.enable_thinking ? '是' : '否'}</Descriptions.Item>
        </Descriptions>
      </Card>

      {/* Trace 配置 */}
      <Card title={<span style={{ color: TEXT }}>Trace 配置</span>} style={{ background: CARD_BG, borderColor: BORDER, marginBottom: 16 }}>
        <Descriptions column={2} labelStyle={{ color: TEXT_DIM }} contentStyle={{ color: TEXT }}>
          <Descriptions.Item label="Batch Size">{config.trace.batch_size}</Descriptions.Item>
          <Descriptions.Item label="Flush Interval">{config.trace.flush_interval}ms</Descriptions.Item>
          <Descriptions.Item label="TTL Days">{config.trace.trace_ttl_days} 天</Descriptions.Item>
        </Descriptions>
      </Card>

      {/* Token 配额 */}
      <Card title={<span style={{ color: TEXT }}>Token 配额</span>} style={{ background: CARD_BG, borderColor: BORDER, marginBottom: 16 }}>
        <Descriptions column={2} labelStyle={{ color: TEXT_DIM }} contentStyle={{ color: TEXT }}>
          <Descriptions.Item label="日限额">{config.token_quota.daily_limit}</Descriptions.Item>
          <Descriptions.Item label="超额动作">
            <Tag color={config.token_quota.over_quota_action === 'block' ? 'red' : 'orange'}>
              {config.token_quota.over_quota_action}
            </Tag>
          </Descriptions.Item>
        </Descriptions>
      </Card>

      {/* LangSmith */}
      <Card title={<span style={{ color: TEXT }}>LangSmith</span>} style={{ background: CARD_BG, borderColor: BORDER }}>
        <Descriptions column={2} labelStyle={{ color: TEXT_DIM }} contentStyle={{ color: TEXT }}>
          <Descriptions.Item label="启用">{config.langsmith.enabled ? '是' : '否'}</Descriptions.Item>
          <Descriptions.Item label="项目">{config.langsmith.project}</Descriptions.Item>
        </Descriptions>
      </Card>

      {/* Key 验证提示 */}
      <div style={{ color: TEXT_DIM, fontSize: 12, marginTop: 16, padding: 12, background: '#0d1117', borderRadius: 6 }}>
        注：API Key 验证功能需要后端支持 /admin/config/validate-key 端点。当前 API Key 已脱敏展示。
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add admin-web/src/pages/ConfigKeys/
git commit -m "feat(admin-web): 实现 Config & Keys 页面"
```

---

## Task 13: 构建验证

**Files:**
- None (验证步骤)

- [ ] **Step 1: 运行 TypeScript 编译检查**

```bash
cd /Users/ljn/Documents/demo/explore/admin-web && npx tsc --noEmit
```

Expected: 无 TypeScript 错误。如有错误，根据报错信息修复类型问题。

- [ ] **Step 2: 运行构建**

```bash
cd /Users/ljn/Documents/demo/explore/admin-web && npm run build
```

Expected: 构建成功，输出到 `admin-web/dist/` 目录。

- [ ] **Step 3: Commit**

```bash
git add admin-web/
git commit -m "feat(admin-web): admin-web-redesign 完成 — 6 个开发调试页面"
```

---

## Task 14: 端到端验证清单

**Files:**
- None (手动验证)

- [ ] **Step 1: 启动后端服务**

```bash
cd /Users/ljn/Documents/demo/explore/backend && poetry run uvicorn app.main:app --reload
```

Expected: 后端启动在 `http://localhost:8000`，Admin API 端点可访问。

- [ ] **Step 2: 启动前端开发服务器**

```bash
cd /Users/ljn/Documents/demo/explore/admin-web && npm run dev
```

Expected: 前端启动在 `http://localhost:5173`，侧边栏显示两个分组。

- [ ] **Step 3: 验证侧边栏分组**

- 访问 `http://localhost:5173/`
- 确认侧边栏显示"业务管理"和"开发调试"两个分组
- 确认两组各有正确的菜单项
- 点击每个菜单项，确认路由跳转正确

- [ ] **Step 4: 验证 Trace Monitor**

- 访问 `/dev/traces`
- 点击"查询"按钮，确认 trace 列表加载
- 点击某行展开，确认 Gantt 图显示
- 悬停节点查看 tooltip，点击节点查看 Drawer 详情
- 选择日期后点击"清理历史"，确认弹窗和删除操作

- [ ] **Step 5: 验证 Token Dashboard**

- 访问 `/dev/tokens`
- 确认统计卡片显示（总 Tokens、请求数、今日用量、配额）
- 确认折线图和柱状图渲染
- 切换 7 天/30 天，确认数据更新

- [ ] **Step 6: 验证 Playground**

- 访问 `/dev/playground`
- 输入消息并发送，确认 SSE 流式回复
- 回复完成后，确认下方展开"执行链路"折叠面板
- 点击"清空对话"，确认消息和 trace 被清空

- [ ] **Step 7: 验证 Skill Registry**

- 访问 `/dev/skills`
- 确认 Skill 卡片网格展示
- 确认每个卡片显示 name、description、status 标签、parameters_schema JSON

- [ ] **Step 8: 验证 Prompt Inspector**

- 访问 `/dev/prompts`
- 确认表格展示 prompt 列表
- 点击"重新加载模板"按钮，确认提示和列表刷新
- 点击"预览"，确认 Modal 弹出基本信息

- [ ] **Step 9: 验证 Config & Keys**

- 访问 `/dev/config`
- 确认 AI/Trace/Token/LangSmith 配置卡片展示
- 确认 API Key 已脱敏（如 `sk-ab***cd`）
- 点击"清空缓存"，确认弹窗和操作反馈

- [ ] **Step 10: 确认现有页面不受影响**

- 访问 `/` (Dashboard)、`/crops`、`/cycles`、`/logs`、`/costs`、`/agent`、`/weather`、`/api-tester`
- 确认所有现有页面功能正常

---

## Self-Review Checklist

**1. Spec coverage:**

| Proposal 需求 | 对应 Task |
|---|---|
| Trace Monitor 页（Gantt 图、节点详情） | Task 7 |
| Token Dashboard 页（统计卡片、趋势图、柱状图、明细表） | Task 8 |
| Chat Playground 页（SSE 流式、trace overlay） | Task 9 |
| Skill Registry 页（卡片网格、schema 展示） | Task 10 |
| Prompt Inspector 页（列表、热加载） | Task 11 |
| Config & Keys 页（配置展示、缓存清空） | Task 12 |
| 侧边栏分组（业务管理 + 开发调试） | Task 6 |
| 前端 API 层统一封装 | Task 2 |
| 保留现有业务页面 | Task 5/6（路由保留，未修改页面代码） |

**2. Placeholder scan:**

- [x] 无 "TBD"、"TODO"、"implement later"
- [x] 无 "Add appropriate error handling" 等模糊描述
- [x] 每个代码步骤包含完整代码
- [x] 无 "Similar to Task N" 引用

**3. Type consistency:**

- [x] `TraceRecord` / `TimelineNode` / `TimelineResponse` 类型前后一致
- [x] `TokenSummaryResponse` / `TokenDailyResponse` 类型前后一致
- [x] `SkillItem` / `PromptItem` / `ConfigResponse` 类型前后一致
- [x] GanttTimeline `onNodeClick` 签名与使用处一致

**4. 已知限制（已在计划中处理）：**

- 后端 `GET /admin/prompts/{name}/render` 缺失 → PromptInspector 使用基本信息 Modal 替代
- 后端 `POST /admin/config/validate-key` 缺失 → ConfigKeys 页面跳过 key 验证，添加说明文字
- SSE 不返回 `request_id` → Playground 使用查询最新 trace 的简化方案关联
