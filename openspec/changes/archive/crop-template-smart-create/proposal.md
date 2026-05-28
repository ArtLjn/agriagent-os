## Why

当前移动端作物模板列表页（CropTemplateScreen）的"+"按钮仅弹出"后续开放"提示，用户无法创建模板。同时首页4个快捷功能按钮中，只有"种植规划"有独立页面，其余3个（农事提醒、天气趋势、病虫害识别）均跳转到AI聊天，属于占位功能。作物模板是种植规划的前置依赖（创建茬口需要选择模板），没有模板创建能力导致整个种植流程断链。

## What Changes

- **新增后端 API**：`POST /crops/templates/parse`，接收自然语言描述，调用 LLM 解析出作物名称、品种、生长阶段列表，返回结构化预览数据（不入库）。参考现有 `POST /costs/parse` 的实现模式。
- **新增移动端页面**：`CropTemplateCreateScreen`，支持两种创建模式：
  - **智能创建**：自然语言输入 → 调 parse API → 预填表单 → 用户可编辑确认 → POST `/crops/templates` 正式创建
  - **手动创建**：空白表单，逐项填写作物名称、品种、生长阶段（支持增删改）
- **首页快捷功能改造**：修改 `HomeScreen` 的 `QUICK_ACTIONS`：
  - 保留"种植规划"
  - 新增"作物模板"，跳转到 `CropTemplateCreateScreen`
  - 移除"农事提醒"、"天气趋势"、"病虫害识别"（当前均为跳转到 `AgentChat` 的占位按钮）
- **更新导航**：在 `AppNavigator` 中注册 `CropTemplateCreate` 路由

## Capabilities

### New Capabilities
- `crop-template-smart-create`：作物模板智能创建能力，包含自然语言解析 API 和移动端双模式创建界面

### Modified Capabilities
- `home-screen-redesign`：首页快捷功能按钮列表调整（移除3个占位按钮，新增作物模板入口）

## Impact

- **后端**：`backend/app/api/crop.py` 新增 parse 端点；新增 prompt template（参考 `cost_parse`）
- **移动端**：新增 `CropTemplateCreateScreen.tsx`；修改 `HomeScreen.tsx` 快捷功能区域；更新 `AppNavigator.tsx`
- **API 客户端**：`FarmManagerMobile/src/api/client.ts` 新增 `parseTemplate` 方法
- **无破坏性变更**：现有 `POST /crops/templates` 创建接口保持不变
