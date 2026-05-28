## 1. 后端 API — 作物模板自然语言解析

- [ ] 1.1 在 `app/schemas/crop.py` 新增 `CropTemplateParseRequest` 和 `CropTemplateParseResponse` schema
- [ ] 1.2 在 `app/agent/prompt_registry.py` 注册 `crop_template_parse` prompt（复用 skill 的 system prompt）
- [ ] 1.3 在 `app/api/crop.py` 新增 `POST /crops/templates/parse` 端点，调用 LLM 解析并返回结构化数据
- [ ] 1.4 为 parse 端点添加幂等键缓存（参考 `POST /costs/parse`）
- [ ] 1.5 后端测试：正常解析、含品种解析、解析失败回退

## 2. 移动端 API 客户端

- [ ] 2.1 在 `FarmManagerMobile/src/api/client.ts` 的 `cropApi` 中新增 `parseTemplate(description: string)` 方法
- [ ] 2.2 定义 `CropTemplateParseResponse` TypeScript 类型

## 3. 移动端 — 作物模板创建页面

- [ ] 3.1 新建 `FarmManagerMobile/src/screens/crop/CropTemplateCreateScreen.tsx`
- [ ] 3.2 实现页面顶部智能输入区（自然语言输入框 + 示例标签 + 提交按钮）
- [ ] 3.3 实现作物名称和品种输入字段
- [ ] 3.4 实现生长阶段列表（FlatList，每行显示名称/天数/任务/删除按钮）
- [ ] 3.5 实现"添加阶段"按钮和空状态
- [ ] 3.6 实现表单验证（名称必填、阶段数 ≥ 1、天数 1-365）
- [ ] 3.7 实现保存逻辑：调 `POST /crops/templates` 创建，成功后返回列表页
- [ ] 3.8 实现加载态和错误处理

## 4. 移动端 — 首页快捷功能改造

- [ ] 4.1 修改 `HomeScreen.tsx` 的 `QUICK_ACTIONS`：保留"种植规划"，新增"作物模板"，移除"农事提醒"、"天气趋势"、"病虫害识别"
- [ ] 4.2 为"作物模板"快捷按钮配置图标（`seed` 或 `sprout`）、背景色 `#FFF8E8`

## 5. 移动端 — 导航与列表页更新

- [ ] 5.1 在 `AppNavigator.tsx` 注册 `CropTemplateCreate` 路由
- [ ] 5.2 修改 `CropTemplateScreen.tsx`，将"+"按钮的 Alert 改为导航到 `CropTemplateCreate`
- [ ] 5.3 创建成功后刷新列表数据

## 6. 验证

- [ ] 6.1 后端：运行 `poetry run pytest` 确保新增测试通过
- [ ] 6.2 移动端：启动 Metro，验证创建流程（智能创建 + 手动创建 + 表单验证 + 返回列表）
- [ ] 6.3 移动端：验证首页快捷按钮仅显示2个，且点击正确导航
