# Farm Manager Phase 3 — React Native 客户端实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为父母辈农民构建一个简单易用的 React Native 原生 App，对接已完成的后端 API，实现种植周期管理、农事日志、成本记账、AI Agent 对话四大功能模块。

**Architecture:** 采用 React Native CLI + TypeScript，底部 Tab 导航组织四大模块，Zustand 管理全局状态，Axios 封装 API 调用，AsyncStorage 本地缓存。UI 遵循"大按钮、大字体、高对比度"原则，适合父母辈操作。

**Tech Stack:** React Native CLI 0.74, TypeScript 5, React Navigation 6, Zustand 4, Axios 1.6, AsyncStorage, dayjs

---

## 文件结构

```
mobile/
  src/
    api/
      client.ts              Axios 实例 + 拦截器
      types.ts               前后端共享类型定义
    stores/
      cycleStore.ts          种植周期状态
      logStore.ts            农事日志状态
      costStore.ts           成本记账状态
      agentStore.ts          Agent 对话/建议状态
    components/
      BigButton.tsx          大按钮（核心交互组件）
      Card.tsx               通用卡片容器
      Timeline.tsx           时间线组件（茬口阶段展示）
      WeatherCard.tsx        天气卡片
      AdviceCard.tsx         AI 建议卡片
      Loading.tsx            加载指示器
      EmptyState.tsx         空状态提示
    screens/
      home/
        HomeScreen.tsx       首页（天气 + 建议 + 快捷入口）
      cycle/
        CycleListScreen.tsx  茬口列表
        CycleDetailScreen.tsx 茬口详情（时间线）
        CycleCreateScreen.tsx 创建茬口
      log/
        LogListScreen.tsx    农事日志列表
        LogCreateScreen.tsx  快速打卡
      cost/
        CostListScreen.tsx   记账列表
        CostCreateScreen.tsx 记账录入
        ProfitScreen.tsx     利润统计
      agent/
        AgentChatScreen.tsx  Agent 对话
        AgentReportScreen.tsx 报告查看
      settings/
        SettingsScreen.tsx   设置/我的
    navigation/
      MainTabNavigator.tsx   底部 Tab 导航
      AppNavigator.tsx       根导航器（Stack）
    theme/
      colors.ts              配色方案
      spacing.ts             间距/字体大小规范
  App.tsx                    应用入口
```

---

## 后端前置修改

### Task 0: 后端 CORS 与天气 API

**Files:**
- Modify: `backend/app/main.py`
- Create: `backend/app/api/weather.py`
- Test: `backend/tests/test_weather_api.py`

- [ ] **Step 1: 添加 CORS 中间件和天气路由**

修改 `backend/app/main.py`：

```python
import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import agent, crop, cycle, log, cost, weather
from app.core.config import settings
from app.core.database import engine, Base


@asynccontextmanager
async def lifespan(app: FastAPI):
    await asyncio.to_thread(Base.metadata.create_all, bind=engine)
    yield


app = FastAPI(title=settings.project_name, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(crop.router)
app.include_router(cycle.router)
app.include_router(log.router)
app.include_router(cost.router)
app.include_router(agent.router)
app.include_router(weather.router)


@app.get("/health")
def health_check():
    return {"status": "ok"}
```

创建 `backend/app/api/weather.py`：

```python
from fastapi import APIRouter

from app.core.config import settings
from app.services.weather_service import fetch_weather

router = APIRouter(prefix="/weather", tags=["weather"])


@router.get("/forecast")
def get_forecast(days: int = 7):
    """获取未来 N 天天气预报原始数据。"""
    data = fetch_weather(
        settings.weather_latitude,
        settings.weather_longitude,
        days=days,
    )
    return data
```

- [ ] **Step 2: 验证后端编译正常**

Run: `cd backend && python -c "from app.main import app; print('OK')"`
Expected: `OK`

- [ ] **Step 3: 提交**

```bash
git add backend/app/main.py backend/app/api/weather.py
git commit -m "feat: add CORS and weather API endpoint for mobile client"
```

---

## React Native 客户端

### Task 1: 项目初始化与依赖安装

**Files:**
- Create: `mobile/` 目录（RN CLI 初始化生成）
- Modify: `mobile/package.json`

- [ ] **Step 1: 初始化 React Native 项目**

Run:
```bash
cd /Users/ljn/Documents/demo/explore
npx react-native@latest init FarmManagerMobile --template react-native-template-typescript
cd FarmManagerMobile
```

Expected: 项目创建成功，`ios/` 和 `android/` 目录存在。

- [ ] **Step 2: 安装导航和状态管理依赖**

Run:
```bash
cd FarmManagerMobile
npm install @react-navigation/native @react-navigation/bottom-tabs @react-navigation/native-stack
npm install react-native-screens react-native-safe-area-context
npm install zustand axios @react-native-async-storage/async-storage dayjs
```

iOS 额外步骤：
```bash
cd ios && pod install && cd ..
```

Expected: `node_modules/` 包含所有包，`ios/Pods` 已安装（macOS）。

- [ ] **Step 3: 创建目录结构**

Run:
```bash
mkdir -p src/{api,stores,components,screens/{home,cycle,log,cost,agent,settings},navigation,theme}
```

- [ ] **Step 4: 提交**

```bash
git add mobile/
git commit -m "chore: init React Native project with dependencies"
```

---

### Task 2: 主题、API 客户端与类型定义

**Files:**
- Create: `mobile/src/theme/colors.ts`
- Create: `mobile/src/theme/spacing.ts`
- Create: `mobile/src/api/types.ts`
- Create: `mobile/src/api/client.ts`

- [ ] **Step 1: 创建主题配色**

`mobile/src/theme/colors.ts`：

```typescript
export const colors = {
  primary: '#2E7D32',
  primaryLight: '#4CAF50',
  primaryDark: '#1B5E20',
  accent: '#F57C00',
  accentLight: '#FF9800',
  background: '#FFFFFF',
  surface: '#F5F5F5',
  border: '#E0E0E0',
  text: '#212121',
  textSecondary: '#757575',
  textInverse: '#FFFFFF',
  success: '#388E3C',
  warning: '#FBC02D',
  danger: '#D32F2F',
  info: '#1976D2',
} as const;
```

`mobile/src/theme/spacing.ts`：

```typescript
export const spacing = {
  xs: 4,
  sm: 8,
  md: 16,
  lg: 24,
  xl: 32,
  xxl: 48,
} as const;

export const fontSize = {
  xs: 12,
  sm: 14,
  md: 16,
  lg: 20,
  xl: 24,
  xxl: 32,
  xxxl: 48,
} as const;

export const borderRadius = {
  sm: 4,
  md: 8,
  lg: 12,
  xl: 16,
  full: 999,
} as const;
```

- [ ] **Step 2: 定义 API 类型**

`mobile/src/api/types.ts`：

```typescript
export interface CropTemplate {
  id: number;
  name: string;
  variety: string | null;
  stages: GrowthStage[];
}

export interface GrowthStage {
  id: number;
  crop_template_id: number;
  name: string;
  duration_days: number;
  order_index: number;
  key_tasks: string | null;
}

export interface CropCycle {
  id: number;
  name: string;
  crop_template_id: number;
  start_date: string;
  field_name: string | null;
  status: string;
  stages: CycleStage[];
}

export interface CycleStage {
  id: number;
  cycle_id: number;
  name: string;
  start_date: string;
  end_date: string;
  order_index: number;
  key_tasks: string | null;
  is_current: boolean;
}

export interface CropCycleListItem {
  id: number;
  name: string;
  crop_template_name: string;
  start_date: string;
  status: string;
  current_stage_name: string | null;
}

export interface FarmLog {
  id: number;
  cycle_id: number;
  operation_type: string;
  operation_date: string;
  operation_time: string | null;
  note: string | null;
  photo_urls: string | null;
  created_at: string;
}

export interface CostRecord {
  id: number;
  cycle_id: number | null;
  record_type: string;
  category: string;
  amount: string;
  record_date: string;
  note: string | null;
}

export interface CycleProfit {
  cycle_id: number;
  total_cost: string;
  total_income: string;
  net_profit: string;
}

export interface ChatMessage {
  role: 'user' | 'agent';
  content: string;
}

export interface ChatRequest {
  cycle_id?: number;
  message: string;
}

export interface ChatResponse {
  reply: string;
}

export interface DailyAdvice {
  cycle_id: number | null;
  advice: string;
  created_at: string;
}

export interface ReportRequest {
  cycle_id?: number;
  report_type: string;
}

export interface ReportResponse {
  cycle_id: number | null;
  report_type: string;
  content: string;
  created_at: string;
}

export interface WeatherForecast {
  daily: {
    time: string[];
    temperature_2m_max: number[];
    temperature_2m_min: number[];
    precipitation_sum: number[];
    windspeed_10m_max: number[];
  };
}
```

- [ ] **Step 3: 创建 API 客户端**

`mobile/src/api/client.ts`：

```typescript
import axios from 'axios';
import AsyncStorage from '@react-native-async-storage/async-storage';

const API_BASE_URL = 'http://localhost:8000';

export const apiClient = axios.create({
  baseURL: API_BASE_URL,
  timeout: 15000,
  headers: {
    'Content-Type': 'application/json',
  },
});

apiClient.interceptors.request.use(async config => {
  return config;
});

apiClient.interceptors.response.use(
  response => response,
  error => {
    if (error.response) {
      const msg = error.response.data?.detail || `请求失败: ${error.response.status}`;
      return Promise.reject(new Error(msg));
    }
    if (error.request) {
      return Promise.reject(new Error('网络连接失败，请检查后重试'));
    }
    return Promise.reject(new Error('请求发生错误'));
  },
);

// 作物模板
export const cropApi = {
  getTemplates: () => apiClient.get('/crops/templates'),
  getTemplate: (id: number) => apiClient.get(`/crops/templates/${id}`),
};

// 种植周期
export const cycleApi = {
  getCycles: () => apiClient.get('/cycles'),
  getCycle: (id: number) => apiClient.get(`/cycles/${id}`),
  createCycle: (data: { name: string; crop_template_id: number; start_date: string; field_name?: string }) =>
    apiClient.post('/cycles', data),
};

// 农事日志
export const logApi = {
  getLogs: (params?: { cycle_id?: number; operation_type?: string }) =>
    apiClient.get('/logs', { params }),
  createLog: (data: { cycle_id: number; operation_type: string; operation_date: string; note?: string }) =>
    apiClient.post('/logs', data),
};

// 成本记账
export const costApi = {
  getRecords: (params?: { cycle_id?: number; category?: string }) =>
    apiClient.get('/costs', { params }),
  createRecord: (data: { cycle_id?: number; record_type: string; category: string; amount: string; record_date: string; note?: string }) =>
    apiClient.post('/costs', data),
  getProfit: (cycleId: number) => apiClient.get(`/costs/cycles/${cycleId}/profit`),
  getYearlySummary: (year: number) => apiClient.get(`/costs/summary/${year}`),
};

// Agent
export const agentApi = {
  chat: (data: { cycle_id?: number; message: string }) => apiClient.post('/agent/chat', data),
  getDailyAdvice: (cycleId?: number) => apiClient.get('/agent/daily', { params: { cycle_id: cycleId } }),
  generateReport: (data: { cycle_id?: number; report_type: string }) =>
    apiClient.post('/agent/report', data),
  getAdviceHistory: (cycleId?: number) =>
    apiClient.get('/agent/advice-history', { params: { cycle_id: cycleId } }),
  getReportHistory: (cycleId?: number) =>
    apiClient.get('/agent/report-history', { params: { cycle_id: cycleId } }),
};

// 天气
export const weatherApi = {
  getForecast: (days: number = 3) => apiClient.get('/weather/forecast', { params: { days } }),
};
```

- [ ] **Step 4: 提交**

```bash
git add mobile/src/theme/ mobile/src/api/
git commit -m "feat: add theme, API types and client"
```

---

### Task 3: 通用 UI 组件

**Files:**
- Create: `mobile/src/components/BigButton.tsx`
- Create: `mobile/src/components/Card.tsx`
- Create: `mobile/src/components/Loading.tsx`
- Create: `mobile/src/components/EmptyState.tsx`

- [ ] **Step 1: BigButton 组件**

`mobile/src/components/BigButton.tsx`：

```typescript
import React from 'react';
import { TouchableOpacity, Text, StyleSheet, ViewStyle, TextStyle } from 'react-native';
import { colors } from '../theme/colors';
import { spacing, fontSize, borderRadius } from '../theme/spacing';

interface BigButtonProps {
  title: string;
  onPress: () => void;
  variant?: 'primary' | 'secondary' | 'danger';
  disabled?: boolean;
  style?: ViewStyle;
}

export const BigButton: React.FC<BigButtonProps> = ({
  title,
  onPress,
  variant = 'primary',
  disabled = false,
  style,
}) => {
  const bgColors = {
    primary: colors.primary,
    secondary: colors.surface,
    danger: colors.danger,
  };

  const textColors = {
    primary: colors.textInverse,
    secondary: colors.text,
    danger: colors.textInverse,
  };

  return (
    <TouchableOpacity
      onPress={onPress}
      disabled={disabled}
      activeOpacity={0.8}
      style={[
        styles.button,
        { backgroundColor: bgColors[variant] },
        disabled && styles.disabled,
        style,
      ]}
    >
      <Text style={[styles.text, { color: textColors[variant] }]}>{title}</Text>
    </TouchableOpacity>
  );
};

const styles = StyleSheet.create({
  button: {
    paddingVertical: spacing.md,
    paddingHorizontal: spacing.lg,
    borderRadius: borderRadius.lg,
    alignItems: 'center',
    justifyContent: 'center',
    minHeight: 56,
    borderWidth: 1,
    borderColor: colors.border,
  },
  text: {
    fontSize: fontSize.lg,
    fontWeight: '600',
  },
  disabled: {
    opacity: 0.5,
  },
});
```

- [ ] **Step 2: Card 和辅助组件**

`mobile/src/components/Card.tsx`：

```typescript
import React from 'react';
import { View, StyleSheet, ViewStyle } from 'react-native';
import { colors } from '../theme/colors';
import { spacing, borderRadius } from '../theme/spacing';

interface CardProps {
  children: React.ReactNode;
  style?: ViewStyle;
  padding?: 'sm' | 'md' | 'lg';
}

export const Card: React.FC<CardProps> = ({ children, style, padding = 'md' }) => {
  const paddingMap = { sm: spacing.sm, md: spacing.md, lg: spacing.lg };
  return (
    <View style={[styles.card, { padding: paddingMap[padding] }, style]}>
      {children}
    </View>
  );
};

const styles = StyleSheet.create({
  card: {
    backgroundColor: colors.surface,
    borderRadius: borderRadius.lg,
    borderWidth: 1,
    borderColor: colors.border,
  },
});
```

`mobile/src/components/Loading.tsx`：

```typescript
import React from 'react';
import { View, ActivityIndicator, Text, StyleSheet } from 'react-native';
import { colors } from '../theme/colors';
import { spacing, fontSize } from '../theme/spacing';

export const Loading: React.FC<{ message?: string }> = ({ message = '加载中...' }) => (
  <View style={styles.container}>
    <ActivityIndicator size="large" color={colors.primary} />
    <Text style={styles.text}>{message}</Text>
  </View>
);

const styles = StyleSheet.create({
  container: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    padding: spacing.lg,
  },
  text: {
    marginTop: spacing.md,
    fontSize: fontSize.md,
    color: colors.textSecondary,
  },
});
```

`mobile/src/components/EmptyState.tsx`：

```typescript
import React from 'react';
import { View, Text, StyleSheet } from 'react-native';
import { colors } from '../theme/colors';
import { spacing, fontSize } from '../theme/spacing';
import { BigButton } from './BigButton';

interface EmptyStateProps {
  title: string;
  subtitle?: string;
  actionLabel?: string;
  onAction?: () => void;
}

export const EmptyState: React.FC<EmptyStateProps> = ({
  title,
  subtitle,
  actionLabel,
  onAction,
}) => (
  <View style={styles.container}>
    <Text style={styles.title}>{title}</Text>
    {subtitle && <Text style={styles.subtitle}>{subtitle}</Text>}
    {actionLabel && onAction && (
      <BigButton title={actionLabel} onPress={onAction} style={styles.button} />
    )}
  </View>
);

const styles = StyleSheet.create({
  container: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    padding: spacing.xl,
  },
  title: {
    fontSize: fontSize.xl,
    fontWeight: '600',
    color: colors.text,
    marginBottom: spacing.sm,
  },
  subtitle: {
    fontSize: fontSize.md,
    color: colors.textSecondary,
    textAlign: 'center',
    marginBottom: spacing.lg,
  },
  button: {
    marginTop: spacing.md,
    minWidth: 160,
  },
});
```

- [ ] **Step 3: 提交**

```bash
git add mobile/src/components/
git commit -m "feat: add common UI components"
```

---

### Task 4: Zustand 状态管理

**Files:**
- Create: `mobile/src/stores/cycleStore.ts`
- Create: `mobile/src/stores/logStore.ts`
- Create: `mobile/src/stores/costStore.ts`
- Create: `mobile/src/stores/agentStore.ts`

- [ ] **Step 1: 种植周期 Store**

`mobile/src/stores/cycleStore.ts`：

```typescript
import { create } from 'zustand';
import type { CropCycle, CropCycleListItem, CropTemplate } from '../api/types';
import { cycleApi, cropApi } from '../api/client';

interface CycleState {
  cycles: CropCycleListItem[];
  currentCycle: CropCycle | null;
  templates: CropTemplate[];
  loading: boolean;
  error: string | null;
  fetchCycles: () => Promise<void>;
  fetchCycleDetail: (id: number) => Promise<void>;
  fetchTemplates: () => Promise<void>;
  createCycle: (data: { name: string; crop_template_id: number; start_date: string; field_name?: string }) => Promise<void>;
  clearError: () => void;
}

export const useCycleStore = create<CycleState>(set => ({
  cycles: [],
  currentCycle: null,
  templates: [],
  loading: false,
  error: null,

  fetchCycles: async () => {
    set({ loading: true, error: null });
    try {
      const res = await cycleApi.getCycles();
      set({ cycles: res.data, loading: false });
    } catch (err: any) {
      set({ error: err.message, loading: false });
    }
  },

  fetchCycleDetail: async (id: number) => {
    set({ loading: true, error: null });
    try {
      const res = await cycleApi.getCycle(id);
      set({ currentCycle: res.data, loading: false });
    } catch (err: any) {
      set({ error: err.message, loading: false });
    }
  },

  fetchTemplates: async () => {
    set({ loading: true, error: null });
    try {
      const res = await cropApi.getTemplates();
      set({ templates: res.data, loading: false });
    } catch (err: any) {
      set({ error: err.message, loading: false });
    }
  },

  createCycle: async data => {
    set({ loading: true, error: null });
    try {
      await cycleApi.createCycle(data);
      const res = await cycleApi.getCycles();
      set({ cycles: res.data, loading: false });
    } catch (err: any) {
      set({ error: err.message, loading: false });
    }
  },

  clearError: () => set({ error: null }),
}));
```

- [ ] **Step 2: 农事日志 Store**

`mobile/src/stores/logStore.ts`：

```typescript
import { create } from 'zustand';
import type { FarmLog } from '../api/types';
import { logApi } from '../api/client';

interface LogState {
  logs: FarmLog[];
  loading: boolean;
  error: string | null;
  fetchLogs: (cycleId?: number) => Promise<void>;
  createLog: (data: { cycle_id: number; operation_type: string; operation_date: string; note?: string }) => Promise<void>;
  clearError: () => void;
}

export const useLogStore = create<LogState>(set => ({
  logs: [],
  loading: false,
  error: null,

  fetchLogs: async cycleId => {
    set({ loading: true, error: null });
    try {
      const res = await logApi.getLogs(cycleId ? { cycle_id: cycleId } : undefined);
      set({ logs: res.data, loading: false });
    } catch (err: any) {
      set({ error: err.message, loading: false });
    }
  },

  createLog: async data => {
    set({ loading: true, error: null });
    try {
      await logApi.createLog(data);
      const res = await logApi.getLogs(data.cycle_id ? { cycle_id: data.cycle_id } : undefined);
      set({ logs: res.data, loading: false });
    } catch (err: any) {
      set({ error: err.message, loading: false });
    }
  },

  clearError: () => set({ error: null }),
}));
```

- [ ] **Step 3: 成本记账 Store**

`mobile/src/stores/costStore.ts`：

```typescript
import { create } from 'zustand';
import type { CostRecord, CycleProfit } from '../api/types';
import { costApi } from '../api/client';

interface CostState {
  records: CostRecord[];
  profit: CycleProfit | null;
  loading: boolean;
  error: string | null;
  fetchRecords: (cycleId?: number) => Promise<void>;
  createRecord: (data: { cycle_id?: number; record_type: string; category: string; amount: string; record_date: string; note?: string }) => Promise<void>;
  fetchProfit: (cycleId: number) => Promise<void>;
  clearError: () => void;
}

export const useCostStore = create<CostState>(set => ({
  records: [],
  profit: null,
  loading: false,
  error: null,

  fetchRecords: async cycleId => {
    set({ loading: true, error: null });
    try {
      const res = await costApi.getRecords(cycleId ? { cycle_id: cycleId } : undefined);
      set({ records: res.data, loading: false });
    } catch (err: any) {
      set({ error: err.message, loading: false });
    }
  },

  createRecord: async data => {
    set({ loading: true, error: null });
    try {
      await costApi.createRecord(data);
      const res = await costApi.getRecords(data.cycle_id ? { cycle_id: data.cycle_id } : undefined);
      set({ records: res.data, loading: false });
    } catch (err: any) {
      set({ error: err.message, loading: false });
    }
  },

  fetchProfit: async cycleId => {
    set({ loading: true, error: null });
    try {
      const res = await costApi.getProfit(cycleId);
      set({ profit: res.data, loading: false });
    } catch (err: any) {
      set({ error: err.message, loading: false });
    }
  },

  clearError: () => set({ error: null }),
}));
```

- [ ] **Step 4: Agent Store**

`mobile/src/stores/agentStore.ts`：

```typescript
import { create } from 'zustand';
import type { ChatMessage, DailyAdvice, ReportResponse } from '../api/types';
import { agentApi, weatherApi } from '../api/client';

interface AgentState {
  messages: ChatMessage[];
  dailyAdvice: DailyAdvice | null;
  report: ReportResponse | null;
  weather: any | null;
  loading: boolean;
  error: string | null;
  sendMessage: (message: string, cycleId?: number) => Promise<void>;
  fetchDailyAdvice: (cycleId?: number) => Promise<void>;
  generateReport: (reportType: string, cycleId?: number) => Promise<void>;
  fetchWeather: () => Promise<void>;
  clearChat: () => void;
  clearError: () => void;
}

export const useAgentStore = create<AgentState>(set => ({
  messages: [],
  dailyAdvice: null,
  report: null,
  weather: null,
  loading: false,
  error: null,

  sendMessage: async (message, cycleId) => {
    set(state => ({
      messages: [...state.messages, { role: 'user', content: message }],
      loading: true,
      error: null,
    }));
    try {
      const res = await agentApi.chat({ message, cycle_id: cycleId });
      set(state => ({
        messages: [...state.messages, { role: 'agent', content: res.data.reply }],
        loading: false,
      }));
    } catch (err: any) {
      set(state => ({
        messages: [...state.messages, { role: 'agent', content: `抱歉，出错了：${err.message}` }],
        loading: false,
      }));
    }
  },

  fetchDailyAdvice: async cycleId => {
    set({ loading: true, error: null });
    try {
      const res = await agentApi.getDailyAdvice(cycleId);
      set({ dailyAdvice: res.data, loading: false });
    } catch (err: any) {
      set({ error: err.message, loading: false });
    }
  },

  generateReport: async (reportType, cycleId) => {
    set({ loading: true, error: null });
    try {
      const res = await agentApi.generateReport({ report_type: reportType, cycle_id: cycleId });
      set({ report: res.data, loading: false });
    } catch (err: any) {
      set({ error: err.message, loading: false });
    }
  },

  fetchWeather: async () => {
    set({ loading: true, error: null });
    try {
      const res = await weatherApi.getForecast(3);
      set({ weather: res.data, loading: false });
    } catch (err: any) {
      set({ error: err.message, loading: false });
    }
  },

  clearChat: () => set({ messages: [] }),
  clearError: () => set({ error: null }),
}));
```

- [ ] **Step 5: 提交**

```bash
git add mobile/src/stores/
git commit -m "feat: add Zustand stores for all modules"
```

---

### Task 5: 导航配置

**Files:**
- Create: `mobile/src/navigation/MainTabNavigator.tsx`
- Create: `mobile/src/navigation/AppNavigator.tsx`
- Modify: `mobile/App.tsx`

- [ ] **Step 1: 底部 Tab 导航**

`mobile/src/navigation/MainTabNavigator.tsx`：

```typescript
import React from 'react';
import { createBottomTabNavigator } from '@react-navigation/bottom-tabs';
import { Text, StyleSheet } from 'react-native';
import { colors } from '../theme/colors';
import { fontSize } from '../theme/spacing';
import { HomeScreen } from '../screens/home/HomeScreen';
import { CycleListScreen } from '../screens/cycle/CycleListScreen';
import { CostListScreen } from '../screens/cost/CostListScreen';
import { SettingsScreen } from '../screens/settings/SettingsScreen';

export type MainTabParamList = {
  Home: undefined;
  Cycles: undefined;
  Costs: undefined;
  Settings: undefined;
};

const Tab = createBottomTabNavigator<MainTabParamList>();

const TabLabel: React.FC<{ label: string; focused: boolean }> = ({ label, focused }) => (
  <Text style={[styles.tabLabel, focused && styles.tabLabelActive]}>{label}</Text>
);

export const MainTabNavigator: React.FC = () => (
  <Tab.Navigator
    screenOptions={{
      headerShown: false,
      tabBarStyle: styles.tabBar,
      tabBarActiveTintColor: colors.primary,
      tabBarInactiveTintColor: colors.textSecondary,
    }}
  >
    <Tab.Screen
      name="Home"
      component={HomeScreen}
      options={{
        tabBarLabel: ({ focused }) => <TabLabel label="首页" focused={focused} />,
      }}
    />
    <Tab.Screen
      name="Cycles"
      component={CycleListScreen}
      options={{
        tabBarLabel: ({ focused }) => <TabLabel label="茬口" focused={focused} />,
      }}
    />
    <Tab.Screen
      name="Costs"
      component={CostListScreen}
      options={{
        tabBarLabel: ({ focused }) => <TabLabel label="记账" focused={focused} />,
      }}
    />
    <Tab.Screen
      name="Settings"
      component={SettingsScreen}
      options={{
        tabBarLabel: ({ focused }) => <TabLabel label="我的" focused={focused} />,
      }}
    />
  </Tab.Navigator>
);

const styles = StyleSheet.create({
  tabBar: {
    height: 64,
    paddingBottom: 8,
    paddingTop: 8,
    borderTopWidth: 1,
    borderTopColor: colors.border,
  },
  tabLabel: {
    fontSize: fontSize.sm,
  },
  tabLabelActive: {
    fontWeight: '600',
    color: colors.primary,
  },
});
```

- [ ] **Step 2: 根 Stack 导航**

`mobile/src/navigation/AppNavigator.tsx`：

```typescript
import React from 'react';
import { NavigationContainer } from '@react-navigation/native';
import { createNativeStackNavigator } from '@react-navigation/native-stack';
import { MainTabNavigator } from './MainTabNavigator';
import { CycleDetailScreen } from '../screens/cycle/CycleDetailScreen';
import { CycleCreateScreen } from '../screens/cycle/CycleCreateScreen';
import { LogListScreen } from '../screens/log/LogListScreen';
import { LogCreateScreen } from '../screens/log/LogCreateScreen';
import { CostCreateScreen } from '../screens/cost/CostCreateScreen';
import { ProfitScreen } from '../screens/cost/ProfitScreen';
import { AgentChatScreen } from '../screens/agent/AgentChatScreen';
import { AgentReportScreen } from '../screens/agent/AgentReportScreen';

export type RootStackParamList = {
  Main: undefined;
  CycleDetail: { cycleId: number };
  CycleCreate: undefined;
  LogList: { cycleId: number };
  LogCreate: { cycleId: number };
  CostCreate: undefined;
  Profit: { cycleId: number };
  AgentChat: { cycleId?: number };
  AgentReport: { cycleId?: number };
};

const Stack = createNativeStackNavigator<RootStackParamList>();

export const AppNavigator: React.FC = () => (
  <NavigationContainer>
    <Stack.Navigator
      screenOptions={{
        headerStyle: { backgroundColor: '#2E7D32' },
        headerTintColor: '#FFFFFF',
        headerTitleStyle: { fontSize: 20, fontWeight: '600' },
      }}
    >
      <Stack.Screen name="Main" component={MainTabNavigator} options={{ headerShown: false }} />
      <Stack.Screen name="CycleDetail" component={CycleDetailScreen} options={{ title: '茬口详情' }} />
      <Stack.Screen name="CycleCreate" component={CycleCreateScreen} options={{ title: '新建茬口' }} />
      <Stack.Screen name="LogList" component={LogListScreen} options={{ title: '农事记录' }} />
      <Stack.Screen name="LogCreate" component={LogCreateScreen} options={{ title: '快速打卡' }} />
      <Stack.Screen name="CostCreate" component={CostCreateScreen} options={{ title: '记一笔' }} />
      <Stack.Screen name="Profit" component={ProfitScreen} options={{ title: '利润统计' }} />
      <Stack.Screen name="AgentChat" component={AgentChatScreen} options={{ title: '农事顾问' }} />
      <Stack.Screen name="AgentReport" component={AgentReportScreen} options={{ title: '种植报告' }} />
    </Stack.Navigator>
  </NavigationContainer>
);
```

- [ ] **Step 3: 修改 App.tsx**

`mobile/App.tsx`：

```typescript
import React from 'react';
import { StatusBar } from 'react-native';
import { AppNavigator } from './src/navigation/AppNavigator';

const App: React.FC = () => (
  <>
    <StatusBar barStyle="light-content" backgroundColor="#1B5E20" />
    <AppNavigator />
  </>
);

export default App;
```

- [ ] **Step 4: 提交**

```bash
git add mobile/src/navigation/ mobile/App.tsx
git commit -m "feat: configure navigation with tab and stack navigators"
```

---

### Task 6: 首页（天气 + 建议 + 快捷入口）

**Files:**
- Create: `mobile/src/components/WeatherCard.tsx`
- Create: `mobile/src/components/AdviceCard.tsx`
- Create: `mobile/src/screens/home/HomeScreen.tsx`

- [ ] **Step 1: WeatherCard 组件**

`mobile/src/components/WeatherCard.tsx`：

```typescript
import React from 'react';
import { View, Text, StyleSheet } from 'react-native';
import { Card } from './Card';
import { colors } from '../theme/colors';
import { spacing, fontSize } from '../theme/spacing';

interface WeatherDay {
  date: string;
  maxTemp: number;
  minTemp: number;
  precipitation: number;
}

interface WeatherCardProps {
  data: {
    daily: {
      time: string[];
      temperature_2m_max: number[];
      temperature_2m_min: number[];
      precipitation_sum: number[];
    };
  } | null;
}

export const WeatherCard: React.FC<WeatherCardProps> = ({ data }) => {
  if (!data?.daily) {
    return (
      <Card>
        <Text style={styles.title}>天气</Text>
        <Text style={styles.empty}>暂无天气数据</Text>
      </Card>
    );
  }

  const { time, temperature_2m_max, temperature_2m_min, precipitation_sum } = data.daily;
  const days: WeatherDay[] = time.slice(0, 3).map((t, i) => ({
    date: t.slice(5),
    maxTemp: temperature_2m_max[i],
    minTemp: temperature_2m_min[i],
    precipitation: precipitation_sum[i],
  }));

  return (
    <Card>
      <Text style={styles.title}>未来3天天气</Text>
      <View style={styles.row}>
        {days.map(d => (
          <View key={d.date} style={styles.dayItem}>
            <Text style={styles.dayDate}>{d.date}</Text>
            <Text style={styles.dayTemp}>
              {d.minTemp}° ~ {d.maxTemp}°
            </Text>
            {d.precipitation > 0 && (
              <Text style={styles.dayRain}>雨 {d.precipitation}mm</Text>
            )}
          </View>
        ))}
      </View>
    </Card>
  );
};

const styles = StyleSheet.create({
  title: {
    fontSize: fontSize.lg,
    fontWeight: '600',
    color: colors.text,
    marginBottom: spacing.md,
  },
  empty: {
    fontSize: fontSize.md,
    color: colors.textSecondary,
  },
  row: {
    flexDirection: 'row',
    justifyContent: 'space-between',
  },
  dayItem: {
    flex: 1,
    alignItems: 'center',
    paddingVertical: spacing.sm,
  },
  dayDate: {
    fontSize: fontSize.md,
    color: colors.textSecondary,
    marginBottom: spacing.xs,
  },
  dayTemp: {
    fontSize: fontSize.lg,
    fontWeight: '600',
    color: colors.text,
  },
  dayRain: {
    fontSize: fontSize.sm,
    color: colors.info,
    marginTop: spacing.xs,
  },
});
```

- [ ] **Step 2: AdviceCard 组件**

`mobile/src/components/AdviceCard.tsx`：

```typescript
import React from 'react';
import { View, Text, StyleSheet } from 'react-native';
import { Card } from './Card';
import { colors } from '../theme/colors';
import { spacing, fontSize } from '../theme/spacing';

interface AdviceCardProps {
  advice: string | null;
  loading?: boolean;
}

export const AdviceCard: React.FC<AdviceCardProps> = ({ advice, loading }) => (
  <Card>
    <Text style={styles.title}>今日农事建议</Text>
    {loading ? (
      <Text style={styles.loading}>获取中...</Text>
    ) : advice ? (
      <Text style={styles.content}>{advice}</Text>
    ) : (
      <Text style={styles.empty}>暂无建议</Text>
    )}
  </Card>
);

const styles = StyleSheet.create({
  title: {
    fontSize: fontSize.lg,
    fontWeight: '600',
    color: colors.text,
    marginBottom: spacing.md,
  },
  content: {
    fontSize: fontSize.md,
    color: colors.text,
    lineHeight: 24,
  },
  loading: {
    fontSize: fontSize.md,
    color: colors.textSecondary,
  },
  empty: {
    fontSize: fontSize.md,
    color: colors.textSecondary,
  },
});
```

- [ ] **Step 3: HomeScreen**

`mobile/src/screens/home/HomeScreen.tsx`：

```typescript
import React, { useEffect } from 'react';
import { View, Text, StyleSheet, ScrollView } from 'react-native';
import { useNavigation } from '@react-navigation/native';
import type { NativeStackNavigationProp } from '@react-navigation/native-stack';
import type { RootStackParamList } from '../../navigation/AppNavigator';
import { useAgentStore } from '../../stores/agentStore';
import { useCycleStore } from '../../stores/cycleStore';
import { WeatherCard } from '../../components/WeatherCard';
import { AdviceCard } from '../../components/AdviceCard';
import { BigButton } from '../../components/BigButton';
import { Loading } from '../../components/Loading';
import { colors } from '../../theme/colors';
import { spacing, fontSize } from '../../theme/spacing';

type NavigationProp = NativeStackNavigationProp<RootStackParamList>;

export const HomeScreen: React.FC = () => {
  const navigation = useNavigation<NavigationProp>();
  const { weather, dailyAdvice, loading, fetchWeather, fetchDailyAdvice } = useAgentStore();
  const { cycles, fetchCycles } = useCycleStore();

  useEffect(() => {
    fetchWeather();
    fetchDailyAdvice();
    fetchCycles();
  }, []);

  if (loading && !weather && !dailyAdvice) {
    return <Loading message="加载中..." />;
  }

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      <Text style={styles.greeting}>农事助手</Text>

      <WeatherCard data={weather} />

      <View style={styles.spacer} />

      <AdviceCard advice={dailyAdvice?.advice || null} loading={loading && !dailyAdvice} />

      <View style={styles.spacer} />

      <Text style={styles.sectionTitle}>快捷操作</Text>
      <View style={styles.actions}>
        <BigButton
          title="咨询农事顾问"
          onPress={() => navigation.navigate('AgentChat')}
          style={styles.actionButton}
        />
        <BigButton
          title="新建茬口"
          variant="secondary"
          onPress={() => navigation.navigate('CycleCreate')}
          style={styles.actionButton}
        />
        <BigButton
          title="记一笔"
          variant="secondary"
          onPress={() => navigation.navigate('CostCreate')}
          style={styles.actionButton}
        />
      </View>

      {cycles.length > 0 && (
        <>
          <View style={styles.spacer} />
          <Text style={styles.sectionTitle}>当前茬口</Text>
          {cycles.slice(0, 3).map(c => (
            <BigButton
              key={c.id}
              title={`${c.name} (${c.current_stage_name || '无阶段'})`}
              variant="secondary"
              onPress={() => navigation.navigate('CycleDetail', { cycleId: c.id })}
              style={styles.cycleButton}
            />
          ))}
        </>
      )}
    </ScrollView>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.background,
  },
  content: {
    padding: spacing.md,
    paddingBottom: spacing.xxl,
  },
  greeting: {
    fontSize: fontSize.xxl,
    fontWeight: '700',
    color: colors.primary,
    marginBottom: spacing.lg,
    marginTop: spacing.sm,
  },
  spacer: {
    height: spacing.md,
  },
  sectionTitle: {
    fontSize: fontSize.lg,
    fontWeight: '600',
    color: colors.text,
    marginBottom: spacing.md,
  },
  actions: {
    gap: spacing.md,
  },
  actionButton: {
    marginBottom: spacing.sm,
  },
  cycleButton: {
    marginBottom: spacing.sm,
  },
});
```

- [ ] **Step 4: 提交**

```bash
git add mobile/src/components/WeatherCard.tsx mobile/src/components/AdviceCard.tsx mobile/src/screens/home/HomeScreen.tsx
git commit -m "feat: add home screen with weather, advice and quick actions"
```

---

### Task 7: 茬口管理页面

**Files:**
- Create: `mobile/src/screens/cycle/CycleListScreen.tsx`
- Create: `mobile/src/screens/cycle/CycleDetailScreen.tsx`
- Create: `mobile/src/screens/cycle/CycleCreateScreen.tsx`
- Create: `mobile/src/components/Timeline.tsx`

- [ ] **Step 1: Timeline 组件**

`mobile/src/components/Timeline.tsx`：

```typescript
import React from 'react';
import { View, Text, StyleSheet } from 'react-native';
import { colors } from '../theme/colors';
import { spacing, fontSize } from '../theme/spacing';

interface TimelineItem {
  id: number;
  title: string;
  subtitle: string;
  dateRange: string;
  isCurrent: boolean;
}

interface TimelineProps {
  items: TimelineItem[];
}

export const Timeline: React.FC<TimelineProps> = ({ items }) => (
  <View style={styles.container}>
    {items.map((item, index) => (
      <View key={item.id} style={styles.row}>
        <View style={styles.leftColumn}>
          <View style={[styles.dot, item.isCurrent && styles.dotActive]} />
          {index < items.length - 1 && <View style={styles.line} />}
        </View>
        <View style={[styles.card, item.isCurrent && styles.cardActive]}>
          <Text style={[styles.title, item.isCurrent && styles.titleActive]}>
            {item.title}
            {item.isCurrent && ' (当前)'}
          </Text>
          <Text style={styles.date}>{item.dateRange}</Text>
          <Text style={styles.subtitle}>{item.subtitle}</Text>
        </View>
      </View>
    ))}
  </View>
);

const styles = StyleSheet.create({
  container: {
    paddingVertical: spacing.sm,
  },
  row: {
    flexDirection: 'row',
  },
  leftColumn: {
    width: 24,
    alignItems: 'center',
  },
  dot: {
    width: 16,
    height: 16,
    borderRadius: 8,
    backgroundColor: colors.border,
    borderWidth: 2,
    borderColor: colors.textSecondary,
  },
  dotActive: {
    backgroundColor: colors.primary,
    borderColor: colors.primaryDark,
    width: 20,
    height: 20,
    borderRadius: 10,
  },
  line: {
    width: 2,
    flex: 1,
    backgroundColor: colors.border,
    marginVertical: 4,
  },
  card: {
    flex: 1,
    marginLeft: spacing.md,
    marginBottom: spacing.lg,
    padding: spacing.md,
    backgroundColor: colors.surface,
    borderRadius: 8,
    borderWidth: 1,
    borderColor: colors.border,
  },
  cardActive: {
    borderColor: colors.primary,
    backgroundColor: '#E8F5E9',
  },
  title: {
    fontSize: fontSize.lg,
    fontWeight: '600',
    color: colors.text,
    marginBottom: spacing.xs,
  },
  titleActive: {
    color: colors.primaryDark,
  },
  date: {
    fontSize: fontSize.sm,
    color: colors.textSecondary,
    marginBottom: spacing.xs,
  },
  subtitle: {
    fontSize: fontSize.md,
    color: colors.text,
  },
});
```

- [ ] **Step 2: 茬口列表页**

`mobile/src/screens/cycle/CycleListScreen.tsx`：

```typescript
import React, { useEffect } from 'react';
import { View, Text, StyleSheet, FlatList, TouchableOpacity } from 'react-native';
import { useNavigation } from '@react-navigation/native';
import type { NativeStackNavigationProp } from '@react-navigation/native-stack';
import type { RootStackParamList } from '../../navigation/AppNavigator';
import { useCycleStore } from '../../stores/cycleStore';
import { Card } from '../../components/Card';
import { BigButton } from '../../components/BigButton';
import { Loading } from '../../components/Loading';
import { EmptyState } from '../../components/EmptyState';
import { colors } from '../../theme/colors';
import { spacing, fontSize } from '../../theme/spacing';

type NavigationProp = NativeStackNavigationProp<RootStackParamList>;

export const CycleListScreen: React.FC = () => {
  const navigation = useNavigation<NavigationProp>();
  const { cycles, loading, fetchCycles } = useCycleStore();

  useEffect(() => {
    const unsubscribe = navigation.addListener('focus', () => {
      fetchCycles();
    });
    return unsubscribe;
  }, [navigation]);

  if (loading && cycles.length === 0) {
    return <Loading />;
  }

  if (cycles.length === 0) {
    return (
      <EmptyState
        title="还没有茬口"
        subtitle="创建第一个种植周期，开始管理农事"
        actionLabel="新建茬口"
        onAction={() => navigation.navigate('CycleCreate')}
      />
    );
  }

  return (
    <View style={styles.container}>
      <FlatList
        data={cycles}
        keyExtractor={item => String(item.id)}
        contentContainerStyle={styles.list}
        renderItem={({ item }) => (
          <TouchableOpacity
            onPress={() => navigation.navigate('CycleDetail', { cycleId: item.id })}
            activeOpacity={0.8}
          >
            <Card style={styles.card}>
              <View style={styles.cardHeader}>
                <Text style={styles.name}>{item.name}</Text>
                <View style={[styles.badge, item.status === 'active' && styles.badgeActive]}>
                  <Text style={styles.badgeText}>
                    {item.status === 'active' ? '进行中' : item.status}
                  </Text>
                </View>
              </View>
              <Text style={styles.info}>作物：{item.crop_template_name}</Text>
              <Text style={styles.info}>开始：{item.start_date}</Text>
              {item.current_stage_name && (
                <Text style={styles.currentStage}>当前阶段：{item.current_stage_name}</Text>
              )}
            </Card>
          </TouchableOpacity>
        )}
        ListFooterComponent={
          <BigButton
            title="+ 新建茬口"
            variant="secondary"
            onPress={() => navigation.navigate('CycleCreate')}
            style={styles.addButton}
          />
        }
      />
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.background,
  },
  list: {
    padding: spacing.md,
    paddingBottom: spacing.xxl,
  },
  card: {
    marginBottom: spacing.md,
  },
  cardHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: spacing.sm,
  },
  name: {
    fontSize: fontSize.xl,
    fontWeight: '600',
    color: colors.text,
  },
  badge: {
    paddingHorizontal: spacing.sm,
    paddingVertical: 4,
    backgroundColor: colors.border,
    borderRadius: 4,
  },
  badgeActive: {
    backgroundColor: '#E8F5E9',
  },
  badgeText: {
    fontSize: fontSize.sm,
    color: colors.textSecondary,
  },
  info: {
    fontSize: fontSize.md,
    color: colors.textSecondary,
    marginBottom: spacing.xs,
  },
  currentStage: {
    fontSize: fontSize.md,
    color: colors.primary,
    fontWeight: '500',
    marginTop: spacing.xs,
  },
  addButton: {
    marginTop: spacing.md,
  },
});
```

- [ ] **Step 3: 茬口详情页**

`mobile/src/screens/cycle/CycleDetailScreen.tsx`：

```typescript
import React, { useEffect } from 'react';
import { View, Text, StyleSheet, ScrollView } from 'react-native';
import { useNavigation, useRoute, type RouteProp } from '@react-navigation/native';
import type { NativeStackNavigationProp } from '@react-navigation/native-stack';
import type { RootStackParamList } from '../../navigation/AppNavigator';
import { useCycleStore } from '../../stores/cycleStore';
import { Timeline } from '../../components/Timeline';
import { BigButton } from '../../components/BigButton';
import { Loading } from '../../components/Loading';
import { colors } from '../../theme/colors';
import { spacing, fontSize } from '../../theme/spacing';

type RouteParams = RouteProp<RootStackParamList, 'CycleDetail'>;
type NavigationProp = NativeStackNavigationProp<RootStackParamList>;

export const CycleDetailScreen: React.FC = () => {
  const route = useRoute<RouteParams>();
  const navigation = useNavigation<NavigationProp>();
  const { cycleId } = route.params;
  const { currentCycle, loading, fetchCycleDetail } = useCycleStore();

  useEffect(() => {
    fetchCycleDetail(cycleId);
  }, [cycleId]);

  if (loading || !currentCycle) {
    return <Loading />;
  }

  const timelineItems = currentCycle.stages.map(stage => ({
    id: stage.id,
    title: stage.name,
    subtitle: stage.key_tasks || '无关键任务',
    dateRange: `${stage.start_date} ~ ${stage.end_date}`,
    isCurrent: stage.is_current,
  }));

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      <View style={styles.header}>
        <Text style={styles.title}>{currentCycle.name}</Text>
        <Text style={styles.subtitle}>地块：{currentCycle.field_name || '未指定'}</Text>
        <Text style={styles.subtitle}>状态：{currentCycle.status}</Text>
        <Text style={styles.subtitle}>开始日期：{currentCycle.start_date}</Text>
      </View>

      <Text style={styles.sectionTitle}>生长阶段</Text>
      <Timeline items={timelineItems} />

      <View style={styles.actions}>
        <BigButton
          title="农事记录"
          onPress={() => navigation.navigate('LogList', { cycleId })}
        />
        <BigButton
          title="利润统计"
          variant="secondary"
          onPress={() => navigation.navigate('Profit', { cycleId })}
        />
        <BigButton
          title="问农事顾问"
          variant="secondary"
          onPress={() => navigation.navigate('AgentChat', { cycleId })}
        />
      </View>
    </ScrollView>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.background,
  },
  content: {
    padding: spacing.md,
    paddingBottom: spacing.xxl,
  },
  header: {
    marginBottom: spacing.lg,
  },
  title: {
    fontSize: fontSize.xxl,
    fontWeight: '700',
    color: colors.primary,
    marginBottom: spacing.sm,
  },
  subtitle: {
    fontSize: fontSize.md,
    color: colors.textSecondary,
    marginBottom: spacing.xs,
  },
  sectionTitle: {
    fontSize: fontSize.xl,
    fontWeight: '600',
    color: colors.text,
    marginBottom: spacing.md,
  },
  actions: {
    gap: spacing.md,
    marginTop: spacing.lg,
  },
});
```

- [ ] **Step 4: 创建茬口页**

`mobile/src/screens/cycle/CycleCreateScreen.tsx`：

```typescript
import React, { useEffect, useState } from 'react';
import { View, Text, TextInput, StyleSheet, ScrollView, Alert } from 'react-native';
import { useNavigation } from '@react-navigation/native';
import type { NativeStackNavigationProp } from '@react-navigation/native-stack';
import type { RootStackParamList } from '../../navigation/AppNavigator';
import { useCycleStore } from '../../stores/cycleStore';
import { BigButton } from '../../components/BigButton';
import { Card } from '../../components/Card';
import { Loading } from '../../components/Loading';
import { colors } from '../../theme/colors';
import { spacing, fontSize } from '../../theme/spacing';

type NavigationProp = NativeStackNavigationProp<RootStackParamList>;

export const CycleCreateScreen: React.FC = () => {
  const navigation = useNavigation<NavigationProp>();
  const { templates, loading, fetchTemplates, createCycle, error, clearError } = useCycleStore();

  const [name, setName] = useState('');
  const [selectedTemplateId, setSelectedTemplateId] = useState<number | null>(null);
  const [startDate, setStartDate] = useState('');
  const [fieldName, setFieldName] = useState('');

  useEffect(() => {
    fetchTemplates();
  }, []);

  useEffect(() => {
    if (error) {
      Alert.alert('错误', error);
      clearError();
    }
  }, [error]);

  const handleSubmit = async () => {
    if (!name.trim() || !selectedTemplateId || !startDate.trim()) {
      Alert.alert('提示', '请填写茬口名称、选择作物模板和开始日期');
      return;
    }
    await createCycle({
      name: name.trim(),
      crop_template_id: selectedTemplateId,
      start_date: startDate.trim(),
      field_name: fieldName.trim() || undefined,
    });
    navigation.goBack();
  };

  if (loading && templates.length === 0) {
    return <Loading />;
  }

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      <Text style={styles.label}>茬口名称</Text>
      <TextInput
        style={styles.input}
        value={name}
        onChangeText={setName}
        placeholder="例如：2024春季西瓜"
        placeholderTextColor={colors.textSecondary}
      />

      <Text style={styles.label}>选择作物</Text>
      <View style={styles.templateList}>
        {templates.map(t => (
          <BigButton
            key={t.id}
            title={`${t.name} ${t.variety || ''}`}
            variant={selectedTemplateId === t.id ? 'primary' : 'secondary'}
            onPress={() => setSelectedTemplateId(t.id)}
            style={styles.templateButton}
          />
        ))}
      </View>

      <Text style={styles.label}>开始日期（YYYY-MM-DD）</Text>
      <TextInput
        style={styles.input}
        value={startDate}
        onChangeText={setStartDate}
        placeholder="2024-03-15"
        placeholderTextColor={colors.textSecondary}
        keyboardType="numbers-and-punctuation"
      />

      <Text style={styles.label}>地块名称（可选）</Text>
      <TextInput
        style={styles.input}
        value={fieldName}
        onChangeText={setFieldName}
        placeholder="例如：东大棚"
        placeholderTextColor={colors.textSecondary}
      />

      <BigButton title="创建茬口" onPress={handleSubmit} style={styles.submitButton} />
    </ScrollView>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.background,
  },
  content: {
    padding: spacing.md,
    paddingBottom: spacing.xxl,
  },
  label: {
    fontSize: fontSize.lg,
    fontWeight: '600',
    color: colors.text,
    marginTop: spacing.lg,
    marginBottom: spacing.sm,
  },
  input: {
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: 8,
    padding: spacing.md,
    fontSize: fontSize.lg,
    backgroundColor: colors.surface,
    color: colors.text,
  },
  templateList: {
    gap: spacing.sm,
  },
  templateButton: {
    marginBottom: spacing.sm,
  },
  submitButton: {
    marginTop: spacing.xl,
  },
});
```

- [ ] **Step 5: 提交**

```bash
git add mobile/src/screens/cycle/ mobile/src/components/Timeline.tsx
git commit -m "feat: add cycle management screens with timeline"
```

---

### Task 8: 农事日志页面

**Files:**
- Create: `mobile/src/screens/log/LogListScreen.tsx`
- Create: `mobile/src/screens/log/LogCreateScreen.tsx`

- [ ] **Step 1: 农事日志列表**

`mobile/src/screens/log/LogListScreen.tsx`：

```typescript
import React, { useEffect } from 'react';
import { View, Text, StyleSheet, FlatList } from 'react-native';
import { useNavigation, useRoute, type RouteProp } from '@react-navigation/native';
import type { NativeStackNavigationProp } from '@react-navigation/native-stack';
import type { RootStackParamList } from '../../navigation/AppNavigator';
import { useLogStore } from '../../stores/logStore';
import { Card } from '../../components/Card';
import { BigButton } from '../../components/BigButton';
import { Loading } from '../../components/Loading';
import { EmptyState } from '../../components/EmptyState';
import { colors } from '../../theme/colors';
import { spacing, fontSize } from '../../theme/spacing';

type RouteParams = RouteProp<RootStackParamList, 'LogList'>;
type NavigationProp = NativeStackNavigationProp<RootStackParamList>;

const OPERATION_LABELS: Record<string, string> = {
  sowing: '播种',
  fertilizing: '施肥',
  watering: '浇水',
  weeding: '除草',
  pest_control: '病虫害防治',
  pruning: '修剪',
  harvesting: '采收',
  other: '其他',
};

export const LogListScreen: React.FC = () => {
  const route = useRoute<RouteParams>();
  const navigation = useNavigation<NavigationProp>();
  const { cycleId } = route.params;
  const { logs, loading, fetchLogs } = useLogStore();

  useEffect(() => {
    fetchLogs(cycleId);
  }, [cycleId]);

  if (loading && logs.length === 0) {
    return <Loading />;
  }

  if (logs.length === 0) {
    return (
      <EmptyState
        title="暂无记录"
        subtitle="记录每一次农事活动"
        actionLabel="添加记录"
        onAction={() => navigation.navigate('LogCreate', { cycleId })}
      />
    );
  }

  return (
    <View style={styles.container}>
      <FlatList
        data={logs}
        keyExtractor={item => String(item.id)}
        contentContainerStyle={styles.list}
        renderItem={({ item }) => (
          <Card style={styles.card}>
            <View style={styles.row}>
              <Text style={styles.type}>
                {OPERATION_LABELS[item.operation_type] || item.operation_type}
              </Text>
              <Text style={styles.date}>{item.operation_date}</Text>
            </View>
            {item.note && <Text style={styles.note}>{item.note}</Text>}
          </Card>
        )}
        ListFooterComponent={
          <BigButton
            title="+ 添加记录"
            variant="secondary"
            onPress={() => navigation.navigate('LogCreate', { cycleId })}
            style={styles.addButton}
          />
        }
      />
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.background,
  },
  list: {
    padding: spacing.md,
    paddingBottom: spacing.xxl,
  },
  card: {
    marginBottom: spacing.md,
  },
  row: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: spacing.sm,
  },
  type: {
    fontSize: fontSize.lg,
    fontWeight: '600',
    color: colors.primary,
  },
  date: {
    fontSize: fontSize.md,
    color: colors.textSecondary,
  },
  note: {
    fontSize: fontSize.md,
    color: colors.text,
  },
  addButton: {
    marginTop: spacing.md,
  },
});
```

- [ ] **Step 2: 快速打卡页**

`mobile/src/screens/log/LogCreateScreen.tsx`：

```typescript
import React, { useState } from 'react';
import { View, Text, TextInput, StyleSheet, ScrollView, Alert } from 'react-native';
import { useNavigation, useRoute, type RouteProp } from '@react-navigation/native';
import type { NativeStackNavigationProp } from '@react-navigation/native-stack';
import type { RootStackParamList } from '../../navigation/AppNavigator';
import { useLogStore } from '../../stores/logStore';
import { BigButton } from '../../components/BigButton';
import { Card } from '../../components/Card';
import { colors } from '../../theme/colors';
import { spacing, fontSize } from '../../theme/spacing';
import dayjs from 'dayjs';

type RouteParams = RouteProp<RootStackParamList, 'LogCreate'>;
type NavigationProp = NativeStackNavigationProp<RootStackParamList>;

const QUICK_ACTIONS = [
  { key: 'watering', label: '浇水' },
  { key: 'fertilizing', label: '施肥' },
  { key: 'weeding', label: '除草' },
  { key: 'pest_control', label: '打药' },
  { key: 'pruning', label: '修剪' },
  { key: 'harvesting', label: '采收' },
  { key: 'other', label: '其他' },
];

export const LogCreateScreen: React.FC = () => {
  const route = useRoute<RouteParams>();
  const navigation = useNavigation<NavigationProp>();
  const { cycleId } = route.params;
  const { createLog, error, clearError } = useLogStore();

  const [selectedType, setSelectedType] = useState('');
  const [note, setNote] = useState('');
  const today = dayjs().format('YYYY-MM-DD');

  const handleSubmit = async () => {
    if (!selectedType) {
      Alert.alert('提示', '请选择农事类型');
      return;
    }
    await createLog({
      cycle_id: cycleId,
      operation_type: selectedType,
      operation_date: today,
      note: note.trim() || undefined,
    });
    if (!error) {
      navigation.goBack();
    } else {
      Alert.alert('错误', error);
      clearError();
    }
  };

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      <Text style={styles.dateLabel}>日期：{today}</Text>

      <Text style={styles.label}>选择农事类型</Text>
      <View style={styles.actionsGrid}>
        {QUICK_ACTIONS.map(action => (
          <View key={action.key} style={styles.actionWrapper}>
            <BigButton
              title={action.label}
              variant={selectedType === action.key ? 'primary' : 'secondary'}
              onPress={() => setSelectedType(action.key)}
            />
          </View>
        ))}
      </View>

      <Text style={styles.label}>备注（可选）</Text>
      <TextInput
        style={[styles.input, styles.textArea]}
        value={note}
        onChangeText={setNote}
        placeholder="补充说明..."
        placeholderTextColor={colors.textSecondary}
        multiline
        numberOfLines={3}
      />

      <BigButton title="确认打卡" onPress={handleSubmit} style={styles.submitButton} />
    </ScrollView>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.background,
  },
  content: {
    padding: spacing.md,
    paddingBottom: spacing.xxl,
  },
  dateLabel: {
    fontSize: fontSize.lg,
    color: colors.textSecondary,
    marginBottom: spacing.md,
  },
  label: {
    fontSize: fontSize.lg,
    fontWeight: '600',
    color: colors.text,
    marginTop: spacing.lg,
    marginBottom: spacing.md,
  },
  actionsGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    marginHorizontal: -spacing.sm,
  },
  actionWrapper: {
    width: '50%',
    padding: spacing.sm,
  },
  input: {
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: 8,
    padding: spacing.md,
    fontSize: fontSize.lg,
    backgroundColor: colors.surface,
    color: colors.text,
  },
  textArea: {
    height: 100,
    textAlignVertical: 'top',
  },
  submitButton: {
    marginTop: spacing.xl,
  },
});
```

- [ ] **Step 3: 提交**

```bash
git add mobile/src/screens/log/
git commit -m "feat: add farm log list and quick-create screen"
```

---

### Task 9: 成本记账页面

**Files:**
- Create: `mobile/src/screens/cost/CostListScreen.tsx`
- Create: `mobile/src/screens/cost/CostCreateScreen.tsx`
- Create: `mobile/src/screens/cost/ProfitScreen.tsx`

- [ ] **Step 1: 记账列表**

`mobile/src/screens/cost/CostListScreen.tsx`：

```typescript
import React, { useEffect } from 'react';
import { View, Text, StyleSheet, FlatList, TouchableOpacity } from 'react-native';
import { useNavigation } from '@react-navigation/native';
import type { NativeStackNavigationProp } from '@react-navigation/native-stack';
import type { RootStackParamList } from '../../navigation/AppNavigator';
import { useCostStore } from '../../stores/costStore';
import { Card } from '../../components/Card';
import { BigButton } from '../../components/BigButton';
import { Loading } from '../../components/Loading';
import { EmptyState } from '../../components/EmptyState';
import { colors } from '../../theme/colors';
import { spacing, fontSize } from '../../theme/spacing';

type NavigationProp = NativeStackNavigationProp<RootStackParamList>;

const TYPE_LABELS: Record<string, string> = {
  cost: '支出',
  income: '收入',
};

const TYPE_COLORS: Record<string, string> = {
  cost: colors.danger,
  income: colors.success,
};

export const CostListScreen: React.FC = () => {
  const navigation = useNavigation<NavigationProp>();
  const { records, loading, fetchRecords } = useCostStore();

  useEffect(() => {
    const unsubscribe = navigation.addListener('focus', () => {
      fetchRecords();
    });
    return unsubscribe;
  }, [navigation]);

  if (loading && records.length === 0) {
    return <Loading />;
  }

  if (records.length === 0) {
    return (
      <EmptyState
        title="暂无账目"
        subtitle="记录每一笔投入和收入"
        actionLabel="记一笔"
        onAction={() => navigation.navigate('CostCreate')}
      />
    );
  }

  return (
    <View style={styles.container}>
      <FlatList
        data={records}
        keyExtractor={item => String(item.id)}
        contentContainerStyle={styles.list}
        renderItem={({ item }) => (
          <Card style={styles.card}>
            <View style={styles.row}>
              <View style={styles.left}>
                <Text style={styles.category}>{item.category}</Text>
                <Text style={styles.date}>{item.record_date}</Text>
                {item.note && <Text style={styles.note}>{item.note}</Text>}
              </View>
              <View style={styles.right}>
                <Text style={[styles.amount, { color: TYPE_COLORS[item.record_type] || colors.text }]}>
                  {item.record_type === 'cost' ? '-' : '+'}{item.amount} 元
                </Text>
                <View style={[styles.badge, { backgroundColor: TYPE_COLORS[item.record_type] || colors.border }]}>
                  <Text style={styles.badgeText}>{TYPE_LABELS[item.record_type] || item.record_type}</Text>
                </View>
              </View>
            </View>
          </Card>
        )}
        ListFooterComponent={
          <BigButton
            title="+ 记一笔"
            variant="secondary"
            onPress={() => navigation.navigate('CostCreate')}
            style={styles.addButton}
          />
        }
      />
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.background,
  },
  list: {
    padding: spacing.md,
    paddingBottom: spacing.xxl,
  },
  card: {
    marginBottom: spacing.md,
  },
  row: {
    flexDirection: 'row',
    justifyContent: 'space-between',
  },
  left: {
    flex: 1,
  },
  right: {
    alignItems: 'flex-end',
  },
  category: {
    fontSize: fontSize.lg,
    fontWeight: '600',
    color: colors.text,
    marginBottom: spacing.xs,
  },
  date: {
    fontSize: fontSize.sm,
    color: colors.textSecondary,
    marginBottom: spacing.xs,
  },
  note: {
    fontSize: fontSize.md,
    color: colors.textSecondary,
  },
  amount: {
    fontSize: fontSize.xl,
    fontWeight: '700',
    marginBottom: spacing.xs,
  },
  badge: {
    paddingHorizontal: spacing.sm,
    paddingVertical: 2,
    borderRadius: 4,
  },
  badgeText: {
    fontSize: fontSize.sm,
    color: colors.textInverse,
  },
  addButton: {
    marginTop: spacing.md,
  },
});
```

- [ ] **Step 2: 记账录入页**

`mobile/src/screens/cost/CostCreateScreen.tsx`：

```typescript
import React, { useState } from 'react';
import { View, Text, TextInput, StyleSheet, ScrollView, Alert } from 'react-native';
import { useNavigation } from '@react-navigation/native';
import type { NativeStackNavigationProp } from '@react-navigation/native-stack';
import type { RootStackParamList } from '../../navigation/AppNavigator';
import { useCostStore } from '../../stores/costStore';
import { BigButton } from '../../components/BigButton';
import { colors } from '../../theme/colors';
import { spacing, fontSize } from '../../theme/spacing';
import dayjs from 'dayjs';

type NavigationProp = NativeStackNavigationProp<RootStackParamList>;

const COST_CATEGORIES = ['种子', '化肥', '农药', '人工', '水电', '地租', '其他'];
const INCOME_CATEGORIES = ['销售', '补贴', '其他'];

export const CostCreateScreen: React.FC = () => {
  const navigation = useNavigation<NavigationProp>();
  const { createRecord, error, clearError } = useCostStore();

  const [recordType, setRecordType] = useState<'cost' | 'income'>('cost');
  const [category, setCategory] = useState('');
  const [amount, setAmount] = useState('');
  const [recordDate, setRecordDate] = useState(dayjs().format('YYYY-MM-DD'));
  const [note, setNote] = useState('');

  const categories = recordType === 'cost' ? COST_CATEGORIES : INCOME_CATEGORIES;

  const handleSubmit = async () => {
    if (!category || !amount || !recordDate) {
      Alert.alert('提示', '请填写类型、金额和日期');
      return;
    }
    const numAmount = parseFloat(amount);
    if (isNaN(numAmount) || numAmount <= 0) {
      Alert.alert('提示', '金额必须大于0');
      return;
    }
    await createRecord({
      record_type: recordType,
      category,
      amount: numAmount.toFixed(2),
      record_date: recordDate,
      note: note.trim() || undefined,
    });
    if (!error) {
      navigation.goBack();
    } else {
      Alert.alert('错误', error);
      clearError();
    }
  };

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      <Text style={styles.label}>收支类型</Text>
      <View style={styles.typeRow}>
        <BigButton
          title="支出"
          variant={recordType === 'cost' ? 'danger' : 'secondary'}
          onPress={() => { setRecordType('cost'); setCategory(''); }}
          style={styles.typeButton}
        />
        <BigButton
          title="收入"
          variant={recordType === 'income' ? 'primary' : 'secondary'}
          onPress={() => { setRecordType('income'); setCategory(''); }}
          style={styles.typeButton}
        />
      </View>

      <Text style={styles.label}>分类</Text>
      <View style={styles.categoryGrid}>
        {categories.map(c => (
          <View key={c} style={styles.categoryWrapper}>
            <BigButton
              title={c}
              variant={category === c ? 'primary' : 'secondary'}
              onPress={() => setCategory(c)}
            />
          </View>
        ))}
      </View>

      <Text style={styles.label}>金额（元）</Text>
      <TextInput
        style={styles.input}
        value={amount}
        onChangeText={setAmount}
        placeholder="0.00"
        placeholderTextColor={colors.textSecondary}
        keyboardType="decimal-pad"
      />

      <Text style={styles.label}>日期</Text>
      <TextInput
        style={styles.input}
        value={recordDate}
        onChangeText={setRecordDate}
        placeholder="YYYY-MM-DD"
        placeholderTextColor={colors.textSecondary}
      />

      <Text style={styles.label}>备注（可选）</Text>
      <TextInput
        style={[styles.input, styles.textArea]}
        value={note}
        onChangeText={setNote}
        placeholder="补充说明..."
        placeholderTextColor={colors.textSecondary}
        multiline
        numberOfLines={2}
      />

      <BigButton title="保存" onPress={handleSubmit} style={styles.submitButton} />
    </ScrollView>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.background,
  },
  content: {
    padding: spacing.md,
    paddingBottom: spacing.xxl,
  },
  label: {
    fontSize: fontSize.lg,
    fontWeight: '600',
    color: colors.text,
    marginTop: spacing.lg,
    marginBottom: spacing.md,
  },
  typeRow: {
    flexDirection: 'row',
    gap: spacing.md,
  },
  typeButton: {
    flex: 1,
  },
  categoryGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    marginHorizontal: -spacing.sm,
  },
  categoryWrapper: {
    width: '33.33%',
    padding: spacing.sm,
  },
  input: {
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: 8,
    padding: spacing.md,
    fontSize: fontSize.lg,
    backgroundColor: colors.surface,
    color: colors.text,
  },
  textArea: {
    height: 80,
    textAlignVertical: 'top',
  },
  submitButton: {
    marginTop: spacing.xl,
  },
});
```

- [ ] **Step 3: 利润统计页**

`mobile/src/screens/cost/ProfitScreen.tsx`：

```typescript
import React, { useEffect } from 'react';
import { View, Text, StyleSheet, ScrollView } from 'react-native';
import { useRoute, type RouteProp } from '@react-navigation/native';
import type { RootStackParamList } from '../../navigation/AppNavigator';
import { useCostStore } from '../../stores/costStore';
import { Card } from '../../components/Card';
import { Loading } from '../../components/Loading';
import { colors } from '../../theme/colors';
import { spacing, fontSize } from '../../theme/spacing';

type RouteParams = RouteProp<RootStackParamList, 'Profit'>;

export const ProfitScreen: React.FC = () => {
  const route = useRoute<RouteParams>();
  const { cycleId } = route.params;
  const { profit, loading, fetchProfit } = useCostStore();

  useEffect(() => {
    fetchProfit(cycleId);
  }, [cycleId]);

  if (loading || !profit) {
    return <Loading />;
  }

  const net = parseFloat(profit.net_profit);
  const isProfit = net >= 0;

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      <Card style={styles.summaryCard}>
        <Text style={styles.summaryLabel}>净利润</Text>
        <Text style={[styles.summaryValue, { color: isProfit ? colors.success : colors.danger }]}>
          {isProfit ? '+' : ''}{profit.net_profit} 元
        </Text>
      </Card>

      <View style={styles.spacer} />

      <Card>
        <View style={styles.row}>
          <Text style={styles.rowLabel}>总成本</Text>
          <Text style={[styles.rowValue, { color: colors.danger }]}>-{profit.total_cost} 元</Text>
        </View>
        <View style={[styles.row, styles.rowBorder]}>
          <Text style={styles.rowLabel}>总收入</Text>
          <Text style={[styles.rowValue, { color: colors.success }]}>+{profit.total_income} 元</Text>
        </View>
      </Card>
    </ScrollView>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.background,
  },
  content: {
    padding: spacing.md,
    paddingBottom: spacing.xxl,
  },
  summaryCard: {
    alignItems: 'center',
    paddingVertical: spacing.xl,
  },
  summaryLabel: {
    fontSize: fontSize.lg,
    color: colors.textSecondary,
    marginBottom: spacing.sm,
  },
  summaryValue: {
    fontSize: fontSize.xxxl,
    fontWeight: '700',
  },
  spacer: {
    height: spacing.md,
  },
  row: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingVertical: spacing.md,
  },
  rowBorder: {
    borderTopWidth: 1,
    borderTopColor: colors.border,
  },
  rowLabel: {
    fontSize: fontSize.lg,
    color: colors.text,
  },
  rowValue: {
    fontSize: fontSize.xl,
    fontWeight: '600',
  },
});
```

- [ ] **Step 4: 提交**

```bash
git add mobile/src/screens/cost/
git commit -m "feat: add cost accounting screens with profit view"
```

---

### Task 10: Agent 页面

**Files:**
- Create: `mobile/src/screens/agent/AgentChatScreen.tsx`
- Create: `mobile/src/screens/agent/AgentReportScreen.tsx`

- [ ] **Step 1: Agent 对话页**

`mobile/src/screens/agent/AgentChatScreen.tsx`：

```typescript
import React, { useState, useRef, useEffect } from 'react';
import {
  View,
  Text,
  TextInput,
  StyleSheet,
  FlatList,
  KeyboardAvoidingView,
  Platform,
  TouchableOpacity,
} from 'react-native';
import { useRoute, type RouteProp } from '@react-navigation/native';
import type { RootStackParamList } from '../../navigation/AppNavigator';
import { useAgentStore } from '../../stores/agentStore';
import { Card } from '../../components/Card';
import { Loading } from '../../components/Loading';
import { colors } from '../../theme/colors';
import { spacing, fontSize } from '../../theme/spacing';

type RouteParams = RouteProp<RootStackParamList, 'AgentChat'>;

export const AgentChatScreen: React.FC = () => {
  const route = useRoute<RouteParams>();
  const cycleId = route.params?.cycleId;
  const { messages, loading, sendMessage, clearChat } = useAgentStore();
  const [input, setInput] = useState('');
  const flatListRef = useRef<FlatList>(null);

  useEffect(() => {
    clearChat();
  }, []);

  const handleSend = async () => {
    const text = input.trim();
    if (!text || loading) return;
    setInput('');
    await sendMessage(text, cycleId);
  };

  const renderMessage = ({ item }: { item: { role: string; content: string } }) => (
    <View style={[styles.messageRow, item.role === 'user' && styles.userRow]}>
      <Card
        style={[
          styles.messageCard,
          item.role === 'user' ? styles.userCard : styles.agentCard,
        ]}
        padding="sm"
      >
        <Text style={[styles.messageText, item.role === 'user' && styles.userText]}>
          {item.content}
        </Text>
      </Card>
    </View>
  );

  return (
    <KeyboardAvoidingView
      style={styles.container}
      behavior={Platform.OS === 'ios' ? 'padding' : undefined}
      keyboardVerticalOffset={Platform.OS === 'ios' ? 90 : 0}
    >
      <FlatList
        ref={flatListRef}
        data={messages}
        keyExtractor={(_, i) => String(i)}
        renderItem={renderMessage}
        contentContainerStyle={styles.messagesList}
        onContentSizeChange={() => flatListRef.current?.scrollToEnd({ animated: true })}
      />

      {loading && messages.length > 0 && messages[messages.length - 1].role === 'user' && (
        <View style={styles.typing}>
          <Text style={styles.typingText}>农事顾问思考中...</Text>
        </View>
      )}

      <View style={styles.inputBar}>
        <TextInput
          style={styles.input}
          value={input}
          onChangeText={setInput}
          placeholder="输入问题..."
          placeholderTextColor={colors.textSecondary}
          multiline
          maxLength={500}
        />
        <TouchableOpacity
          onPress={handleSend}
          disabled={loading || !input.trim()}
          style={[styles.sendButton, (!input.trim() || loading) && styles.sendButtonDisabled]}
        >
          <Text style={styles.sendButtonText}>发送</Text>
        </TouchableOpacity>
      </View>
    </KeyboardAvoidingView>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.background,
  },
  messagesList: {
    padding: spacing.md,
    paddingBottom: spacing.lg,
  },
  messageRow: {
    marginBottom: spacing.md,
    alignItems: 'flex-start',
  },
  userRow: {
    alignItems: 'flex-end',
  },
  messageCard: {
    maxWidth: '85%',
  },
  userCard: {
    backgroundColor: colors.primary,
  },
  agentCard: {
    backgroundColor: colors.surface,
  },
  messageText: {
    fontSize: fontSize.md,
    color: colors.text,
    lineHeight: 22,
  },
  userText: {
    color: colors.textInverse,
  },
  typing: {
    paddingHorizontal: spacing.md,
    paddingBottom: spacing.sm,
  },
  typingText: {
    fontSize: fontSize.sm,
    color: colors.textSecondary,
  },
  inputBar: {
    flexDirection: 'row',
    padding: spacing.md,
    borderTopWidth: 1,
    borderTopColor: colors.border,
    backgroundColor: colors.surface,
    alignItems: 'flex-end',
  },
  input: {
    flex: 1,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: 20,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    fontSize: fontSize.md,
    backgroundColor: colors.background,
    color: colors.text,
    maxHeight: 100,
    marginRight: spacing.sm,
  },
  sendButton: {
    backgroundColor: colors.primary,
    borderRadius: 20,
    paddingHorizontal: spacing.lg,
    paddingVertical: spacing.sm,
    justifyContent: 'center',
  },
  sendButtonDisabled: {
    backgroundColor: colors.border,
  },
  sendButtonText: {
    color: colors.textInverse,
    fontSize: fontSize.md,
    fontWeight: '600',
  },
});
```

- [ ] **Step 2: 报告查看页**

`mobile/src/screens/agent/AgentReportScreen.tsx`：

```typescript
import React, { useState } from 'react';
import { View, Text, StyleSheet, ScrollView } from 'react-native';
import { useRoute, type RouteProp } from '@react-navigation/native';
import type { RootStackParamList } from '../../navigation/AppNavigator';
import { useAgentStore } from '../../stores/agentStore';
import { Card } from '../../components/Card';
import { BigButton } from '../../components/BigButton';
import { Loading } from '../../components/Loading';
import { colors } from '../../theme/colors';
import { spacing, fontSize } from '../../theme/spacing';

type RouteParams = RouteProp<RootStackParamList, 'AgentReport'>;

export const AgentReportScreen: React.FC = () => {
  const route = useRoute<RouteParams>();
  const cycleId = route.params?.cycleId;
  const { report, loading, generateReport } = useAgentStore();
  const [reportType, setReportType] = useState('weekly');

  const handleGenerate = () => {
    generateReport(reportType, cycleId);
  };

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      <View style={styles.typeSelector}>
        <BigButton
          title="周报"
          variant={reportType === 'weekly' ? 'primary' : 'secondary'}
          onPress={() => setReportType('weekly')}
          style={styles.typeButton}
        />
        <BigButton
          title="月报"
          variant={reportType === 'monthly' ? 'primary' : 'secondary'}
          onPress={() => setReportType('monthly')}
          style={styles.typeButton}
        />
      </View>

      <BigButton
        title="生成报告"
        onPress={handleGenerate}
        disabled={loading}
        style={styles.generateButton}
      />

      {loading && <Loading message="AI 正在生成报告..." />}

      {report && !loading && (
        <Card style={styles.reportCard}>
          <Text style={styles.reportTitle}>
            {report.report_type === 'weekly' ? '周报告' : '月报告'}
            {' '}· {report.created_at.slice(0, 10)}
          </Text>
          <Text style={styles.reportContent}>{report.content}</Text>
        </Card>
      )}
    </ScrollView>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.background,
  },
  content: {
    padding: spacing.md,
    paddingBottom: spacing.xxl,
  },
  typeSelector: {
    flexDirection: 'row',
    gap: spacing.md,
    marginBottom: spacing.md,
  },
  typeButton: {
    flex: 1,
  },
  generateButton: {
    marginBottom: spacing.lg,
  },
  reportCard: {
    marginTop: spacing.md,
  },
  reportTitle: {
    fontSize: fontSize.lg,
    fontWeight: '600',
    color: colors.primary,
    marginBottom: spacing.md,
  },
  reportContent: {
    fontSize: fontSize.md,
    color: colors.text,
    lineHeight: 24,
  },
});
```

- [ ] **Step 3: 提交**

```bash
git add mobile/src/screens/agent/
git commit -m "feat: add AI agent chat and report screens"
```

---

### Task 11: 设置页面与最终整合

**Files:**
- Create: `mobile/src/screens/settings/SettingsScreen.tsx`
- Modify: `mobile/package.json`（如有需要添加 scripts）

- [ ] **Step 1: 设置页**

`mobile/src/screens/settings/SettingsScreen.tsx`：

```typescript
import React from 'react';
import { View, Text, StyleSheet, ScrollView, Linking } from 'react-native';
import { useNavigation } from '@react-navigation/native';
import type { NativeStackNavigationProp } from '@react-navigation/native-stack';
import type { RootStackParamList } from '../../navigation/AppNavigator';
import { Card } from '../../components/Card';
import { BigButton } from '../../components/BigButton';
import { colors } from '../../theme/colors';
import { spacing, fontSize } from '../../theme/spacing';

type NavigationProp = NativeStackNavigationProp<RootStackParamList>;

export const SettingsScreen: React.FC = () => {
  const navigation = useNavigation<NavigationProp>();

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      <Text style={styles.greeting}>我的</Text>

      <Card style={styles.section}>
        <Text style={styles.sectionTitle}>AI 功能</Text>
        <BigButton
          title="农事顾问对话"
          variant="secondary"
          onPress={() => navigation.navigate('AgentChat')}
          style={styles.menuButton}
        />
        <BigButton
          title="生成种植报告"
          variant="secondary"
          onPress={() => navigation.navigate('AgentReport')}
          style={styles.menuButton}
        />
      </Card>

      <View style={styles.spacer} />

      <Card style={styles.section}>
        <Text style={styles.sectionTitle}>关于</Text>
        <Text style={styles.version}>农事助手 v1.0</Text>
        <Text style={styles.desc}>为父母辈农民设计的种植管理工具</Text>
      </Card>
    </ScrollView>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.background,
  },
  content: {
    padding: spacing.md,
    paddingBottom: spacing.xxl,
  },
  greeting: {
    fontSize: fontSize.xxl,
    fontWeight: '700',
    color: colors.primary,
    marginBottom: spacing.lg,
    marginTop: spacing.sm,
  },
  section: {
    marginBottom: spacing.md,
  },
  sectionTitle: {
    fontSize: fontSize.lg,
    fontWeight: '600',
    color: colors.text,
    marginBottom: spacing.md,
  },
  menuButton: {
    marginBottom: spacing.sm,
  },
  spacer: {
    height: spacing.md,
  },
  version: {
    fontSize: fontSize.md,
    color: colors.textSecondary,
    marginBottom: spacing.xs,
  },
  desc: {
    fontSize: fontSize.sm,
    color: colors.textSecondary,
  },
});
```

- [ ] **Step 2: 验证 Metro 编译**

Run: `cd mobile && npx react-native start --reset-cache`（后台）
然后 Run: `cd mobile && npx react-native run-ios --simulator="iPhone 15"` 或 `npx react-native run-android`

Expected: App 成功启动，底部 Tab 导航正常显示，四个 Tab 可切换。

- [ ] **Step 3: 提交**

```bash
git add mobile/src/screens/settings/
git commit -m "feat: add settings screen and complete phase 3 UI"
```

---

## Self-Review

**1. Spec coverage:**
- ✅ 首页：天气卡片 + 建议 + 快捷入口
- ✅ 茬口管理：列表 + 详情（时间线）+ 创建
- ✅ 农事日志：列表 + 快速打卡
- ✅ 成本记账：列表 + 录入 + 利润统计
- ✅ Agent：对话 + 报告
- ✅ 设置/我的页面
- ✅ 大按钮、大字体、高对比度设计
- ✅ 后端 CORS 和天气 API 前置支持

**2. Placeholder scan:** 无 TBD/TODO/"implement later"。

**3. Type consistency:** 所有类型引用（CycleStageResponse、FarmLog 等）与后端 schema 一致。navigation param 类型在 AppNavigator 和各个 screen 中一致。
