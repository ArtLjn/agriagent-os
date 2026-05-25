## 1. 后端：每日建议缓存

- [ ] 1.1 创建 advice_cache 数据模型（models/advice_cache.py），字段：id, farm_id, city, date, content, created_at，唯一约束 (farm_id, city, date)
- [ ] 1.2 实现缓存查询逻辑：在 agent_service.py 的 get_daily_advice() 中，先查缓存再调 LLM，命中时附加 X-Cache 头返回
- [ ] 1.3 实现 POST /agent/daily/refresh 接口：删除当天当城市缓存，重新生成
- [ ] 1.4 添加过期清理：查询时自动删除 30 天前的缓存记录
- [ ] 1.5 编写 advice_cache 单元测试（缓存命中、未命中、刷新、过期清理）

## 2. 后端：报告历史接口

- [ ] 2.1 新增 GET /agent/reports 接口，返回当前 farm_id 的报告列表，支持分页（page/size），按 created_at 倒序
- [ ] 2.2 报告列表响应中 content 字段截断为前 200 字
- [ ] 2.3 编写 reports 接口测试（空列表、分页、排序）

## 3. 移动端：首页优化

- [ ] 3.1 AdviceCard 添加刷新按钮（右上角刷新图标），点击调用 refresh API
- [ ] 3.2 agentStore 新增 refreshDailyAdvice() 方法，调用 POST /agent/daily/refresh
- [ ] 3.3 首页 useEffect 调整：fetchDailyAdvice 改为支持缓存响应（无变化时无 loading）
- [ ] 3.4 城市切换时重新调用 fetchDailyAdvice（已由 handleCitySelect 触发）

## 4. 移动端：AI 助手报告视图

- [ ] 4.1 AgentChatScreen 添加顶部 SegmentedControl（对话/报告），切换两个视图
- [ ] 4.2 新建 ReportView 组件：顶部"生成新报告"按钮（周报/月报切换）+ 历史报告列表
- [ ] 4.3 agentStore 扩展：新增 reports 数组和 fetchReports() 方法，调用 GET /agent/reports
- [ ] 4.4 报告列表点击跳转 AgentReportScreen，传入 report_id 加载完整内容
- [ ] 4.5 AgentReportScreen 替换 <Text> 为 <MarkdownText> 渲染报告内容

## 5. 移动端：我的页面重设计

- [ ] 5.1 新建 settingsStore（Zustand + persist）：存储 defaultCity、defaultFarm、crops、reminderTime 等用户设置
- [ ] 5.2 SettingsScreen 移除 AI_SECTION 分组（农事顾问、种植报告）
- [ ] 5.3 SettingsScreen 新增农场设置分组：默认农场（Toast 提示即将上线）、默认城市（复用 CityPicker）
- [ ] 5.4 SettingsScreen 新增种植偏好分组：常种作物（多选）、提醒时间（时间选择器）
- [ ] 5.5 SettingsScreen 新增数据管理分组：导出数据（Toast）、清除缓存（确认弹窗 + 清 AsyncStorage）
- [ ] 5.6 用户信息区域点击时显示"登录功能即将上线"提示
