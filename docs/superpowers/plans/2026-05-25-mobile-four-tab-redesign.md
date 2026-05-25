# 移动端四 Tab 全面改版 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 重构移动端四个 Tab 页面的功能和布局，添加每日建议缓存、报告历史、用户设置页，优化 API 成本和用户体验。

**Architecture:** 后端在现有 `AdviceRecord` 模型基础上添加缓存查询逻辑，前端 AI 助手 Tab 新增 SegmentedControl 切换对话/报告视图，"我的"页面从 AI 入口改为用户设置。

**Tech Stack:** FastAPI + SQLAlchemy（后端），React Native + Zustand + TypeScript（移动端），AsyncStorage（持久化）

---

## File Structure

### 后端新增/修改

| 文件 | 操作 | 职责 |
|------|------|------|
| `backend/app/services/agent_service.py` | 修改 | `get_daily_advice()` 添加缓存查询，新增 `refresh_daily_advice()` |
| `backend/app/api/agent.py` | 修改 | 新增 `POST /agent/daily/refresh`、`GET /agent/reports` 端点 |
| `backend/app/schemas/agent.py` | 修改 | 新增 `ReportListResponse` schema |
| `backend/tests/test_advice_cache.py` | 新增 | 缓存逻辑单元测试 |
| `backend/tests/test_report_api.py` | 新增 | 报告列表 API 测试 |

### 移动端新增/修改

| 文件 | 操作 | 职责 |
|------|------|------|
| `FarmManagerMobile/src/stores/agentStore.ts` | 修改 | 新增 `refreshDailyAdvice`、`reports`、`fetchReports` |
| `FarmManagerMobile/src/stores/settingsStore.ts` | 新增 | 用户设置 store（城市/农场/作物偏好） |
| `FarmManagerMobile/src/api/client.ts` | 修改 | 新增 `refreshAdvice`、`getReportHistory` API 调用 |
| `FarmManagerMobile/src/api/types.ts` | 修改 | 新增 `ReportListItem` 类型 |
| `FarmManagerMobile/src/components/AdviceCard.tsx` | 修改 | 添加刷新按钮 |
| `FarmManagerMobile/src/screens/agent/AgentChatScreen.tsx` | 修改 | 添加 SegmentedControl + 报告视图 |
| `FarmManagerMobile/src/screens/agent/AgentReportScreen.tsx` | 修改 | `<Text>` 替换为 `<MarkdownText>`，支持从历史列表查看 |
| `FarmManagerMobile/src/screens/settings/SettingsScreen.tsx` | 修改 | 完全重写为用户设置页 |

---

## Task 1: 后端 — 每日建议缓存逻辑

**Files:**
- Modify: `backend/app/services/agent_service.py`
- Test: `backend/tests/test_advice_cache.py`

- [ ] **Step 1: 编写缓存查询失败的测试**

```python
# backend/tests/test_advice_cache.py
"""每日建议缓存逻辑测试。"""

from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.agent import AdviceRecord
from app.core.database import Base


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


def _today_start() -> datetime:
    cst = timezone(timedelta(hours=8))
    now = datetime.now(cst)
    return now.replace(hour=0, minute=0, second=0, microsecond=0)


class TestDailyAdviceCache:
    """测试 get_daily_advice 缓存命中/未命中逻辑。"""

    @pytest.mark.asyncio
    async def test_cache_miss_calls_llm(self, db):
        """无缓存时应调用 LLM。"""
        with patch("app.services.agent_service.invoke_advisor", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = "建议内容"
            from app.services.agent_service import get_daily_advice
            result = await get_daily_advice(db, farm_id=1)
        mock_llm.assert_called_once()
        assert result.advice == "建议内容"

    @pytest.mark.asyncio
    async def test_cache_hit_skips_llm(self, db):
        """有缓存时不应调用 LLM，直接返回缓存。"""
        today = _today_start()
        cached = AdviceRecord(
            farm_id=1, advice_type="daily", content="缓存建议", created_at=today,
        )
        db.add(cached)
        db.commit()

        with patch("app.services.agent_service.invoke_advisor", new_callable=AsyncMock) as mock_llm:
            from app.services.agent_service import get_daily_advice
            result = await get_daily_advice(db, farm_id=1)
        mock_llm.assert_not_called()
        assert result.advice == "缓存建议"

    @pytest.mark.asyncio
    async def test_different_farm_cache_miss(self, db):
        """不同 farm_id 应视为缓存未命中。"""
        today = _today_start()
        db.add(AdviceRecord(farm_id=1, advice_type="daily", content="农场1", created_at=today))
        db.commit()

        with patch("app.services.agent_service.invoke_advisor", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = "农场2建议"
            from app.services.agent_service import get_daily_advice
            result = await get_daily_advice(db, farm_id=2)
        mock_llm.assert_called_once()
        assert result.advice == "农场2建议"

    @pytest.mark.asyncio
    async def test_yesterday_record_is_expired(self, db):
        """昨天生成的缓存应已过期，需重新生成。"""
        yesterday = _today_start() - timedelta(days=1)
        db.add(AdviceRecord(farm_id=1, advice_type="daily", content="旧建议", created_at=yesterday))
        db.commit()

        with patch("app.services.agent_service.invoke_advisor", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = "新建议"
            from app.services.agent_service import get_daily_advice
            result = await get_daily_advice(db, farm_id=1)
        mock_llm.assert_called_once()
        assert result.advice == "新建议"

    @pytest.mark.asyncio
    async def test_refresh_deletes_old_and_regenerates(self, db):
        """刷新应删除旧缓存并重新生成。"""
        today = _today_start()
        db.add(AdviceRecord(farm_id=1, advice_type="daily", content="旧缓存", created_at=today))
        db.commit()

        with patch("app.services.agent_service.invoke_advisor", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = "刷新后的建议"
            from app.services.agent_service import refresh_daily_advice
            result = await refresh_daily_advice(db, farm_id=1)
        mock_llm.assert_called_once()
        assert result.advice == "刷新后的建议"
        records = db.query(AdviceRecord).filter(
            AdviceRecord.farm_id == 1, AdviceRecord.advice_type == "daily"
        ).all()
        assert len(records) == 1
        assert records[0].content == "刷新后的建议"
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd backend && python -m pytest tests/test_advice_cache.py -v`
Expected: FAIL（`get_daily_advice` 尚无缓存逻辑，`refresh_daily_advice` 不存在）

- [ ] **Step 3: 修改 agent_service.py 添加缓存逻辑**

在 `backend/app/services/agent_service.py` 中修改 `get_daily_advice` 并新增 `refresh_daily_advice`：

```python
# 在文件顶部添加 import
from datetime import datetime, timezone, timedelta
from sqlalchemy import and_

# 替换 get_daily_advice 函数（约第 41-59 行）
def _today_start_cst() -> datetime:
    """获取东八区今天零点的 UTC 时间。"""
    cst = timezone(timedelta(hours=8))
    now = datetime.now(cst)
    return (now.replace(hour=0, minute=0, second=0, microsecond=0)
            .astimezone(timezone.utc).replace(tzinfo=None))


async def get_daily_advice(
    db: Session, cycle_id: int | None = None, farm_id: int = 1
) -> DailyAdviceResponse:
    """获取每日农事建议（优先从缓存读取）。"""
    today_start = _today_start_cst()

    cached = db.query(AdviceRecord).filter(
        and_(
            AdviceRecord.farm_id == farm_id,
            AdviceRecord.advice_type == "daily",
            AdviceRecord.created_at >= today_start,
        )
    ).first()

    if cached:
        logger.info("建议缓存命中 | record_id=%s", cached.id)
        return DailyAdviceResponse(
            cycle_id=cached.cycle_id,
            advice=cached.content,
            created_at=cached.created_at,
        )

    prompt = "请生成今天的农事建议，考虑当前天气和种植周期阶段。"
    if cycle_id:
        prompt = f"请为周期 ID={cycle_id} 生成今天的农事建议，查询天气和周期信息。"
    logger.info("生成每日建议 | farm=%s cycle=%s", farm_id, cycle_id)
    advice = await invoke_advisor(prompt, farm_id=farm_id)
    record = AdviceRecord(cycle_id=cycle_id, advice_type="daily", content=advice, farm_id=farm_id)
    db.add(record)
    db.commit()
    db.refresh(record)
    logger.info("建议已保存 | record_id=%s", record.id)
    return DailyAdviceResponse(
        cycle_id=record.cycle_id,
        advice=record.content,
        created_at=record.created_at,
    )


async def refresh_daily_advice(
    db: Session, cycle_id: int | None = None, farm_id: int = 1
) -> DailyAdviceResponse:
    """强制刷新每日建议（删除旧缓存，重新生成）。"""
    today_start = _today_start_cst()
    db.query(AdviceRecord).filter(
        and_(
            AdviceRecord.farm_id == farm_id,
            AdviceRecord.advice_type == "daily",
            AdviceRecord.created_at >= today_start,
        )
    ).delete()
    db.commit()
    logger.info("已清除今日缓存 | farm=%s", farm_id)

    prompt = "请生成今天的农事建议，考虑当前天气和种植周期阶段。"
    if cycle_id:
        prompt = f"请为周期 ID={cycle_id} 生成今天的农事建议，查询天气和周期信息。"
    advice = await invoke_advisor(prompt, farm_id=farm_id)
    record = AdviceRecord(cycle_id=cycle_id, advice_type="daily", content=advice, farm_id=farm_id)
    db.add(record)
    db.commit()
    db.refresh(record)
    return DailyAdviceResponse(
        cycle_id=record.cycle_id,
        advice=record.content,
        created_at=record.created_at,
    )
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd backend && python -m pytest tests/test_advice_cache.py -v`
Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
cd backend
git add app/services/agent_service.py tests/test_advice_cache.py
git commit -m "feat: add daily advice cache by farm_id + date"
```

---

## Task 2: 后端 — 新增刷新和报告列表 API

**Files:**
- Modify: `backend/app/api/agent.py`
- Modify: `backend/app/schemas/agent.py`
- Test: `backend/tests/test_report_api.py`

- [ ] **Step 1: 在 schemas/agent.py 添加 ReportListResponse**

在 `backend/app/schemas/agent.py` 末尾添加：

```python
class ReportListResponse(BaseModel):
    """报告历史列表响应。"""
    items: list[ReportHistoryItem]
    total: int
    model_config = ConfigDict(from_attributes=True)
```

- [ ] **Step 2: 在 agent.py 添加刷新和报告列表端点**

在 `backend/app/api/agent.py` 的 `daily_advice` 端点之后添加：

```python
@router.post("/daily/refresh", response_model=DailyAdviceResponse)
async def refresh_daily_advice_endpoint(
    cycle_id: int | None = Query(None, description="关联种植周期 ID"),
    db: Session = Depends(get_db),
    farm: Farm = Depends(get_current_farm),
) -> DailyAdviceResponse:
    """强制刷新每日农事建议。"""
    rid = _new_request_id()
    logger.info("[%s] POST /agent/daily/refresh | cycle_id=%s", rid, cycle_id)
    start = time.perf_counter()
    try:
        result = await refresh_daily_advice(db, cycle_id, farm_id=farm.id)
        logger.info("[%s] /agent/daily/refresh 完成 | 耗时 %.2fs", rid, time.perf_counter() - start)
        return result
    except LlmNotConfiguredError as e:
        raise HTTPException(status_code=503, detail=str(e))
```

在文件顶部 import 中添加 `refresh_daily_advice`：

```python
from app.services.agent_service import (
    chat_with_agent,
    get_daily_advice,
    refresh_daily_advice,
    generate_report,
    get_advice_history,
    get_report_history,
)
```

添加报告列表端点（在现有报告端点之后）：

```python
@router.get("/reports", response_model=ReportListResponse)
async def list_reports(
    page: int = Query(1, ge=1),
    size: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db),
    farm: Farm = Depends(get_current_farm),
) -> ReportListResponse:
    """获取报告历史列表。"""
    from sqlalchemy import func as sqlfunc
    from app.models.agent import ReportRecord
    from app.schemas.agent import ReportHistoryItem, ReportListResponse

    offset = (page - 1) * size
    query = db.query(ReportRecord).filter(ReportRecord.farm_id == farm.id)
    total = query.count()
    records = query.order_by(ReportRecord.created_at.desc()).offset(offset).limit(size).all()
    items = [
        ReportHistoryItem(
            id=r.id,
            cycle_id=r.cycle_id,
            report_type=r.report_type,
            content=r.content[:200],
            created_at=r.created_at,
        )
        for r in records
    ]
    return ReportListResponse(items=items, total=total)
```

- [ ] **Step 3: 编写报告列表 API 测试**

```python
# backend/tests/test_report_api.py
"""报告历史列表 API 测试。"""

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    from app.main import app
    return TestClient(app)


class TestReportListAPI:
    def test_empty_list(self, client):
        resp = client.get("/agent/reports")
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert "total" in data
        assert isinstance(data["items"], list)

    def test_pagination(self, client):
        resp = client.get("/agent/reports?page=1&size=5")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 0
```

- [ ] **Step 4: 运行测试**

Run: `cd backend && python -m pytest tests/test_report_api.py tests/test_advice_cache.py -v`
Expected: all passed

- [ ] **Step 5: Commit**

```bash
cd backend
git add app/api/agent.py app/schemas/agent.py tests/test_report_api.py
git commit -m "feat: add daily advice refresh + report list API"
```

---

## Task 3: 移动端 — agentStore 扩展 + API client 更新

**Files:**
- Modify: `FarmManagerMobile/src/stores/agentStore.ts`
- Modify: `FarmManagerMobile/src/api/client.ts`
- Modify: `FarmManagerMobile/src/api/types.ts`

- [ ] **Step 1: 在 types.ts 添加新类型**

在 `FarmManagerMobile/src/api/types.ts` 末尾添加：

```typescript
export interface ReportListItem {
  id: number;
  cycle_id: number | null;
  report_type: string;
  content: string;
  created_at: string;
}

export interface ReportListResponse {
  items: ReportListItem[];
  total: number;
}
```

- [ ] **Step 2: 在 client.ts 添加新 API 方法**

在 `FarmManagerMobile/src/api/client.ts` 的 `agentApi` 对象中添加：

```typescript
export const agentApi = {
  chat: (data: ChatRequest) => apiClient.post('/agent/chat', data),
  getDailyAdvice: (cycleId?: number) =>
    apiClient.get('/agent/daily', { params: { cycle_id: cycleId } }),
  refreshAdvice: (cycleId?: number) =>
    apiClient.post('/agent/daily/refresh', null, { params: { cycle_id: cycleId } }),
  generateReport: (data: ReportRequest) => apiClient.post('/agent/report', data),
  getAdviceHistory: (cycleId?: number, limit?: number) =>
    apiClient.get('/agent/history', { params: { cycle_id: cycleId, limit } }),
  getReportHistory: (page: number = 1, size: number = 10) =>
    apiClient.get('/agent/reports', { params: { page, size } }),
};
```

在文件顶部 import 中添加 `ReportListResponse`：

```typescript
import type {
  // ...existing imports
  ReportListResponse,
} from './types';
```

- [ ] **Step 3: 扩展 agentStore — 添加 refreshDailyAdvice 和报告历史**

修改 `FarmManagerMobile/src/stores/agentStore.ts`，在 interface `AgentState` 中添加：

```typescript
  reports: ReportListItem[];
  refreshDailyAdvice: (cycleId?: number) => Promise<void>;
  fetchReports: () => Promise<void>;
```

在 import 中添加：

```typescript
import type {ChatMessage, DailyAdvice, ReportResponse, ReportListItem} from '../api/types';
```

在 persist 内部的 state 中添加初始值：

```typescript
  reports: [],
```

在 actions 中添加（在 `setCity` 之前）：

```typescript
  refreshDailyAdvice: async cycleId => {
    set({loading: true, error: null});
    try {
      const res = await agentApi.refreshAdvice(cycleId);
      set({dailyAdvice: res.data, loading: false});
    } catch (err: any) {
      set({error: err.message, loading: false});
    }
  },

  fetchReports: async () => {
    try {
      const res = await agentApi.getReportHistory();
      set({reports: res.data.items});
    } catch (_e) {
      // 报告列表加载失败不阻塞主流程
    }
  },
```

- [ ] **Step 4: Commit**

```bash
cd FarmManagerMobile
git add src/api/types.ts src/api/client.ts src/stores/agentStore.ts
git commit -m "feat: extend agentStore with refresh + report history"
```

---

## Task 4: 移动端 — AdviceCard 添加刷新按钮

**Files:**
- Modify: `FarmManagerMobile/src/components/AdviceCard.tsx`
- Modify: `FarmManagerMobile/src/screens/home/HomeScreen.tsx`

- [ ] **Step 1: 给 AdviceCard 添加 onRefresh prop**

修改 `FarmManagerMobile/src/components/AdviceCard.tsx`，在 Props 接口中添加：

```typescript
interface AdviceCardProps {
  advice: string | null;
  loading: boolean;
  onPress: () => void;
  onRefresh?: () => void;
}
```

在组件参数中接收 `onRefresh`：

```typescript
export const AdviceCard: React.FC<AdviceCardProps> = ({advice, loading, onPress, onRefresh}) => {
```

在 header 区域的 "每日更新" badge 旁边添加刷新按钮（找到 "每日更新" `<Text>` 那一行之后）：

```typescript
<TouchableOpacity onPress={onRefresh} activeOpacity={0.7} style={styles.refreshBtn}>
  <Icon name="refresh" size={16} color={colors.textTertiary} />
</TouchableOpacity>
```

在 styles 中添加：

```typescript
refreshBtn: {
  padding: spacing.xs,
},
```

- [ ] **Step 2: 在 HomeScreen 中传递 onRefresh**

修改 `FarmManagerMobile/src/screens/home/HomeScreen.tsx`，从 agentStore 解构中添加 `refreshDailyAdvice`：

```typescript
const {weather, dailyAdvice, loading, error, cityName, fetchWeather, fetchDailyAdvice, refreshDailyAdvice, setCity} = useAgentStore();
```

修改 AdviceCard 渲染（约第 134 行）：

```tsx
<AdviceCard
  advice={dailyAdvice?.advice ?? null}
  loading={loading}
  onPress={handleAdvicePress}
  onRefresh={() => refreshDailyAdvice()}
/>
```

- [ ] **Step 3: Commit**

```bash
cd FarmManagerMobile
git add src/components/AdviceCard.tsx src/screens/home/HomeScreen.tsx
git commit -m "feat: add refresh button to AdviceCard"
```

---

## Task 5: 移动端 — AgentChatScreen 添加 SegmentedControl + 报告视图

**Files:**
- Modify: `FarmManagerMobile/src/screens/agent/AgentChatScreen.tsx`

- [ ] **Step 1: 添加 SegmentedControl 和报告视图**

在 `AgentChatScreen.tsx` 中添加状态和报告视图。在组件内部添加：

```typescript
const [activeTab, setActiveTab] = useState<'chat' | 'report'>('chat');
const {messages, sendMessage, loading: isLoading, reports, fetchReports} = useAgentStore();
```

在 `hasMessages` 后添加：

```typescript
const hasReports = reports.length > 0;
```

在 `useEffect` 中加载报告列表（在组件内部，return 之前添加）：

```typescript
useEffect(() => {
  if (activeTab === 'report') {
    fetchReports();
  }
}, [activeTab]);
```

在 header View（约第 109-120 行）之后、KeyboardAvoidingView 之前添加 SegmentedControl：

```tsx
<View style={styles.segmentRow}>
  <TouchableOpacity
    style={[styles.segBtn, activeTab === 'chat' && styles.segBtnActive]}
    onPress={() => setActiveTab('chat')}
    activeOpacity={0.7}>
    <Text style={[styles.segText, activeTab === 'chat' && styles.segTextActive]}>对话</Text>
  </TouchableOpacity>
  <TouchableOpacity
    style={[styles.segBtn, activeTab === 'report' && styles.segBtnActive]}
    onPress={() => setActiveTab('report')}
    activeOpacity={0.7}>
    <Text style={[styles.segText, activeTab === 'report' && styles.segTextActive]}>报告</Text>
  </TouchableOpacity>
</View>
```

在 KeyboardAvoidingView 内部，根据 `activeTab` 条件渲染：

```tsx
{activeTab === 'chat' ? (
  <>
    {/* 现有的 FlatList + typing indicator + input bar */}
    <FlatList ... />
    {isLoading && hasMessages && (...typing indicator...)}
    <View style={styles.inputBar}>...</View>
  </>
) : (
  <ReportListView
    reports={reports}
    onGenerate={() => navigation.navigate('AgentReport' as never)}
  />
)}
```

添加 ReportListView 内联组件（在 AgentChatScreen 组件外部）：

```typescript
const ReportListView: React.FC<{
  reports: ReportListItem[];
  onGenerate: () => void;
}> = ({reports, onGenerate}) => (
  <ScrollView style={styles.reportList} contentContainerStyle={styles.reportListContent}>
    <TouchableOpacity style={styles.generateBtn} onPress={onGenerate} activeOpacity={0.7}>
      <Icon name="plus" size={20} color="#FFFFFF" />
      <Text style={styles.generateBtnText}>生成新报告</Text>
    </TouchableOpacity>
    {reports.length === 0 ? (
      <View style={styles.emptyReports}>
        <Icon name="file-document-outline" size={48} color={colors.textTertiary} />
        <Text style={styles.emptyReportsText}>暂无报告</Text>
        <Text style={styles.emptyReportsSub}>点击上方按钮生成第一份报告</Text>
      </View>
    ) : (
      reports.map(r => (
        <TouchableOpacity
          key={r.id}
          style={styles.reportItem}
          activeOpacity={0.7}
          onPress={() => {/* TODO: navigate to report detail */}}>
          <View style={styles.reportItemHeader}>
            <Text style={styles.reportItemType}>{r.report_type === 'weekly' ? '周报' : '月报'}</Text>
            <Text style={styles.reportItemDate}>
              {new Date(r.created_at).toLocaleDateString('zh-CN')}
            </Text>
          </View>
          <Text style={styles.reportItemPreview} numberOfLines={2}>{r.content}</Text>
        </TouchableOpacity>
      ))
    )}
  </ScrollView>
);
```

在文件顶部添加必要的 import：

```typescript
import {ScrollView} from 'react-native';
import {useNavigation} from '@react-navigation/native';
import type {ReportListItem} from '../../api/types';
```

添加 SegmentedControl 和报告列表的样式：

```typescript
segmentRow: {
  flexDirection: 'row',
  marginHorizontal: spacing.lg,
  marginTop: spacing.sm,
  marginBottom: spacing.sm,
  backgroundColor: colors.background,
  borderRadius: borderRadius.lg,
  padding: 3,
},
segBtn: {
  flex: 1,
  paddingVertical: spacing.sm,
  alignItems: 'center',
  borderRadius: borderRadius.md,
},
segBtnActive: {
  backgroundColor: colors.surface,
  shadowColor: '#000',
  shadowOffset: {width: 0, height: 1},
  shadowOpacity: 0.1,
  shadowRadius: 2,
  elevation: 2,
},
segText: {
  fontSize: fontSize.sm,
  color: colors.textSecondary,
  fontWeight: '600',
},
segTextActive: {
  color: colors.text,
},
reportList: {
  flex: 1,
},
reportListContent: {
  padding: spacing.md,
},
generateBtn: {
  flexDirection: 'row',
  alignItems: 'center',
  justifyContent: 'center',
  backgroundColor: colors.primary,
  borderRadius: borderRadius.lg,
  paddingVertical: spacing.md,
  marginBottom: spacing.md,
  gap: spacing.sm,
},
generateBtnText: {
  color: '#FFFFFF',
  fontSize: fontSize.md,
  fontWeight: '700',
},
emptyReports: {
  alignItems: 'center',
  paddingVertical: spacing.xxl,
},
emptyReportsText: {
  fontSize: fontSize.lg,
  color: colors.textSecondary,
  marginTop: spacing.md,
  fontWeight: '600',
},
emptyReportsSub: {
  fontSize: fontSize.sm,
  color: colors.textTertiary,
  marginTop: spacing.xs,
},
reportItem: {
  backgroundColor: colors.surface,
  borderRadius: borderRadius.lg,
  padding: spacing.md,
  marginBottom: spacing.md,
  borderWidth: 1,
  borderColor: colors.borderLight,
},
reportItemHeader: {
  flexDirection: 'row',
  justifyContent: 'space-between',
  marginBottom: spacing.sm,
},
reportItemType: {
  fontSize: fontSize.sm,
  fontWeight: '700',
  color: colors.primary,
},
reportItemDate: {
  fontSize: fontSize.xs,
  color: colors.textTertiary,
},
reportItemPreview: {
  fontSize: fontSize.sm,
  color: colors.textSecondary,
  lineHeight: 20,
},
```

- [ ] **Step 2: Commit**

```bash
cd FarmManagerMobile
git add src/screens/agent/AgentChatScreen.tsx
git commit -m "feat: add SegmentedControl with report view to AI assistant"
```

---

## Task 6: 移动端 — AgentReportScreen Markdown 渲染 + 历史详情

**Files:**
- Modify: `FarmManagerMobile/src/screens/agent/AgentReportScreen.tsx`

- [ ] **Step 1: 替换 <Text> 为 <MarkdownText>**

修改 `FarmManagerMobile/src/screens/agent/AgentReportScreen.tsx`：

添加 import：

```typescript
import {MarkdownText} from '../../components/MarkdownText';
```

将第 62 行的：

```tsx
<Text style={styles.reportContent}>{report.content}</Text>
```

替换为：

```tsx
<MarkdownText text={report.content} baseStyle={styles.reportContent} />
```

移除 styles 中 `reportContent` 的 `color` 和 `fontSize`（MarkdownText 自带样式），只保留 `lineHeight`：

```typescript
reportContent: {
  lineHeight: 24,
},
```

- [ ] **Step 2: Commit**

```bash
cd FarmManagerMobile
git add src/screens/agent/AgentReportScreen.tsx
git commit -m "fix: render report content with MarkdownText"
```

---

## Task 7: 移动端 — settingsStore + SettingsScreen 重写

**Files:**
- Create: `FarmManagerMobile/src/stores/settingsStore.ts`
- Modify: `FarmManagerMobile/src/screens/settings/SettingsScreen.tsx`

- [ ] **Step 1: 创建 settingsStore**

创建 `FarmManagerMobile/src/stores/settingsStore.ts`：

```typescript
import AsyncStorage from '@react-native-async-storage/async-storage';
import {create} from 'zustand';
import {persist, createJSONStorage} from 'zustand/middleware';

interface SettingsState {
  defaultFarmName: string;
  defaultCity: string;
  crops: string[];
  reminderTime: string;
  notificationEnabled: boolean;
  weatherAlertEnabled: boolean;
  setDefaultFarmName: (name: string) => void;
  setDefaultCity: (city: string) => void;
  setCrops: (crops: string[]) => void;
  setReminderTime: (time: string) => void;
  setNotificationEnabled: (enabled: boolean) => void;
  setWeatherAlertEnabled: (enabled: boolean) => void;
}

export const useSettingsStore = create<SettingsState, [['zustand/persist', unknown]]>(
  persist(
    set => ({
      defaultFarmName: '睢宁农场',
      defaultCity: '苏州',
      crops: ['西瓜', '豆角'],
      reminderTime: '08:00',
      notificationEnabled: true,
      weatherAlertEnabled: true,

      setDefaultFarmName: (name) => set({defaultFarmName: name}),
      setDefaultCity: (city) => set({defaultCity: city}),
      setCrops: (crops) => set({crops}),
      setReminderTime: (time) => set({reminderTime: time}),
      setNotificationEnabled: (enabled) => set({notificationEnabled: enabled}),
      setWeatherAlertEnabled: (enabled) => set({weatherAlertEnabled: enabled}),
    }),
    {
      name: 'settings-store',
      storage: createJSONStorage(() => AsyncStorage),
    },
  ),
);
```

- [ ] **Step 2: 重写 SettingsScreen**

重写 `FarmManagerMobile/src/screens/settings/SettingsScreen.tsx`，完全替换为：

```tsx
import React, {useState} from 'react';
import {
  View,
  Text,
  TouchableOpacity,
  StyleSheet,
  ScrollView,
  Alert,
  Switch,
} from 'react-native';
import {SafeAreaView} from 'react-native-safe-area-context';
import {useNavigation} from '@react-navigation/native';
import {Card} from '../../components/Card';
import {CityPicker} from '../../components/CityPicker';
import {useSettingsStore} from '../../stores/settingsStore';
import {useAgentStore} from '../../stores/agentStore';
import {colors} from '../../theme/colors';
import {spacing, fontSize, borderRadius} from '../../theme/spacing';
import Icon from 'react-native-vector-icons/MaterialCommunityIcons';
import AsyncStorage from '@react-native-async-storage/async-storage';

const CROP_OPTIONS = ['西瓜', '豆角', '番茄', '黄瓜', '辣椒', '茄子', '草莓', '玉米'];

const SETTINGS_SECTIONS = {
  farm: [
    {label: '默认农场', icon: 'home', color: colors.primary, field: 'defaultFarmName'},
    {label: '默认城市', icon: 'map-marker', color: colors.success, field: 'defaultCity'},
  ],
  preference: [
    {label: '常种作物', icon: 'sprout', color: colors.accent, field: 'crops'},
    {label: '提醒时间', icon: 'clock-outline', color: colors.info, field: 'reminderTime'},
  ],
  data: [
    {label: '导出数据', icon: 'export', color: colors.primary},
    {label: '清除缓存', icon: 'delete-outline', color: colors.danger},
  ],
  about: [
    {label: '版本', value: 'v1.0', icon: 'tag', color: colors.textTertiary},
    {label: '使用指南', icon: 'book-open-variant', color: colors.primary, route: 'Guide'},
    {label: '关于', value: '智能种植管理平台', icon: 'information', color: colors.textTertiary},
  ],
};

export const SettingsScreen: React.FC = () => {
  const navigation = useNavigation();
  const settings = useSettingsStore();
  const {setCity, cityName} = useAgentStore();
  const [cityPickerVisible, setCityPickerVisible] = useState(false);

  const handleProfilePress = () => {
    Alert.alert('提示', '登录功能即将上线');
  };

  const handleCitySelect = (city: {name: string; lat: number; lon: number}) => {
    settings.setDefaultCity(city.name);
    setCity(city.name, city.lat, city.lon);
    setCityPickerVisible(false);
  };

  const handleExportData = () => {
    Alert.alert('提示', '数据导出功能即将上线');
  };

  const handleClearCache = () => {
    Alert.alert('确认', '确定要清除所有缓存数据吗？', [
      {text: '取消', style: 'cancel'},
      {
        text: '确定',
        style: 'destructive',
        onPress: async () => {
          const keys = await AsyncStorage.getAllKeys();
          const cacheKeys = keys.filter(k => k !== 'settings-store' && k !== 'agent-store');
          if (cacheKeys.length > 0) {
            await AsyncStorage.multiRemove(cacheKeys);
          }
          Alert.alert('提示', '缓存已清除');
        },
      },
    ]);
  };

  const handleCropSelect = () => {
    const currentCrops = settings.crops;
    const selected = new Set(currentCrops);
    Alert.alert(
      '选择常种作物',
      CROP_OPTIONS.join('、'),
      [
        {text: '取消', style: 'cancel'},
        {
          text: '确定',
          onPress: () => settings.setCrops(Array.from(selected)),
        },
      ],
    );
  };

  const renderSection = (title: string, items: any[]) => (
    <View style={styles.section}>
      <Text style={styles.sectionTitle}>{title}</Text>
      <Card elevated={false} style={styles.menuCard}>
        {items.map((item, index) => (
          <TouchableOpacity
            key={item.label}
            style={[styles.menuItem, index < items.length - 1 && styles.menuItemBorder]}
            onPress={() => {
              if (item.route) navigation.navigate(item.route as never);
              else if (item.field === 'defaultCity') setCityPickerVisible(true);
              else if (item.field === 'defaultFarmName') Alert.alert('提示', '多农场管理即将上线');
              else if (item.field === 'crops') handleCropSelect();
              else if (item.field === 'reminderTime') Alert.alert('提示', '提醒时间设置即将上线');
              else if (item.label === '导出数据') handleExportData();
              else if (item.label === '清除缓存') handleClearCache();
            }}
            activeOpacity={item.value ? 1 : 0.6}>
            <View style={styles.menuLeft}>
              <View style={[styles.menuIcon, {backgroundColor: item.color + '12'}]}>
                <Icon name={item.icon} size={20} color={item.color} />
              </View>
              <Text style={styles.menuText}>{item.label}</Text>
            </View>
            <View style={styles.menuRight}>
              <Text style={styles.menuValue}>
                {item.value ?? settings[item.field as keyof typeof settings] ?? ''}
                {Array.isArray(settings[item.field as keyof typeof settings])
                  ? (settings[item.field as keyof typeof settings] as unknown as string[]).join('、')
                  : ''}
              </Text>
              {!item.value && <Icon name="chevron-right" size={20} color={colors.textTertiary} />}
            </View>
          </TouchableOpacity>
        ))}
      </Card>
    </View>
  );

  return (
    <SafeAreaView style={styles.container} edges={['bottom']}>
      <ScrollView contentContainerStyle={styles.scrollContent} showsVerticalScrollIndicator={false}>
        {/* 用户信息 */}
        <TouchableOpacity style={styles.profileSection} onPress={handleProfilePress} activeOpacity={0.7}>
          <View style={styles.profileCard}>
            <View style={styles.avatar}>
              <Icon name="account" size={32} color={colors.primary} />
            </View>
            <View style={styles.profileInfo}>
              <Text style={styles.profileName}>农友</Text>
              <Text style={styles.profileSub}>让种植更简单</Text>
            </View>
            <Icon name="chevron-right" size={20} color="rgba(255,255,255,0.5)" />
          </View>
        </TouchableOpacity>

        {renderSection('农场设置', SETTINGS_SECTIONS.farm)}
        {renderSection('种植偏好', SETTINGS_SECTIONS.preference)}

        {/* 通知开关 */}
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>通知</Text>
          <Card elevated={false} style={styles.menuCard}>
            <View style={[styles.menuItem, styles.menuItemBorder]}>
              <View style={styles.menuLeft}>
                <View style={[styles.menuIcon, {backgroundColor: colors.warning + '12'}]}>
                  <Icon name="bell-outline" size={20} color={colors.warning} />
                </View>
                <Text style={styles.menuText}>农事提醒</Text>
              </View>
              <Switch
                value={settings.notificationEnabled}
                onValueChange={settings.setNotificationEnabled}
                trackColor={{false: colors.borderLight, true: colors.primary + '40'}}
                thumbColor={settings.notificationEnabled ? colors.primary : colors.textTertiary}
              />
            </View>
            <View style={styles.menuItem}>
              <View style={styles.menuLeft}>
                <View style={[styles.menuIcon, {backgroundColor: colors.info + '12'}]}>
                  <Icon name="weather-pouring" size={20} color={colors.info} />
                </View>
                <Text style={styles.menuText}>天气预警</Text>
              </View>
              <Switch
                value={settings.weatherAlertEnabled}
                onValueChange={settings.setWeatherAlertEnabled}
                trackColor={{false: colors.borderLight, true: colors.primary + '40'}}
                thumbColor={settings.weatherAlertEnabled ? colors.primary : colors.textTertiary}
              />
            </View>
          </Card>
        </View>

        {renderSection('数据', SETTINGS_SECTIONS.data)}
        {renderSection('关于', SETTINGS_SECTIONS.about)}
      </ScrollView>

      <CityPicker
        visible={cityPickerVisible}
        selectedCity={settings.defaultCity}
        onSelect={handleCitySelect}
        onClose={() => setCityPickerVisible(false)}
      />
    </SafeAreaView>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.background,
  },
  scrollContent: {
    paddingBottom: spacing.xxl,
  },
  profileSection: {
    paddingHorizontal: spacing.lg,
    paddingTop: spacing.lg,
    paddingBottom: spacing.md,
  },
  profileCard: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: colors.headerBg,
    borderRadius: borderRadius.lg,
    padding: spacing.lg,
  },
  avatar: {
    width: 56,
    height: 56,
    borderRadius: borderRadius.lg,
    backgroundColor: 'rgba(255,255,255,0.1)',
    alignItems: 'center',
    justifyContent: 'center',
    marginRight: spacing.md,
  },
  profileInfo: {
    flex: 1,
  },
  profileName: {
    fontSize: fontSize.lg,
    fontWeight: '700',
    color: colors.headerText,
  },
  profileSub: {
    fontSize: fontSize.sm,
    color: 'rgba(255,255,255,0.6)',
    marginTop: 2,
  },
  section: {
    paddingHorizontal: spacing.lg,
    marginBottom: spacing.lg,
  },
  sectionTitle: {
    fontSize: fontSize.md,
    fontWeight: '700',
    color: colors.text,
    marginBottom: spacing.md,
  },
  menuCard: {
    padding: 0,
    overflow: 'hidden',
  },
  menuItem: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingVertical: spacing.md,
    paddingHorizontal: spacing.md,
  },
  menuItemBorder: {
    borderBottomWidth: 1,
    borderBottomColor: colors.borderLight,
  },
  menuLeft: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.md,
  },
  menuIcon: {
    width: 36,
    height: 36,
    borderRadius: borderRadius.md,
    alignItems: 'center',
    justifyContent: 'center',
  },
  menuText: {
    fontSize: fontSize.md,
    color: colors.text,
    fontWeight: '500',
  },
  menuRight: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.xs,
  },
  menuValue: {
    fontSize: fontSize.sm,
    color: colors.textSecondary,
    fontWeight: '500',
  },
});
```

- [ ] **Step 3: Commit**

```bash
cd FarmManagerMobile
git add src/stores/settingsStore.ts src/screens/settings/SettingsScreen.tsx
git commit -m "feat: redesign settings page with user settings store"
```

---

## Self-Review Checklist

**1. Spec coverage:**
- `daily-advice-cache`: Task 1（后端缓存逻辑）+ Task 2（刷新 API）+ Task 3（store 扩展）+ Task 4（刷新按钮）
- `report-history`: Task 2（报告列表 API）+ Task 3（store + API）+ Task 5（SegmentedControl + 报告视图）+ Task 6（Markdown 渲染）
- `user-settings`: Task 7（settingsStore + SettingsScreen 重写）

**2. Placeholder scan:** 无 TBD/TODO，所有步骤含完整代码。

**3. Type consistency:** `ReportListItem` 在 types.ts 定义，在 client.ts 和 agentStore.ts 中一致使用。`refresh_daily_advice` 在后端 service 定义并在 API route 中引用。
