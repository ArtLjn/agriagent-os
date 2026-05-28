## Context

当前 FarmManager Mobile App 使用深青绿（#0D7377）为主色，风格偏向传统管理工具。UI 设计图（docs/ui/app/ui.png + ui.md）提出了一套完整的"轻 AI 农业助手"设计语言，核心变化：

- **配色**: 从深青绿 → 蓝紫绿三主色（#5B8CFF / #8B5CF6 / #3BB273）
- **风格**: 从密集列表 → 大留白卡片式
- **交互**: 从无动效 → 呼吸、浮动、淡入动画
- **定位**: 从"管理系统" → "AI 助手"

技术约束：
- React Native 0.72+（现有项目）
- 必须兼容 Android（主要目标用户为农民，Android 占绝对多数）
- 不引入 Expo（现有项目为纯 RN）
- 动画性能需在低端 Android 设备上流畅（目标设备：千元机）

## Goals / Non-Goals

**Goals:**
1. 实现 UI 设计图中的全部视觉规范（配色、圆角、阴影、字体）
2. 首页完全按设计图重塑（天气卡片、农事建议情绪卡片、快捷操作、AI 宠物）
3. BottomBar 改为毛玻璃 + 胶囊选中态
4. AI 聊天页视觉升级（渐变背景、胶囊推荐问题）
5. 全局动效系统（进入动画、呼吸浮动、点击反馈）
6. 天气详情页新增（小时预报、7 日趋势图）

**Non-Goals:**
1. 不改动后端 API（纯前端 UI 变更）
2. 不新增业务功能（如记账逻辑、AI 对话逻辑保持不变）
3. 不改动物流或数据库模型
4. 不引入全新的导航架构（保持 React Navigation）

## Decisions

### 1. 渐变实现：react-native-linear-gradient

**选择**: 使用 `react-native-linear-gradient`（社区成熟库，5700+ stars）

**理由**: 
- 设计图中大量使用线性渐变（天气卡片、按钮、背景、文字）
- 该库支持 Android/iOS 双端，性能稳定
- 支持角度渐变（如 135deg）

**替代方案**: 
- `expo-linear-gradient`: 不适用（项目不使用 Expo）
- CSS `linear-gradient`: RN 不支持原生 CSS 渐变

### 2. 图表库：victory-native

**选择**: 使用 `victory-native`（基于 react-native-svg）

**理由**:
- 设计图天气详情页需要 7 日温度趋势折线图
- Victory 定制化程度高，可精确控制线条颜色、节点样式
- 支持响应式布局和动画

**替代方案**:
- `react-native-chart-kit`: API 更简单但定制化不足，圆点/线条样式难以精确匹配设计图
- `react-native-svg` 手写：灵活但开发成本高

### 3. AI 宠物动画：纯 CSS 呼吸动画

**选择**: 使用 React Native Animated API 实现呼吸效果（上下浮动 + 缩放）

**理由**:
- 设计图要求"上下 4px 呼吸"，可用 Animated.loop + Animated.sequence 实现
- 无需引入 Lottie（减少包体积 ~200KB）
- 低端设备性能更好

**替代方案**:
- Lottie: 可导入设计师制作的复杂动画，但增加包体积和解析开销

### 4. 毛玻璃效果：降级策略

**选择**: Android 使用半透明背景 + 模糊边框模拟，iOS 使用 `@react-native-community/blur`

**理由**:
- RN 没有原生跨平台毛玻璃组件
- Android 的 `BlurView` 实现参差不齐，部分设备不支持
- 设计图中毛玻璃用于 BottomBar 和天气卡片，半透明 + 边框已能达到 80% 效果

**降级方案**:
```
iOS: BlurView (blurType="light", blurAmount=20)
Android: backgroundColor: "rgba(255,255,255,0.7)" + borderTopWidth: 1
```

### 5. 主题系统：集中式主题对象

**选择**: 扩展现有 `src/theme/colors.ts`，新增 `src/theme/designTokens.ts`

**理由**:
- 现有项目已有主题文件，避免重构成本
- 新增 designTokens 统一管理设计图的尺寸、圆角、阴影、动效参数
- 保持向后兼容（旧组件可逐步迁移）

## Risks / Trade-offs

| 风险 | 缓解措施 |
|------|---------|
| **低端 Android 动画卡顿** | 使用 `useNativeDriver: true`，避免 JS 线程计算；复杂动画（如粒子效果）取消 |
| **渐变文字在 Android 上兼容性问题** | 使用 `react-native-linear-gradient` + `background-clip: text` 的 RN 等效方案（mask 实现），如兼容性差则降级为纯色文字 |
| **包体积增加** | `react-native-linear-gradient` (+50KB)、`victory-native` (+300KB 含依赖)，总计 ~350KB，可接受 |
| **设计图→代码还原度不足** | 建立设计审查清单，每页实现后对照 UI 图检查；关键页面（首页、聊天页）必须 90%+ 还原 |
| **多页面同时改造导致回归风险** | 分 Phase 实施，每 Phase 独立测试；保持现有导航和业务逻辑不变 |

## Migration Plan

无需迁移（纯前端 UI 变更，无数据或 API 变更）。

部署策略：
1. Phase 1（主题 + 首页）合并后发布内测
2. Phase 2（聊天页 + BottomBar）合并后继续内测
3. Phase 3（天气详情 + 账本 + 设置）合并后全量发布

## Open Questions

1. **天气详情页数据源**: 当前 `/weather` API 是否返回小时级数据？如果不返回，是否需要后端新增字段？
2. **AI 宠物点击行为**: 点击后跳转到 AI 聊天页，还是展开快捷菜单？
3. **账本页轻财务风格**: 是否需要新增"总资产"统计 API，还是前端基于现有数据计算？
