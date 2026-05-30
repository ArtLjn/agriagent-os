## Context

当前首页 `HomeScreen` 使用 `AdviceCard` 组件平铺展示所有 `DailyAdvice.items`。每个建议条目都是带背景、边框、padding 的独立卡片，信息密度过高。在 iPhone 14 Pro（390×844pt）上，WeatherCard（~280px）+ AdviceCard（~350px）已经超过首屏高度，导致 QuickActions 被遮挡。

用户希望将建议模块改为"预览+详情"模式，保持首页清爽，同时提供完整的建议查看体验。

## Goals / Non-Goals

**Goals:**
- 首页建议卡片高度控制在 90-110px，不超出首屏
- 预览卡片展示天气氛围 + 一句总结 + 建议数量
- 详情页展示完整建议列表，带灵宠 Emoji 和天气氛围
- LLM 返回的结构化数据新增 `preview` 字段
- 保持向后兼容，旧格式数据可正常解析

**Non-Goals:**
- 不修改底部 Tab 导航（已达 4 个上限）
- 不添加新的 LLM 调用，preview 在生成 items 时一并产出
- 不做复杂的动画（保持简单 LayoutAnimation）
- 不涉及 AI Chat 对话流程的修改

## Decisions

### 1. 首页预览卡片设计

采用**横向布局**，左侧灵宠 Emoji（56px 圆形背景），右侧文案纵向排列：

```
┌─────────────────────────────────────┐
│ ┌────────┐                          │
│ │  🌧️   │  今日有雨，注意防涝       │
│ │        │  3 条农事建议待查看  >   │
│ └────────┘                          │
└─────────────────────────────────────┘
```

- **灵宠**：根据 `weatherCondition` 显示 Emoji，放在浅色圆形背景上
  - sunny → 🌾 `#FDF6E3` 背景
  - rainy → 🌧️ `#E8F1FF` 背景
  - foggy → 🌫️ `#F0F4F8` 背景
  - cold → ❄️ `#E8F4FF` 背景
- **主文案**：`preview` 字段（≤15 字），16px Bold
- **副文案**："{count} 条农事建议"，13px，次要色
- **背景**：`#FFFFFF` 卡片 + `shadowV2.light`
- **圆角**：24px（`borderRadiusV2.xxl`）
- **点击**：整卡片可点击，右侧有 `chevron-right` 图标

### 2. 详情页设计

新建 `AdviceDetailScreen`，全屏页面：

**Header 区域**（120-140px）：
- 大灵宠 Emoji（72px）
- 天气总结文案（`preview`）
- 日期标签
- 背景使用与天气匹配的浅色渐变

**建议列表区域**：
- 每条建议一个卡片，但**去掉独立背景**，改为：
  - 左侧彩色优先级竖条（priority 1=红色, 2=橙色, 3=蓝色）
  - 标题 + 详情文本
  - 右侧 icon Emoji
- 卡片间距 12px
- 整体使用 `ScrollView` 支持长列表

**底部操作栏**：
- "咨询农事顾问"按钮（主色渐变），跳转到 `AgentChat`

### 3. 数据流设计

```
HomeScreen
├── CompactAdviceCard
│   ├── preview: dailyAdvice.preview
│   ├── itemCount: dailyAdvice.items.length
│   └── onPress → navigation.navigate('AdviceDetail')
│
AdviceDetailScreen (route.params: { items, preview, weatherCondition })
├── Header (preview + weatherCondition)
├── ItemsList (dailyAdvice.items)
└── Footer → AgentChat
```

### 4. API Schema 变更

**Backend `DailyAdviceResponse`**:
```python
class DailyAdviceResponse(BaseModel):
    cycle_id: int | None = None
    preview: str = Field(default="", max_length=20)  # 新增
    items: list[AdviceItem]
    created_at: datetime
```

**Frontend `DailyAdvice` type**:
```typescript
interface DailyAdvice {
  cycle_id: number | null;
  preview: string;  // 新增
  advice: string;   // computed_field 保持兼容
  items: AdviceItem[];
  created_at: string;
}
```

### 5. Prompt 模板更新

原 Prompt（line 277-281）:
```
"请生成今天的农事建议。你必须以 JSON 数组格式回复..."
```

新 Prompt:
```
"请生成今天的农事建议。以 JSON 格式回复：
{
  \"preview\": \"≤15字今日一句话总结\",
  \"items\": [
    {\"title\":\"≤10字结论\",\"detail\":\"≤40字原因\",\"priority\":1到3,\"icon\":\"emoji\"}
  ]
}。最多5条，按紧急程度排序。"
```

### 6. 解析逻辑更新

`_parse_advice_items` 需要支持两种格式：
- **新格式**: `{"preview": "...", "items": [...]}`
- **旧格式**: `[...]` 或 `{...}`（无 preview，直接是 item）

解析策略：
1. 尝试解析为 dict
2. 如果有 `preview` 字段，提取之；`items` 字段作为 item 列表
3. 如果解析为 list，或无 `preview`，则保持旧逻辑（整个解析结果为 items）
4. `preview` 缺失时默认空字符串

## Risks / Trade-offs

- **[Risk]** LLM 可能不遵循新 Prompt 格式，返回旧格式 JSON → **Mitigation**: 解析逻辑兼容旧格式，preview 缺失时前端 fallback 为 "今日农事建议"
- **[Risk]** 缓存的旧格式数据在刷新前没有 preview → **Mitigation**: 首次刷新后获得 preview；或前端对无 preview 的数据使用 weatherCondition 生成默认文案
- **[Risk]** 详情页从路由参数接收数据，如果用户从深层链接进入可能无数据 → **Mitigation**: AdviceDetailScreen 内部也调用 `fetchDailyAdvice()` 作为 fallback，参数存在时优先使用参数避免重复请求
- **[Trade-off]** 详情页未使用底部 Tab，而是 Stack 导航页面。这符合当前导航模式（WeatherDetail 也是 Stack 页面），保持一致性

## Migration Plan

1. 后端部署：Schema 更新 + Prompt 更新 + 解析逻辑更新
2. 前端部署：类型更新 + 新组件 + 导航更新
3. 用户首次打开 App 时，缓存的旧数据无 preview，显示 fallback 文案
4. 下次刷新或进入详情页时，获取新格式数据

## Open Questions

- 详情页是否需要支持下拉刷新？（建议添加，保持数据新鲜度）
- 灵宠 Emoji 是否应支持自定义？（当前版本不做，后续可考虑）
- 详情页是否展示历史建议？（当前版本只做当日，历史可后续扩展）
