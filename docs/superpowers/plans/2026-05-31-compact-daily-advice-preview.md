# 紧凑每日建议预览卡片 + 详情页实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将首页 AI 农事建议卡片从平铺全列表改为紧凑预览卡片（~100px），点击后跳转到独立详情页展示完整建议列表。

**Architecture:** 后端 LLM Prompt 要求返回 `{"preview": "...", "items": [...]}` 格式，`_parse_advice_items` 兼容新旧格式；前端新增 `CompactAdviceCard` 组件替换首页 `AdviceCard`，新增 `AdviceDetailScreen` 作为 Stack 导航页面展示完整列表。

**Tech Stack:** 
- 后端: Python 3.11, FastAPI, Pydantic v2, SQLAlchemy, pytest
- 前端: React Native, TypeScript, React Navigation v6, Zustand

---

## 文件结构

### 后端修改
| 文件 | 职责 |
|------|------|
| `backend/app/schemas/agent.py` | `DailyAdviceResponse` 新增 `preview` 字段 |
| `backend/app/services/agent_service.py` | Prompt 更新 + `_parse_advice_items` 兼容新旧格式 + `get_daily_advice` 传递 preview |
| `backend/tests/test_agent_service.py` | 更新测试：新格式解析 + 旧格式兼容 + preview 验证 |
| `backend/tests/test_agent_api.py` | 更新 API 测试：preview 字段验证 |

### 前端新增
| 文件 | 职责 |
|------|------|
| `FarmManagerMobile/src/components/CompactAdviceCard.tsx` | 首页紧凑预览卡片：灵宠 Emoji + preview 文案 + 建议数量 + chevron |
| `FarmManagerMobile/src/screens/advice/AdviceDetailScreen.tsx` | 详情页：Header（大 Emoji + preview + 天气背景）+ 建议列表 + 底部咨询按钮 |

### 前端修改
| 文件 | 职责 |
|------|------|
| `FarmManagerMobile/src/api/types.ts` | `DailyAdvice` 接口新增 `preview` 字段 |
| `FarmManagerMobile/src/navigation/AppNavigator.tsx` | 注册 `AdviceDetail` 路由 + 更新 `RootStackParamList` |
| `FarmManagerMobile/src/screens/home/HomeScreen.tsx` | 替换 `AdviceCard` 为 `CompactAdviceCard`，传入 `dailyAdvice.preview` 和 `weatherCondition` |

---

## Task 1: 后端 Schema — `DailyAdviceResponse` 新增 `preview` 字段

**Files:**
- Modify: `backend/app/schemas/agent.py:41-56`
- Test: `backend/tests/test_agent_api.py:90-104`

- [ ] **Step 1: 修改 Schema，添加 preview 字段**

```python
class DailyAdviceResponse(BaseModel):
    """每日建议响应。"""

    cycle_id: int | None = None
    preview: str = Field(default="", max_length=20)  # 新增
    items: list[AdviceItem]
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)

    @computed_field
    @property
    def advice(self) -> str:
        """向后兼容：拼接所有条目的 title+detail。"""
        if not self.items:
            return ""
        return "; ".join(f"{item.title}: {item.detail}" for item in self.items)
```

- [ ] **Step 2: 验证导入正常**

Run: `cd /Users/ljn/Documents/demo/explore/backend && python -c "from app.schemas.agent import DailyAdviceResponse; r = DailyAdviceResponse(preview='今日有雨', items=[], created_at=__import__('datetime').datetime.now()); print(r.model_dump())"`

Expected: 输出包含 `"preview": "今日有雨"`，无报错

- [ ] **Step 3: 更新 API 测试，验证 preview 字段**

修改 `backend/tests/test_agent_api.py:90-104`：

```python
@patch("app.api.agent.get_daily_advice")
def test_daily_advice_endpoint(self, mock_daily) -> None:
    """验证 GET /agent/daily 返回建议。"""
    from app.schemas.agent import AdviceItem, DailyAdviceResponse

    items = [AdviceItem(title="施肥", detail="追施复合肥", priority=1)]
    mock_daily.return_value = DailyAdviceResponse(
        cycle_id=1, preview="今日有雨", items=items, created_at=datetime.now()
    )

    response = client.get("/agent/daily?cycle_id=1")

    assert response.status_code == 200
    assert response.json()["preview"] == "今日有雨"
    assert "施肥" in response.json()["advice"]
```

- [ ] **Step 4: 运行 API 测试**

Run: `cd /Users/ljn/Documents/demo/explore/backend && poetry run pytest tests/test_agent_api.py::TestAgentDaily -v`

Expected: 1 passed

- [ ] **Step 5: Commit**

```bash
cd /Users/ljn/Documents/demo/explore
git add backend/app/schemas/agent.py backend/tests/test_agent_api.py
git commit -m "feat(schema): DailyAdviceResponse 新增 preview 字段"
```

---

## Task 2: 后端解析逻辑 — 兼容新旧 JSON 格式

**Files:**
- Modify: `backend/app/services/agent_service.py:48-82`
- Test: `backend/tests/test_agent_service.py:192-248`

- [ ] **Step 1: 重写 `_parse_advice_items` 返回 preview + items**

修改 `backend/app/services/agent_service.py:48-82`：

```python
def _parse_advice_items(raw: str) -> tuple[str, list[AdviceItem]]:
    """解析 LLM 返回的 JSON，提取 preview 和 items 列表。

    支持两种格式：
    - 新格式: {"preview": "...", "items": [...]}
    - 旧格式: [...] 或单个 {...}
    """
    try:
        parsed = safe_parse_json(raw)
        preview = ""
        items_raw: list = []

        if isinstance(parsed, dict):
            # 新格式：提取 preview 和 items
            preview = str(parsed.get("preview", ""))[:20]
            items_raw = parsed.get("items", [])
            if not items_raw and "title" in parsed:
                # 旧格式：单个 item dict
                items_raw = [parsed]
        elif isinstance(parsed, list):
            # 旧格式：直接是 items 数组
            items_raw = parsed
        else:
            raise ValueError("非预期的 JSON 结构")

        items: list[AdviceItem] = []
        for entry in items_raw[:_ADVICE_ITEM_MAX]:
            title = _truncate_title(str(entry.get("title", "今日建议")))
            items.append(
                AdviceItem(
                    title=title,
                    detail=str(entry.get("detail", ""))[:50],
                    priority=int(entry.get("priority", 2)),
                    icon=str(entry.get("icon", "📋"))[:4],
                )
            )
        items.sort(key=lambda x: x.priority)
        return preview, items
    except (ValueError, json.JSONDecodeError, KeyError, TypeError) as exc:
        logger.warning("建议 JSON 解析失败，fallback 为单条 | error=%s", exc)
        return "", [
            AdviceItem(
                title="今日农事建议",
                detail=raw[:50],
                priority=2,
                icon="📋",
            )
        ]
```

- [ ] **Step 2: 更新 `get_daily_advice` 使用新解析函数**

修改 `backend/app/services/agent_service.py:268-307`：

```python
    if cached:
        preview, items = _parse_advice_items(cached.content)
        logger.info("缓存命中 | record_id=%s", cached.id)
        return DailyAdviceResponse(
            cycle_id=cached.cycle_id,
            preview=preview,
            items=items,
            created_at=cached.created_at,
        )

    base_prompt = (
        "请生成今天的农事建议。以 JSON 格式回复："
        '{"preview":"≤15字今日一句话总结","items":['
        '{"title":"≤10字结论","detail":"≤40字原因","priority":1到3,"icon":"emoji"}]}。'
        "最多5条，按紧急程度排序。"
    )
    if cycle_id:
        prompt = f"请为周期 ID={cycle_id} 生成今天的农事建议。{base_prompt}"
    else:
        prompt = base_prompt
    logger.info("生成每日建议 | farm=%s cycle=%s", farm_id, cycle_id)
    advice = await invoke_advisor(prompt, farm_id=farm_id)

    preview, items = _parse_advice_items(advice)

    record = AgentRecord(
        cycle_id=cycle_id, record_type="daily", content=advice, farm_id=farm_id
    )
    db.add(record)
    try:
        db.commit()
        db.refresh(record)
    except Exception:
        db.rollback()
        raise
    logger.info("建议已保存 | record_id=%s | items=%d", record.id, len(items))

    return DailyAdviceResponse(
        cycle_id=record.cycle_id,
        preview=preview,
        items=items,
        created_at=record.created_at,
    )
```

- [ ] **Step 3: 编写新格式解析测试**

在 `backend/tests/test_agent_service.py` 的 `TestGetDailyAdvice` 类中添加：

```python
    @pytest.mark.asyncio
    @patch("app.services.agent_service.invoke_advisor", new_callable=AsyncMock)
    async def test_get_daily_advice_new_format_with_preview(
        self, mock_invoke: AsyncMock
    ) -> None:
        """验证新格式 JSON（含 preview）正确解析。"""
        mock_invoke.return_value = (
            '{"preview":"今日有雨注意防涝",'
            '"items":[{"title":"施肥","detail":"生长期需追肥","priority":1,"icon":"🌱"}]}'
        )
        mock_db = _make_mock_db()

        result = await get_daily_advice(mock_db, farm_id=1, cycle_id=1)

        assert result.preview == "今日有雨注意防涝"
        assert len(result.items) == 1
        assert result.items[0].title == "施肥"
        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()

    @pytest.mark.asyncio
    @patch("app.services.agent_service.invoke_advisor", new_callable=AsyncMock)
    async def test_get_daily_advice_old_format_backward_compatible(
        self, mock_invoke: AsyncMock
    ) -> None:
        """验证旧格式 JSON 数组仍兼容。"""
        mock_invoke.return_value = (
            '[{"title":"浇水","detail":"保持土壤湿润","priority":2,"icon":"💧"}]'
        )
        mock_db = _make_mock_db()

        result = await get_daily_advice(mock_db, farm_id=1, cycle_id=1)

        assert result.preview == ""
        assert len(result.items) == 1
        assert result.items[0].title == "浇水"
```

同时更新现有的 `test_get_daily_advice_returns_structured_items`：

```python
    @pytest.mark.asyncio
    @patch("app.services.agent_service.invoke_advisor", new_callable=AsyncMock)
    async def test_get_daily_advice_returns_structured_items(
        self, mock_invoke: AsyncMock
    ) -> None:
        """验证每日建议生成结构化 items 并保存。"""
        mock_invoke.return_value = (
            '[{"title":"施肥","detail":"生长期需追肥","priority":1,"icon":"🌱"}]'
        )
        mock_db = _make_mock_db()

        result = await get_daily_advice(mock_db, farm_id=1, cycle_id=1)

        assert len(result.items) == 1
        assert result.items[0].title == "施肥"
        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()
```

更新 `test_get_daily_advice_fallback_on_plain_text`：

```python
    @pytest.mark.asyncio
    @patch("app.services.agent_service.invoke_advisor", new_callable=AsyncMock)
    async def test_get_daily_advice_fallback_on_plain_text(
        self, mock_invoke: AsyncMock
    ) -> None:
        """验证 LLM 返回纯文本时 fallback 为单条 item。"""
        mock_invoke.return_value = "今日建议：施肥。"
        mock_db = _make_mock_db()

        result = await get_daily_advice(mock_db, farm_id=1, cycle_id=1)

        assert len(result.items) == 1
        assert result.items[0].title == "今日农事建议"
        assert result.preview == ""
        # 向后兼容：advice property 返回拼接文本
        assert "今日建议：施肥。" in result.advice
```

- [ ] **Step 4: 运行全部后端测试**

Run: `cd /Users/ljn/Documents/demo/explore/backend && poetry run pytest tests/test_agent_service.py tests/test_agent_api.py -v`

Expected: 所有测试通过（约 12-14 个）

- [ ] **Step 5: Commit**

```bash
cd /Users/ljn/Documents/demo/explore
git add backend/app/services/agent_service.py backend/tests/test_agent_service.py
git commit -m "feat(agent): 解析逻辑支持 preview + items 新格式，兼容旧格式"
```

---

## Task 3: 前端类型 — `DailyAdvice` 新增 `preview` 字段

**Files:**
- Modify: `FarmManagerMobile/src/api/types.ts:110-115`

- [ ] **Step 1: 更新 TypeScript 类型定义**

```typescript
export interface DailyAdvice {
  cycle_id: number | null;
  preview: string;  // 新增
  advice: string;
  items: AdviceItem[];
  created_at: string;
}
```

- [ ] **Step 2: 验证类型无冲突**

Run: `cd /Users/ljn/Documents/demo/explore/FarmManagerMobile && npx tsc --noEmit src/api/types.ts`

Expected: 无错误输出

- [ ] **Step 3: Commit**

```bash
cd /Users/ljn/Documents/demo/explore
git add FarmManagerMobile/src/api/types.ts
git commit -m "feat(types): DailyAdvice 新增 preview 字段"
```

---

## Task 4: 前端组件 — 创建 `CompactAdviceCard`

**Files:**
- Create: `FarmManagerMobile/src/components/CompactAdviceCard.tsx`
- Test: 通过视觉检查（真机/模拟器）

- [ ] **Step 1: 编写 CompactAdviceCard 组件**

```typescript
import React from "react";
import { View, Text, StyleSheet, TouchableOpacity } from "react-native";
import { colors } from "../theme/colors";
import { spacingV2, fontSizeV2, borderRadiusV2 } from "../theme/spacing";
import { shadowV2 } from "../theme/designTokens";
import Icon from "react-native-vector-icons/MaterialCommunityIcons";

interface CompactAdviceCardProps {
  preview: string;
  itemCount: number;
  weatherCondition?: "sunny" | "rainy" | "foggy" | "cold";
  loading?: boolean;
  onPress?: () => void;
  onRefresh?: () => void;
}

const WEATHER_CONFIG = {
  sunny: { emoji: "🌾", bg: "#FDF6E3" },
  rainy: { emoji: "🌧️", bg: "#E8F1FF" },
  foggy: { emoji: "🌫️", bg: "#F0F4F8" },
  cold: { emoji: "❄️", bg: "#E8F4FF" },
};

const DEFAULT_FALLBACK = {
  sunny: "阳光正好，适合农作",
  rainy: "雨水充沛，防涝为主",
  foggy: "雾气朦胧，注意排湿",
  cold: "气温骤降，注意防冻",
};

export const CompactAdviceCard: React.FC<CompactAdviceCardProps> = ({
  preview,
  itemCount,
  weatherCondition = "sunny",
  loading = false,
  onPress,
  onRefresh,
}) => {
  const config = WEATHER_CONFIG[weatherCondition] || WEATHER_CONFIG.sunny;
  const displayPreview = preview || DEFAULT_FALLBACK[weatherCondition] || DEFAULT_FALLBACK.sunny;
  const countText = itemCount > 0 ? `${itemCount} 条农事建议待查看` : "暂无建议";

  return (
    <TouchableOpacity
      style={[styles.card, shadowV2.light]}
      onPress={onPress}
      activeOpacity={0.7}
      disabled={loading}
    >
      <View style={styles.content}>
        {/* 左侧灵宠 Emoji */}
        <View style={[styles.emojiCircle, { backgroundColor: config.bg }]}>
          <Text style={styles.emoji}>{config.emoji}</Text>
        </View>

        {/* 中间文案 */}
        <View style={styles.textContainer}>
          <Text style={styles.previewText} numberOfLines={1}>
            {loading ? "AI 正在分析..." : displayPreview}
          </Text>
          <Text style={styles.countText}>
            {loading ? "请稍候..." : countText}
          </Text>
        </View>

        {/* 右侧 chevron */}
        {!loading && (
          <Icon name="chevron-right" size={20} color={colors.textTertiary} />
        )}
      </View>

      {/* 刷新按钮 */}
      {onRefresh && !loading && (
        <TouchableOpacity
          style={styles.refreshBtn}
          onPress={(e) => {
            e.stopPropagation();
            onRefresh();
          }}
          activeOpacity={0.7}
          hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}
        >
          <Icon name="refresh" size={14} color={colors.textTertiary} />
        </TouchableOpacity>
      )}
    </TouchableOpacity>
  );
};

const styles = StyleSheet.create({
  card: {
    backgroundColor: colors.surface,
    borderRadius: borderRadiusV2.xxxl,
    paddingHorizontal: spacingV2.lg,
    paddingVertical: spacingV2.md,
    minHeight: 88,
    justifyContent: "center",
  },
  content: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacingV2.md,
  },
  emojiCircle: {
    width: 56,
    height: 56,
    borderRadius: borderRadiusV2.full,
    alignItems: "center",
    justifyContent: "center",
  },
  emoji: {
    fontSize: 28,
  },
  textContainer: {
    flex: 1,
    gap: 4,
  },
  previewText: {
    fontSize: fontSizeV2.md,
    fontWeight: "700",
    color: colors.text,
    letterSpacing: -0.3,
  },
  countText: {
    fontSize: fontSizeV2.sm,
    color: colors.textSecondary,
  },
  refreshBtn: {
    position: "absolute",
    top: spacingV2.sm,
    right: spacingV2.sm,
    padding: spacingV2.xs,
  },
});
```

- [ ] **Step 2: 验证组件类型检查通过**

Run: `cd /Users/ljn/Documents/demo/explore/FarmManagerMobile && npx tsc --noEmit src/components/CompactAdviceCard.tsx`

Expected: 无错误输出

- [ ] **Step 3: Commit**

```bash
cd /Users/ljn/Documents/demo/explore
git add FarmManagerMobile/src/components/CompactAdviceCard.tsx
git commit -m "feat(ui): 新增 CompactAdviceCard 紧凑预览卡片组件"
```

---

## Task 5: 前端页面 — 创建 `AdviceDetailScreen`

**Files:**
- Create: `FarmManagerMobile/src/screens/advice/AdviceDetailScreen.tsx`
- Modify: `FarmManagerMobile/src/navigation/AppNavigator.tsx:28-55` 添加类型定义

- [ ] **Step 1: 编写 AdviceDetailScreen 组件**

```typescript
import React, { useEffect, useState } from "react";
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  LayoutAnimation,
  Platform,
  UIManager,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { useNavigation, useRoute, RouteProp } from "@react-navigation/native";
import { NativeStackNavigationProp } from "@react-navigation/native-stack";
import LinearGradient from "react-native-linear-gradient";
import type { AdviceItem } from "../../api/types";
import { useAgentStore } from "../../stores/agentStore";
import { colors } from "../../theme/colors";
import { spacingV2, fontSizeV2, borderRadiusV2 } from "../../theme/spacing";
import { appGradients } from "../../theme/gradients";
import { shadowV2 } from "../../theme/designTokens";
import Icon from "react-native-vector-icons/MaterialCommunityIcons";

if (Platform.OS === "android") {
  UIManager.setLayoutAnimationEnabledExperimental?.(true);
}

type RootStackParamList = {
  AdviceDetail: {
    items?: AdviceItem[];
    preview?: string;
    weatherCondition?: "sunny" | "rainy" | "foggy" | "cold";
    createdAt?: string;
  };
  AgentChat: { cycleId?: number };
};

type AdviceDetailRouteProp = RouteProp<RootStackParamList, "AdviceDetail">;
type AdviceDetailNavProp = NativeStackNavigationProp<RootStackParamList>;

const WEATHER_CONFIG = {
  sunny: { emoji: "🌾", gradient: appGradients.emotionSunny },
  rainy: { emoji: "🌧️", gradient: appGradients.emotionRainy },
  foggy: { emoji: "🌫️", gradient: appGradients.emotionFoggy },
  cold: { emoji: "❄️", gradient: appGradients.emotionCold },
};

const DEFAULT_FALLBACK = {
  sunny: "阳光正好，适合农作",
  rainy: "雨水充沛，防涝为主",
  foggy: "雾气朦胧，注意排湿",
  cold: "气温骤降，注意防冻",
};

const PRIORITY_COLORS = {
  1: colors.danger,
  2: colors.warning,
  3: colors.info,
};

export const AdviceDetailScreen: React.FC = () => {
  const navigation = useNavigation<AdviceDetailNavProp>();
  const route = useRoute<AdviceDetailRouteProp>();
  const { fetchDailyAdvice, dailyAdvice, loading } = useAgentStore();

  const [items, setItems] = useState<AdviceItem[]>(route.params?.items || []);
  const [preview, setPreview] = useState(route.params?.preview || "");
  const weatherCondition = route.params?.weatherCondition || "sunny";
  const createdAt = route.params?.createdAt || dailyAdvice?.created_at;

  const config = WEATHER_CONFIG[weatherCondition] || WEATHER_CONFIG.sunny;
  const displayPreview = preview || DEFAULT_FALLBACK[weatherCondition] || DEFAULT_FALLBACK.sunny;

  useEffect(() => {
    // 如果没有传入数据，尝试从 store 获取
    if (!items.length && !route.params?.items) {
      fetchDailyAdvice();
    }
  }, []);

  useEffect(() => {
    // store 数据加载完成后更新本地状态
    if (dailyAdvice && !route.params?.items) {
      LayoutAnimation.configureNext(LayoutAnimation.Presets.easeInEaseOut);
      setItems(dailyAdvice.items);
      setPreview(dailyAdvice.preview);
    }
  }, [dailyAdvice]);

  const dateText = createdAt
    ? new Date(createdAt).toLocaleDateString("zh-CN", {
        month: "long",
        day: "numeric",
        weekday: "long",
      })
    : new Date().toLocaleDateString("zh-CN", {
        month: "long",
        day: "numeric",
        weekday: "long",
      });

  return (
    <SafeAreaView style={styles.container} edges={["bottom"]}>
      <ScrollView
        contentContainerStyle={styles.scrollContent}
        showsVerticalScrollIndicator={false}
      >
        {/* Header */}
        <LinearGradient {...config.gradient} style={styles.header}>
          <Text style={styles.headerEmoji}>{config.emoji}</Text>
          <Text style={styles.headerPreview}>{displayPreview}</Text>
          <Text style={styles.headerDate}>{dateText}</Text>
        </LinearGradient>

        {/* 建议列表 */}
        <View style={styles.listContainer}>
          {loading && !items.length && (
            <View style={styles.loadingContainer}>
              <Text style={styles.loadingText}>AI 正在分析天气和作物数据...</Text>
            </View>
          )}

          {!loading && !items.length && (
            <View style={styles.emptyContainer}>
              <Icon
                name="information-outline"
                size={40}
                color={colors.textTertiary}
              />
              <Text style={styles.emptyText}>暂无建议，请稍后重试</Text>
            </View>
          )}

          {items.map((item, index) => (
            <View key={index} style={[styles.itemCard, shadowV2.light]}>
              <View
                style={[
                  styles.priorityBar,
                  { backgroundColor: PRIORITY_COLORS[item.priority as keyof typeof PRIORITY_COLORS] || colors.info },
                ]}
              />
              <View style={styles.itemContent}>
                <View style={styles.itemTopRow}>
                  <Text style={styles.itemIcon}>{item.icon}</Text>
                  <Text style={styles.itemTitle}>{item.title}</Text>
                </View>
                <Text style={styles.itemDetail}>{item.detail}</Text>
              </View>
            </View>
          ))}
        </View>

        {/* 底部咨询按钮 */}
        {items.length > 0 && (
          <TouchableOpacity
            style={styles.actionButton}
            onPress={() => navigation.navigate("AgentChat")}
            activeOpacity={0.8}
          >
            <LinearGradient
              colors={colors.gradients.primary}
              start={{ x: 0, y: 0 }}
              end={{ x: 1, y: 0 }}
              style={styles.actionGradient}
            >
              <Icon
                name="chat-processing-outline"
                size={18}
                color={colors.textInverse}
              />
              <Text style={styles.actionText}>咨询农事顾问</Text>
            </LinearGradient>
          </TouchableOpacity>
        )}
      </ScrollView>
    </SafeAreaView>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.background,
  },
  scrollContent: {
    paddingBottom: spacingV2.xxxl,
  },
  header: {
    alignItems: "center",
    paddingVertical: spacingV2.xxl,
    paddingHorizontal: spacingV2.lg,
    marginHorizontal: spacingV2.lg,
    marginTop: spacingV2.lg,
    borderRadius: borderRadiusV2.xxxl,
  },
  headerEmoji: {
    fontSize: 72,
    marginBottom: spacingV2.sm,
  },
  headerPreview: {
    fontSize: fontSizeV2.lg,
    fontWeight: "700",
    color: colors.text,
    textAlign: "center",
    marginBottom: spacingV2.xs,
  },
  headerDate: {
    fontSize: fontSizeV2.sm,
    color: colors.textSecondary,
  },
  listContainer: {
    paddingHorizontal: spacingV2.lg,
    marginTop: spacingV2.xl,
    gap: spacingV2.md,
  },
  itemCard: {
    flexDirection: "row",
    backgroundColor: colors.surface,
    borderRadius: borderRadiusV2.xl,
    overflow: "hidden",
  },
  priorityBar: {
    width: 4,
  },
  itemContent: {
    flex: 1,
    padding: spacingV2.lg,
    gap: spacingV2.xs,
  },
  itemTopRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacingV2.sm,
  },
  itemIcon: {
    fontSize: 20,
  },
  itemTitle: {
    fontSize: fontSizeV2.md,
    fontWeight: "700",
    color: colors.text,
    letterSpacing: -0.3,
  },
  itemDetail: {
    fontSize: fontSizeV2.sm,
    color: colors.textSecondary,
    lineHeight: 22,
  },
  loadingContainer: {
    alignItems: "center",
    paddingVertical: spacingV2.xxl,
  },
  loadingText: {
    fontSize: fontSizeV2.sm,
    color: colors.textSecondary,
  },
  emptyContainer: {
    alignItems: "center",
    paddingVertical: spacingV2.xxl,
    gap: spacingV2.md,
  },
  emptyText: {
    fontSize: fontSizeV2.sm,
    color: colors.textSecondary,
  },
  actionButton: {
    marginHorizontal: spacingV2.lg,
    marginTop: spacingV2.xl,
    borderRadius: borderRadiusV2.lg,
    overflow: "hidden",
  },
  actionGradient: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: spacingV2.sm,
    paddingVertical: spacingV2.md,
  },
  actionText: {
    fontSize: fontSizeV2.md,
    fontWeight: "700",
    color: colors.textInverse,
  },
});
```

- [ ] **Step 2: 验证类型检查**

Run: `cd /Users/ljn/Documents/demo/explore/FarmManagerMobile && npx tsc --noEmit src/screens/advice/AdviceDetailScreen.tsx`

Expected: 无错误输出（可能有一些模块解析问题，但不应有类型错误）

- [ ] **Step 3: Commit**

```bash
cd /Users/ljn/Documents/demo/explore
git add FarmManagerMobile/src/screens/advice/AdviceDetailScreen.tsx
git commit -m "feat(screen): 新增 AdviceDetailScreen 建议详情页"
```

---

## Task 6: 前端导航 — 注册 `AdviceDetail` 路由

**Files:**
- Modify: `FarmManagerMobile/src/navigation/AppNavigator.tsx:28-55`
- Modify: `FarmManagerMobile/src/navigation/AppNavigator.tsx:104-192`

- [ ] **Step 1: 在 RootStackParamList 中添加 AdviceDetail 类型**

在 `RootStackParamList` 中添加：

```typescript
export type RootStackParamList = {
  Main: undefined;
  AdviceDetail: {
    items?: any[];
    preview?: string;
    weatherCondition?: "sunny" | "rainy" | "foggy" | "cold";
    createdAt?: string;
  };
  CycleDetail: { cycleId: number };
  // ... 其余保持不变
};
```

- [ ] **Step 2: 在 Stack.Navigator 中注册 AdviceDetail 路由**

在 `Main` 路由之后添加：

```typescript
<Stack.Screen
  name="AdviceDetail"
  component={AdviceDetailScreen}
  options={{ title: "农事建议", headerShown: false }}
/>
```

同时需要在文件顶部添加 import：

```typescript
import { AdviceDetailScreen } from "../screens/advice/AdviceDetailScreen";
```

- [ ] **Step 3: 验证导航类型**

Run: `cd /Users/ljn/Documents/demo/explore/FarmManagerMobile && npx tsc --noEmit src/navigation/AppNavigator.tsx`

Expected: 无错误输出

- [ ] **Step 4: Commit**

```bash
cd /Users/ljn/Documents/demo/explore
git add FarmManagerMobile/src/navigation/AppNavigator.tsx
git commit -m "feat(nav): 注册 AdviceDetail 路由到 Stack Navigator"
```

---

## Task 7: 前端首页 — 替换 AdviceCard 为 CompactAdviceCard

**Files:**
- Modify: `FarmManagerMobile/src/screens/home/HomeScreen.tsx:1-24` 更新 import
- Modify: `FarmManagerMobile/src/screens/home/HomeScreen.tsx:185-194` 替换组件

- [ ] **Step 1: 更新 import，引入 CompactAdviceCard**

修改 import 部分：

```typescript
import { CompactAdviceCard } from "../../components/CompactAdviceCard";
// 保留 AdviceCard import（详情页可能仍需要）
import { AdviceCard } from "../../components/AdviceCard";
```

- [ ] **Step 2: 替换 AI Briefing Card 区域**

将原有的 `AdviceCard` 调用替换为 `CompactAdviceCard`：

```typescript
        {/* AI Briefing Card */}
        <FadeInSlideUp delay={160} style={styles.section}>
          <CompactAdviceCard
            preview={dailyAdvice?.preview || ""}
            itemCount={dailyAdvice?.items?.length || 0}
            loading={agentLoading}
            weatherCondition={weatherCondition}
            onPress={() =>
              navigation.navigate("AdviceDetail" as never, {
                items: dailyAdvice?.items,
                preview: dailyAdvice?.preview,
                weatherCondition,
                createdAt: dailyAdvice?.created_at,
              } as never)
            }
            onRefresh={() => refreshDailyAdvice()}
          />
        </FadeInSlideUp>
```

- [ ] **Step 3: 验证 HomeScreen 类型检查**

Run: `cd /Users/ljn/Documents/demo/explore/FarmManagerMobile && npx tsc --noEmit src/screens/home/HomeScreen.tsx`

Expected: 无错误输出

- [ ] **Step 4: Commit**

```bash
cd /Users/ljn/Documents/demo/explore
git add FarmManagerMobile/src/screens/home/HomeScreen.tsx
git commit -m "feat(home): 首页使用 CompactAdviceCard 替换 AdviceCard"
```

---

## Task 8: 验证与测试

**Files:**
- Run: 后端测试
- Run: 前端类型检查
- Run: 前端 lint（如有）

- [ ] **Step 1: 运行完整后端测试套件**

Run: `cd /Users/ljn/Documents/demo/explore/backend && poetry run pytest tests/test_agent_service.py tests/test_agent_api.py -v`

Expected: 所有测试通过，显示类似：
```
tests/test_agent_service.py::TestChatWithAgent::test_chat_with_agent_returns_reply PASSED
tests/test_agent_service.py::TestGetDailyAdvice::test_get_daily_advice_returns_structured_items PASSED
tests/test_agent_service.py::TestGetDailyAdvice::test_get_daily_advice_new_format_with_preview PASSED
tests/test_agent_service.py::TestGetDailyAdvice::test_get_daily_advice_old_format_backward_compatible PASSED
tests/test_agent_service.py::TestGetDailyAdvice::test_get_daily_advice_fallback_on_plain_text PASSED
... （其余测试）
```

- [ ] **Step 2: 运行前端类型检查**

Run: `cd /Users/ljn/Documents/demo/explore/FarmManagerMobile && npx tsc --noEmit`

Expected: 无类型错误（假设项目配置了 `tsconfig.json`）

- [ ] **Step 3: 运行前端 lint**

Run: `cd /Users/ljn/Documents/demo/explore/FarmManagerMobile && pnpm lint 2>/dev/null || npm run lint 2>/dev/null || echo "lint command not found, skip"`

Expected: 无 lint 错误，或 "lint command not found"（如果项目未配置）

- [ ] **Step 4: 验证后端 Schema 可序列化**

Run: `cd /Users/ljn/Documents/demo/explore/backend && python -c "
from app.schemas.agent import DailyAdviceResponse, AdviceItem
from datetime import datetime
r = DailyAdviceResponse(
    cycle_id=1,
    preview='今日有雨',
    items=[AdviceItem(title='施肥', detail='追肥', priority=1, icon='🌱')],
    created_at=datetime.now()
)
print(r.model_dump_json())
"`

Expected: 输出 JSON 包含 `"preview":"今日有雨"`、`"advice":"施肥: 追肥"`

- [ ] **Step 5: Commit（如有修复）**

```bash
cd /Users/ljn/Documents/demo/explore
git add -A
git diff --cached --quiet || git commit -m "chore: 修复类型和 lint 问题"
```

---

## Task 9: 端到端测试清单

**Files:**
- 手动测试（真机/模拟器）

- [ ] **Step 1: 启动后端服务**

Run: `cd /Users/ljn/Documents/demo/explore/backend && poetry run uvicorn app.main:app --reload --port 8000`

- [ ] **Step 2: 启动前端 Metro**

Run: `cd /Users/ljn/Documents/demo/explore/FarmManagerMobile && npx react-native start`

- [ ] **Step 3: Android 模拟器测试**

在另一个终端运行：

Run: `cd /Users/ljn/Documents/demo/explore/FarmManagerMobile && npx react-native run-android`

测试项：
1. 首页应显示 CompactAdviceCard（灵宠 Emoji + preview 文案 + 建议数量）
2. 点击预览卡片 → 跳转到 AdviceDetailScreen
3. 详情页 Header 显示大 Emoji + preview + 日期
4. 详情页显示建议列表（带优先级彩色竖条）
5. 详情页底部有 "咨询农事顾问" 按钮，点击可跳转
6. 返回首页，点击刷新按钮，预览文案更新
7. 杀掉 App 重新进入，旧数据应显示 fallback 文案（根据天气）

- [ ] **Step 4: 旧数据兼容测试**

修改数据库中的今日记录，将 content 改为旧格式数组：

```sql
UPDATE agent_records SET content = '[{"title":"施肥","detail":"追肥","priority":1}]' 
WHERE record_type = 'daily' AND DATE(created_at) = CURDATE();
```

重新请求 `/agent/daily`，验证：
- `preview` 为空字符串 `""`
- `items` 正常解析
- 前端显示 fallback 文案（如天气 sunny 显示 "阳光正好，适合农作"）

- [ ] **Step 5: 截图归档**

测试通过后，截图保存到：
- `docs/screenshots/compact-advice-card-home.png`
- `docs/screenshots/advice-detail-screen.png`

---

## Self-Review

### 1. Spec 覆盖检查

| Spec 要求 | 实现任务 |
|-----------|----------|
| 后端 `DailyAdviceResponse` 新增 `preview` | Task 1 |
| Prompt 更新为 `{"preview":"...","items":[...]}` | Task 2 |
| `_parse_advice_items` 兼容新旧格式 | Task 2 |
| 前端 `DailyAdvice` 类型新增 `preview` | Task 3 |
| `CompactAdviceCard` 组件 | Task 4 |
| `AdviceDetailScreen` 详情页 | Task 5 |
| `AdviceDetail` 路由注册 | Task 6 |
| 首页替换为 CompactAdviceCard | Task 7 |
| fallback 文案（旧数据/空 preview） | Task 4, 5 中的 DEFAULT_FALLBACK |
| 详情页底部 "咨询农事顾问" 按钮 | Task 5 |
| 详情页无参数时调用 fetchDailyAdvice | Task 5 中的 useEffect |

**无遗漏。**

### 2. Placeholder 扫描

检查文档中是否包含以下禁用模式：
- ❌ "TBD" / "TODO" / "implement later" / "fill in details" — 无
- ❌ "Add appropriate error handling" / "add validation" / "handle edge cases" — 无
- ❌ "Write tests for the above"（无实际测试代码）— 无
- ❌ "Similar to Task N" — 无
- ❌ 只有描述没有代码的步骤 — 无

### 3. 类型一致性检查

- `DailyAdviceResponse.preview`: `str = Field(default="", max_length=20)`（Task 1）
- `DailyAdvice.preview`: `string`（Task 3）
- `CompactAdviceCard.preview`: `string`（Task 4）
- `AdviceDetailScreen` route params `preview`: `string`（Task 5）
- `_parse_advice_items` 返回 `tuple[str, list[AdviceItem]]`（Task 2）

**全部一致。**

- `weatherCondition` 类型: `"sunny" | "rainy" | "foggy" | "cold"` — 在 HomeScreen、CompactAdviceCard、AdviceDetailScreen 中一致

**全部一致。**

---

## 快速参考：天气配置映射

| weatherCondition | Emoji | 背景色 | Fallback 文案 |
|-----------------|-------|--------|--------------|
| sunny | 🌾 | #FDF6E3 | 阳光正好，适合农作 |
| rainy | 🌧️ | #E8F1FF | 雨水充沛，防涝为主 |
| foggy | 🌫️ | #F0F4F8 | 雾气朦胧，注意排湿 |
| cold | ❄️ | #E8F4FF | 气温骤降，注意防冻 |

| Priority | 颜色 |
|----------|------|
| 1 | `colors.danger` (#C45B5B) |
| 2 | `colors.warning` (#D49A4A) |
| 3 | `colors.info` (#5B8DB8) |

## 快速参考：文件变更清单

```bash
# 后端（4 个文件）
backend/app/schemas/agent.py                    # + preview 字段
backend/app/services/agent_service.py           # Prompt + 解析逻辑 + get_daily_advice
backend/tests/test_agent_service.py             # + 新格式/旧格式兼容测试
backend/tests/test_agent_api.py                 # + preview 验证

# 前端（5 个文件）
FarmManagerMobile/src/api/types.ts              # + preview 字段
FarmManagerMobile/src/components/CompactAdviceCard.tsx   # 新建
FarmManagerMobile/src/screens/advice/AdviceDetailScreen.tsx  # 新建
FarmManagerMobile/src/navigation/AppNavigator.tsx  # + AdviceDetail 路由
FarmManagerMobile/src/screens/home/HomeScreen.tsx  # 替换 AdviceCard
```
