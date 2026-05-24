## 1. 后端配置静态化（yaml-config）

- [ ] 1.1 requirements.txt 新增 pyyaml 依赖并安装
- [ ] 1.2 创建 backend/config.yaml.example 模板文件（含 server/database/ai/weather 分组及注释）
- [ ] 1.3 创建 backend/config.yaml 实际配置文件（.gitignore 中忽略）
- [ ] 1.4 重构 backend/app/core/config.py：Settings 类改为嵌套模型（ServerConfig/DatabaseConfig/AIConfig/WeatherConfig），添加 YAML custom_settings_source
- [ ] 1.5 更新 .gitignore 忽略 config.yaml
- [ ] 1.6 验证后端启动正常，配置从 YAML 正确加载

## 2. 多租户基础（multi-tenant-foundation）

- [ ] 2.1 创建 backend/app/models/farm.py：Farm 模型（id/name/owner_name/location/created_at）
- [ ] 2.2 在 models/__init__.py 导出 Farm
- [ ] 2.3 修改 crop_templates 模型：添加 farm_id 外键指向 farms.id
- [ ] 2.4 修改 crop_cycles 模型：添加 farm_id 外键
- [ ] 2.5 修改 farm_logs 模型：添加 farm_id 外键
- [ ] 2.6 修改 cost_records 模型：添加 farm_id 外键
- [ ] 2.7 修改 advice_records 模型：添加 farm_id 外键
- [ ] 2.8 修改 report_records 模型：添加 farm_id 外键
- [ ] 2.9 创建 backend/app/api/deps.py 中 get_current_farm 依赖（当前硬编码返回 farm_id=1）
- [ ] 2.10 修改所有 service 层函数：查询追加 farm_id 过滤，创建自动填充 farm_id
- [ ] 2.11 修改 6 个路由模块（crop/cycle/log/cost/agent/weather）：注入 farm: Farm = Depends(get_current_farm)
- [ ] 2.12 添加种子数据逻辑：lifespan 中自动创建默认农场（farm_id=1）
- [ ] 2.13 删除旧 farm_manager.db，重新建库验证全部表结构
- [ ] 2.14 运行已有测试并修复因 farm_id 引入的失败用例

## 3. admin-web 项目初始化

- [ ] 3.1 在项目根目录执行 npm create vite@latest admin-web -- --template react-ts
- [ ] 3.2 安装依赖：antd、@ant-design/icons、react-router-dom、axios
- [ ] 3.3 配置 vite.config.ts：添加 /api proxy 到 http://localhost:8000
- [ ] 3.4 创建 src/layouts/AdminLayout.tsx：Ant Design Layout Sider + Content 结构
- [ ] 3.5 创建 src/App.tsx：React Router 路由配置（8 个页面路由）
- [ ] 3.6 创建 src/api/client.ts：Axios 实例（baseURL 配置、响应拦截器）

## 4. admin-web API 层

- [ ] 4.1 创建 src/api/crops.ts：作物模板 CRUD 函数（listTemplates/getTemplate/createTemplate）
- [ ] 4.2 创建 src/api/cycles.ts：茬口 CRUD 函数（listCycles/getCycle/createCycle）
- [ ] 4.3 创建 src/api/logs.ts：日志 CRUD 函数（listLogs/createLog）
- [ ] 4.4 创建 src/api/costs.ts：成本 CRUD + 统计函数（listRecords/createRecord/getCycleProfit/getYearlySummary）
- [ ] 4.5 创建 src/api/agent.ts：Agent API 函数（chat/getDailyAdvice/generateReport/getAdviceHistory/getReportHistory）
- [ ] 4.6 创建 src/api/weather.ts：天气查询函数（getForecast）

## 5. admin-web 公共组件

- [ ] 5.1 创建 src/components/ApiDebugger/index.tsx：可复用 API 调试组件（请求方法/URL/Headers/Body 编辑 + 响应面板）
- [ ] 5.2 创建 src/components/ApiDebugger/request-editor.tsx：请求构建器（JSON Body 编辑器、Query 参数表单）
- [ ] 5.3 创建 src/components/ApiDebugger/response-panel.tsx：响应面板（状态码、耗时、格式化 JSON）

## 6. admin-web 页面 — Dashboard

- [ ] 6.1 创建 src/pages/Dashboard/index.tsx：仪表盘页面，展示周期概览卡片、天气摘要、AI 建议摘要、收支趋势

## 7. admin-web 页面 — 业务 CRUD（Crops/Cycles/Logs/Costs）

- [ ] 7.1 创建 src/pages/Crops/index.tsx：作物模板列表页（Table + 新建/编辑 Modal + 删除确认）
- [ ] 7.2 创建 src/pages/Cycles/index.tsx：茬口列表页（Table + 新建 Modal + 当前阶段标签）
- [ ] 7.3 创建 src/pages/Cycles/Detail.tsx：茬口详情页（阶段时间线 + 关联日志 + 关联成本）
- [ ] 7.4 创建 src/pages/Logs/index.tsx：农事日志列表页（筛选条件 + 新增 Modal）
- [ ] 7.5 创建 src/pages/Costs/index.tsx：成本记账页（统计卡片 + 收支列表 + 年度汇总选择器）

## 8. admin-web 页面 — AI / 天气

- [ ] 8.1 创建 src/pages/Agent/index.tsx：AI 助手页（聊天窗口 + 建议查看 + 报告生成 + 历史查询 Tabs）
- [ ] 8.2 创建 src/pages/Weather/index.tsx：天气页面（天气预报卡片列表，支持天数参数）

## 9. admin-web 页面 — API Tester

- [ ] 9.1 创建 src/pages/ApiTester/index.tsx：独立 API Tester 页面（左侧端点列表 + 右侧请求/响应面板）
- [ ] 9.2 定义全部 20 个端点的元数据（方法/路径/描述/请求体模板）

## 10. admin-web 内嵌调试集成

- [ ] 10.1 在 Crops/Cycles/Logs/Costs 各页面操作栏添加"调试"按钮，集成 ApiDebugger Drawer
- [ ] 10.2 各页面的调试按钮预填对应的 API 端点信息和参数模板

## 11. 验收

- [ ] 11.1 后端：删除旧 DB，启动后自动建表和播种，Swagger (/docs) 显示全部端点
- [ ] 11.2 admin-web：npm run dev 启动，8 个页面均可访问且 CRUD 功能正常
- [ ] 11.3 API Tester：可发送全部 20 个端点请求并查看响应
- [ ] 11.4 内嵌调试：各 CRUD 页面调试按钮可正常弹出并发送请求
