## Why

移动端四个底部标签页（首页/AI助手/记账/我的）存在三个核心问题：①首页每次打开都调用 LLM 生成"今日农事建议"导致 API 成本高、加载慢；②"我的"页面放置了 AI 功能快捷入口而非用户设置项，与用户预期不符；③种植报告使用纯文本渲染而非 Markdown，且报告历史无处查看。此外首页信息密度未经设计，报告入口散落在多个位置造成混乱。

## What Changes

- 后端新增"每日建议按天+城市缓存"机制：同一天同一城市直接返回缓存结果，切换城市或手动刷新时重新生成
- 首页移除独立报告区块，精简为：天气 → 建议（缓存+折叠+刷新）→ 快捷操作 → 最近茬口
- AI 助手 Tab 新增顶部 SegmentedControl（对话/报告），报告视图包含生成入口和历史列表
- 报告详情页 `<Text>` 替换为 `MarkdownText` 组件渲染
- "我的"页面重设计：移除 AI 功能入口，新增农场设置、种植偏好、通知设置、数据管理等用户设置项
- 预留多用户/登录体系扩展点（头像+用户信息区域）

## Capabilities

### New Capabilities
- `daily-advice-cache`: 后端每日建议缓存机制，按 farm_id + 日期 + 城市缓存 LLM 生成结果，支持手动刷新失效
- `report-history`: 报告生成历史列表与详情查看，归属 AI 助手 Tab 报告视图
- `user-settings`: 用户设置页面，包含农场设置、种植偏好、通知开关、数据管理

### Modified Capabilities
<!-- 无现有 spec 需要修改 -->

## Impact

- **后端 API**: 新增 `GET /agent/daily` 缓存查询逻辑（需 advice_records 表或 farm_logs 扩展字段）；可能新增 `GET /agent/reports` 报告历史接口
- **数据库**: 新增建议缓存存储（表或文件），报告记录需持久化
- **移动端 store**: agentStore 扩展报告历史状态，新增 settingsStore
- **移动端 UI**: HomeScreen 精简、AgentChatScreen 加 SegmentedControl、SettingsScreen 重写、AgentReportScreen 加 MarkdownText
- **依赖**: 无新外部依赖
