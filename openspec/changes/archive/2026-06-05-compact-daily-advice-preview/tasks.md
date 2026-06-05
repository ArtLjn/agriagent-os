## 1. 后端 Schema 与 API 更新

- [ ] 1.1 修改 `DailyAdviceResponse`，新增 `preview: str = Field(default="", max_length=20)` 字段
- [ ] 1.2 更新 Prompt 模板，要求 LLM 返回 `{"preview": "...", "items": [...]}` 格式
- [ ] 1.3 更新 `_parse_advice_items` 函数，支持解析新格式（提取 preview + items），兼容旧格式 fallback
- [ ] 1.4 更新 `get_daily_advice` 和 `refresh_daily_advice`，传递 preview 到响应
- [ ] 1.5 运行后端测试，确保解析逻辑兼容旧数据：`poetry run pytest tests/test_structured_advice.py -v`

## 2. 前端类型与数据层

- [ ] 2.1 更新 `api/types.ts` 中 `DailyAdvice` 接口，新增 `preview: string`
- [ ] 2.2 更新 `stores/agentStore.ts`（如有类型断言需要调整）
- [ ] 2.3 更新 `api/client.ts` 中 DailyAdvice 相关的类型引用

## 3. 前端首页预览卡片

- [ ] 3.1 创建 `components/CompactAdviceCard.tsx`：
  - 灵宠 Emoji（根据 weatherCondition）+ 圆形背景
  - preview 主文案（16px Bold）
  - 建议数量副文案（13px 次要色）
  - 右侧 chevron-right 图标
  - 整卡片可点击，高度 ~100px
- [ ] 3.2 在 `HomeScreen.tsx` 中替换 `AdviceCard` 为 `CompactAdviceCard`
- [ ] 3.3 实现 preview 为空时的 fallback 逻辑（根据 weatherCondition 生成默认文案）

## 4. 前端详情页

- [ ] 4.1 创建 `screens/advice/AdviceDetailScreen.tsx`：
  - Header：大灵宠 Emoji（72px）+ preview 文案 + 日期
  - 天气渐变背景
  - 建议列表（带优先级彩色竖条）
  - 底部 "咨询农事顾问" 按钮
  - 空状态处理
- [ ] 4.2 在 `navigation/AppNavigator.tsx` 注册 `AdviceDetail` 路由
- [ ] 4.3 更新 `RootStackParamList` 类型定义
- [ ] 4.3 实现无参数时的数据加载 fallback（调用 fetchDailyAdvice）

## 5. 导航与交互

- [ ] 5.1 在 `CompactAdviceCard` 中添加 `onPress` 跳转到 `AdviceDetailScreen`
- [ ] 5.2 在 `AdviceDetailScreen` 底部添加跳转到 `AgentChatScreen` 的按钮
- [ ] 5.3 测试导航流程：首页 → 点击预览卡片 → 详情页 → 点击咨询 → Chat 页面

## 6. 样式与动画

- [ ] 6.1 为 `CompactAdviceCard` 添加 `FadeInSlideUp` 入场动画
- [ ] 6.2 为 `AdviceDetailScreen` 的建议列表添加 `LayoutAnimation` 展开效果
- [ ] 6.3 确保所有样式符合 `app-ui.md` 设计规范（间距、圆角、阴影）

## 7. 测试与验证

- [ ] 7.1 Android 真机/模拟器测试：首页预览卡片高度、点击跳转、详情页展示
- [ ] 7.2 测试旧数据兼容：清空 preview 字段，验证 fallback 文案显示正常
- [ ] 7.3 测试空状态：无建议时预览卡片和详情页的展示
- [ ] 7.4 运行前端 lint：`pnpm lint`（或项目对应的 lint 命令）
- [ ] 7.5 Metro 热更新验证：修改代码后刷新是否正常

## 8. 文档更新

- [ ] 8.1 更新 `docs/` 中相关模块文档（如存在）
- [ ] 8.2 在代码中添加必要的注释（复杂逻辑处）
