## ADDED Requirements

### Requirement: 管理端项目初始化
系统 SHALL 在项目根目录下创建 admin-web/ 目录，使用 React 18 + Vite 5 + TypeScript + Ant Design 5 技术栈。管理端 SHALL 通过 proxy 或配置连接后端 API（默认 http://localhost:8000）。

#### Scenario: 开发服务器启动
- **WHEN** 在 admin-web/ 目录执行 `npm run dev`
- **THEN** Vite 开发服务器在 5173 端口启动，页面显示侧边栏布局和 Dashboard 页面

#### Scenario: API 代理配置
- **WHEN** 前端发起 `/api/*` 请求
- **THEN** Vite proxy 将请求转发到后端 http://localhost:8000，路径去除 /api 前缀

### Requirement: Dashboard 仪表盘页面
系统 SHALL 提供仪表盘页面，展示种植周期状态概览（进行中/已完成数量）、今日天气摘要、AI 每日建议摘要、近期收支趋势。

#### Scenario: 仪表盘数据加载
- **WHEN** 用户打开 Dashboard 页面
- **THEN** 并行请求 cycles、weather、agent/daily、costs/summary 接口，展示数据卡片

#### Scenario: 后端不可用时
- **WHEN** 后端 API 不可达
- **THEN** 各卡片显示错误提示，不阻塞页面渲染

### Requirement: 作物模板管理页面
系统 SHALL 提供作物模板的列表展示、新增、编辑、删除功能。列表以 Ant Design Table 展示，包含名称、品种、生长阶段数量列。新增/编辑使用 Modal 表单，支持动态添加生长阶段。

#### Scenario: 创建作物模板
- **WHEN** 用户点击"新建模板"并填写名称、品种、添加生长阶段（名称 + 天数 + 排序）
- **THEN** 调用 POST /crops/templates 接口，成功后列表刷新并显示新记录

#### Scenario: 删除作物模板
- **WHEN** 用户点击某模板的删除按钮并确认
- **THEN** 调用 DELETE 操作，成功后从列表移除（如有依赖的茬口则提示不可删除）

### Requirement: 茬口管理页面
系统 SHALL 提供种植周期（茬口）的列表展示、新增、详情查看功能。列表显示茬口名称、关联作物模板、开始日期、状态、当前阶段。新增时选择作物模板和开始日期，系统自动推算各阶段时间。

#### Scenario: 创建茬口
- **WHEN** 用户选择作物模板、填写名称、开始日期、地块名称，点击提交
- **THEN** 调用 POST /cycles，成功后列表刷新，新茬口显示自动推算的阶段时间线

#### Scenario: 查看茬口详情
- **WHEN** 用户点击某茬口进入详情页
- **THEN** 展示该茬口的全部阶段时间线、关联的农事日志和成本记录

### Requirement: 农事日志管理页面
系统 SHALL 提供农事日志的列表展示（支持按茬口和操作类型筛选）、新增功能。新增使用 Modal 表单，选择茬口、填写操作类型、日期、备注。

#### Scenario: 按茬口筛选日志
- **WHEN** 用户在日志页面选择某个茬口筛选条件
- **THEN** 列表仅显示该茬口下的日志记录

#### Scenario: 新增日志
- **WHEN** 用户填写操作类型、日期、备注并提交
- **THEN** 调用 POST /logs，成功后列表刷新

### Requirement: 成本记账管理页面
系统 SHALL 提供收支记录的 CRUD、单周期利润统计、年度汇总报表。列表支持按茬口和分类筛选。页面包含统计卡片展示总成本、总收入、净利润。

#### Scenario: 查看周期利润
- **WHEN** 用户选择某个茬口
- **THEN** 显示该茬口的总成本、总收入、净利润统计卡片，以及收支明细列表

#### Scenario: 查看年度汇总
- **WHEN** 用户选择某年
- **THEN** 调用 GET /costs/summary/{year}，展示年度总收支和按分类的明细

### Requirement: AI 助手页面
系统 SHALL 提供对话界面（聊天窗口形式）、每日建议展示、报告生成与历史查询。对话界面支持输入消息并显示 Agent 回复。

#### Scenario: 与 Agent 对话
- **WHEN** 用户在聊天输入框输入消息并发送
- **THEN** 调用 POST /agent/chat，流式或等待完整回复后显示在对话窗口

#### Scenario: 生成报告
- **WHEN** 用户选择周期和报告类型，点击生成
- **THEN** 调用 POST /agent/report，显示生成中的 loading 状态，完成后展示报告内容

### Requirement: 天气预报页面
系统 SHALL 展示未来 N 天的天气预报数据，默认 7 天。以卡片列表形式展示每日天气信息。

#### Scenario: 查看天气预报
- **WHEN** 用户打开天气页面
- **THEN** 调用 GET /weather/forecast，以每日天气卡片形式展示温度、天气状况等信息

### Requirement: 独立 API Tester 页面
系统 SHALL 提供独立的 API 测试页面，左侧列出全部 20 个 API 端点（按模块分组，标注 HTTP 方法和路径），右侧为请求构建器和响应面板。

#### Scenario: 选择端点并发送请求
- **WHEN** 用户点击左侧某端点
- **THEN** 右侧自动填充该端点的 HTTP 方法、路径、请求体模板（基于 Pydantic schema 生成），用户编辑后点击发送，响应面板显示状态码、耗时、格式化 JSON

#### Scenario: 查看响应详情
- **WHEN** 请求完成后
- **THEN** 响应面板显示 HTTP 状态码（颜色区分 2xx/4xx/5xx）、响应时间（ms）、格式化的 JSON 响应体

### Requirement: 内嵌 API 调试组件
系统 SHALL 在每个 CRUD 管理页面的操作栏提供"调试"按钮，点击弹出 Drawer 或 Modal，预填当前页面对应的 API 端点信息，用户可直接发送请求查看响应。

#### Scenario: 在作物页面调试创建接口
- **WHEN** 用户在作物模板页面点击"调试"按钮
- **THEN** 弹出调试面板，预填 POST /crops/templates 和请求体模板，用户可编辑并发送

#### Scenario: 调试面板复用
- **WHEN** 不同页面使用内嵌调试
- **THEN** 共用同一个 ApiDebugger 组件，仅预填的端点信息不同

### Requirement: 侧边栏导航布局
系统 SHALL 使用 Ant Design Layout 组件提供侧边栏 + 内容区的管理后台布局。侧边栏包含 8 个导航项：仪表盘、作物管理、茬口管理、农事日志、成本记账、AI 助手、天气预报、API Tester。

#### Scenario: 页面导航
- **WHEN** 用户点击侧边栏某导航项
- **THEN** 右侧内容区切换到对应页面，侧边栏高亮当前项
