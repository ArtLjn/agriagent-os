## ADDED Requirements

### Requirement: Skill Registry 列表页
系统 SHALL 提供 `/dev/skills` 页面，展示所有已注册 Skill 的名称、描述、参数 schema、状态。

#### Scenario: 展示 Skill 列表
- **WHEN** 用户进入 `/dev/skills` 页面
- **THEN** 调用 `GET /admin/skills`，以卡片或表格形式展示每个 Skill 的 name、description、parameters_schema（JSON 格式化）、status

#### Scenario: 展开 schema 详情
- **WHEN** 用户点击某个 Skill 卡片
- **THEN** 展开显示完整的 JSON Schema（参数定义）

### Requirement: Prompt Inspector 页
系统 SHALL 提供 `/dev/prompts` 页面，列出所有 prompt 模板并支持渲染预览和热加载。

#### Scenario: 展示模板列表
- **WHEN** 用户进入 `/dev/prompts` 页面
- **THEN** 调用 `GET /admin/prompts`，表格展示模板 name、version、active 状态、source 文件路径

#### Scenario: 渲染预览
- **WHEN** 用户点击某个模板的"渲染预览"按钮，输入变量值
- **THEN** 调用 `GET /admin/prompts/{name}/render?variables=...`，展示渲染后完整 prompt 文本

#### Scenario: 热加载模板
- **WHEN** 用户点击"重新加载模板"按钮
- **THEN** 调用 `POST /admin/prompts/reload`，显示加载结果（成功/失败 + 模板数量）

### Requirement: Config & Keys 页
系统 SHALL 提供 `/dev/config` 页面，展示运行时配置、API key 状态、缓存管理。

#### Scenario: 展示运行时配置
- **WHEN** 用户进入 `/dev/config` 页面
- **THEN** 调用 `GET /admin/config`，以 JSON 树或键值对形式展示配置（API key 脱敏显示）

#### Scenario: API key 连通性测试
- **WHEN** 用户点击某个服务的"验证"按钮（如 qweather）
- **THEN** 调用 `POST /admin/config/validate-key?service=qweather`，显示验证结果（有效/无效 + 延迟）

#### Scenario: 清空缓存
- **WHEN** 用户点击"清空缓存"按钮并确认
- **THEN** 调用 `POST /admin/cache/clear`，显示操作结果

### Requirement: 侧边栏分组
系统 SHALL 将 AdminLayout 侧边栏分为"业务管理"和"开发调试"两个菜单组。

#### Scenario: 业务管理组
- **WHEN** AdminLayout 渲染侧边栏
- **THEN** "业务管理"组包含：Dashboard、作物模板、茬口管理、农事日志、成本记账、天气预报、API 测试器

#### Scenario: 开发调试组
- **WHEN** AdminLayout 渲染侧边栏
- **THEN** "开发调试"组包含：链路追踪、Token 看板、Playground、Skill 注册表、Prompt 检查器、配置管理
