## ADDED Requirements

### Requirement: 我的页面移除 AI 功能入口
SettingsScreen SHALL 移除"农事顾问"和"种植报告"两个 AI 功能快捷入口。这些功能的入口已存在于首页快捷操作和 AI 助手 Tab。

#### Scenario: 我的页面不显示 AI 功能
- **WHEN** 用户进入"我的"Tab
- **THEN** 页面不包含"AI 功能"分组，不显示"农事顾问"和"种植报告"菜单项

### Requirement: 用户信息区域预留登录体系
页面顶部 SHALL 显示用户头像和名称区域，未登录时显示默认头像和"农友"名称。点击该区域 SHALL 显示"即将上线"提示。

#### Scenario: 未登录状态
- **WHEN** 用户进入"我的"Tab 且未登录
- **THEN** 显示默认头像图标 + "农友" + "让种植更简单"副标题

#### Scenario: 点击用户信息
- **WHEN** 用户点击头像/名称区域
- **THEN** 显示 Toast 或 Alert 提示"登录功能即将上线"

### Requirement: 农场设置分组
页面 SHALL 包含"农场设置"分组卡片，内含"默认农场"和"默认城市"两个设置项。

#### Scenario: 修改默认城市
- **WHEN** 用户点击"默认城市"
- **THEN** 弹出城市选择器（复用 CityPicker 组件），选择后保存到 settingsStore 并同步到 agentStore

#### Scenario: 修改默认农场
- **WHEN** 用户点击"默认农场"
- **THEN** 显示当前农场名称（如"睢宁农场"），点击后显示 Toast"多农场管理即将上线"

### Requirement: 种植偏好分组
页面 SHALL 包含"种植偏好"分组卡片，内含"常种作物"和"提醒时间"设置项。

#### Scenario: 设置常种作物
- **WHEN** 用户点击"常种作物"
- **THEN** 显示多选列表（西瓜、豆角、番茄等），确认后保存到 settingsStore

#### Scenario: 设置提醒时间
- **WHEN** 用户点击"提醒时间"
- **THEN** 显示时间选择器，确认后保存到 settingsStore

### Requirement: 数据管理分组
页面 SHALL 包含"数据"分组卡片，内含"导出数据"和"清除缓存"两个操作项。

#### Scenario: 导出数据
- **WHEN** 用户点击"导出数据"
- **THEN** 显示 Toast"数据导出功能即将上线"

#### Scenario: 清除缓存
- **WHEN** 用户点击"清除缓存"
- **THEN** 显示确认弹窗"确定要清除所有缓存数据吗？"，确认后清除 AsyncStorage 中缓存的建议数据

### Requirement: 关于分组
页面 SHALL 包含"关于"分组卡片，内含版本号、使用指南和关于信息。

#### Scenario: 查看版本
- **WHEN** 用户查看"关于"分组
- **THEN** 显示"版本 v1.0"、"使用指南"（可跳转）、"关于 - 智能种植管理平台"

### Requirement: Prompt 版本偏好字段
settingsStore SHALL 新增 `promptVersion` 字段，用于预留用户级 Prompt 版本偏好。MVP 阶段后端支持该字段存储和读取，但 UI 不展示版本切换入口。

#### Scenario: 保存 Prompt 版本偏好
- **WHEN** 后端返回用户配置包含 `prompt_version: "v2"`
- **THEN** settingsStore 保存该值，随请求发送到后端

#### Scenario: 默认版本
- **WHEN** 用户未设置 Prompt 版本
- **THEN** settingsStore 默认值为 "v1"
