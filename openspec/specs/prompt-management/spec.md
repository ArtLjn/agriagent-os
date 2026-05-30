## Requirements

### Requirement: Prompt 模板文件集中存放
所有 Agent system prompt 和任务 prompt SHALL 存放在 `prompts/` 目录下，以 `.j2`（Jinja2 模板）、`.yaml`（配置）和 `snippets/` 子目录（可复用片段）形式管理。禁止在业务代码中硬编码超过 20 字的 prompt 字符串。`prompts/base.j2` SHALL 包含工具调用硬约束指令（"禁止编造数据，必须调用工具"），但 SHALL NOT 包含具体工具名称或触发规则（路由由 `tool_selector.py` + `Tool.description` 处理）。`prompts/base.j2` 或组合后的 system prompt SHALL 包含 `<user_context>` XML 段，注入用户所在城市、称呼、当前季节等结构化信息。

#### Scenario: 启动时加载模板
- **WHEN** 后端服务启动
- **THEN** `PromptRegistry` 自动扫描 `prompts/` 目录，加载所有 `.j2` 模板和 `.yaml` 配置到内存；`PromptComposer` 加载 `compositions` 配置和 `snippets/` 目录

#### Scenario: 运行时获取模板
- **WHEN** `advisor.py` 调用 `composer.compose("system_base", variables={...})`
- **THEN** 返回组合后的 system prompt 字符串，包含注入的变量、工具调用硬约束（无具体工具名）、及 `<user_context>` 结构化用户上下文

#### Scenario: tool calling 约束不含工具名
- **WHEN** 渲染 `system_base` 模板
- **THEN** 【安全护栏】段包含"禁止"和"必须调用工具"的明确措辞，但不包含 `get_weather_forecast`、`get_farm_status` 等具体工具函数名

### Requirement: System prompt 包含 tool calling 硬约束
组合后的 system prompt SHALL 包含明确的硬约束指令（归入 P1 Safety 层级），禁止 LLM 在 skill 覆盖领域编造数据。约束措辞 SHALL 使用"禁止"、"必须"等规范性语言。约束 SHALL NOT 包含具体工具名到触发场景的映射规则。

#### Scenario: prompt 包含禁止编造指令
- **WHEN** 渲染 `system_base` 组合
- **THEN** 输出的 prompt 中包含"禁止凭记忆回答天气、成本、记录等实时数据，必须调用工具获取"的硬约束语句

#### Scenario: prompt 不包含工具路由规则
- **WHEN** 渲染 `system_base` 组合
- **THEN** 输出的 prompt 中不包含"用户提到天气 → 调用 get_weather_forecast"等触发规则文本

#### Scenario: LLM 遵循约束调用 tool
- **WHEN** 用户询问"明天天气"，且 LLM 已接收强化后的 system prompt
- **THEN** LLM 通过 `Tool.description` + `tool_selector` 匹配并调用 `get_weather_forecast` tool

### Requirement: 模板支持变量注入
Prompt 模板 SHALL 支持通过变量注入动态数据。内置变量包括 `current_date`、`current_time`、`current_weekday`，自定义变量由调用方传入。新增内置变量 `farm_location`、`display_name`、`current_season`，用于 `<user_context>` 段渲染。

#### Scenario: 注入当前日期
- **WHEN** `render_prompt("cost_parse", description="人工费300")` 被调用
- **THEN** 模板中 `{{ current_date }}` 被替换为 "2026-05-25"（客户端传入或服务端计算）

#### Scenario: 自定义变量注入
- **WHEN** `render_prompt("report", cycle_id=5)` 被调用
- **THEN** 模板中 `{{ cycle_id }}` 被替换为 5

#### Scenario: 注入农场位置
- **WHEN** `render_prompt("system_base", variables={"farm_location": "苏州"})` 被调用
- **THEN** 模板中 `{{ farm_location }}` 被替换为"苏州"

#### Scenario: user_context 段正确渲染
- **WHEN** `render_prompt("system_base", variables={"farm_location": "苏州", "display_name": "老李", "current_season": "春季"})`
- **THEN** 输出包含 `<user_context><location>苏州</location><name>老李</name><season>春季</season></user_context>`

#### Scenario: location 为空时条件渲染
- **WHEN** `farm_location` 为空字符串或 None
- **THEN** `<user_context>` 段不包含 `<location>` 节点

### Requirement: Prompt 版本注册表
系统 SHALL 维护 `PromptRegistry`，支持注册多个版本的同名 prompt，并能切换活跃版本。版本号格式为 `v{N}`（如 v1, v2）。

#### Scenario: 注册新版本
- **WHEN** 调用 `registry.register("system_base", "v2", new_template)`
- **THEN** "system_base" 的 v2 版本被存储，不影响当前活跃版本

#### Scenario: 切换活跃版本
- **WHEN** 调用 `registry.set_active("system_base", "v2")`
- **THEN** 后续 `registry.get("system_base")` 返回 v2 版本模板

#### Scenario: 获取指定版本
- **WHEN** 调用 `registry.get("system_base", version="v1")`
- **THEN** 返回 v1 版本，不受活跃版本切换影响

### Requirement: Prompt 热加载
`PromptRegistry` SHALL 支持从文件系统重新加载所有模板，无需重启服务。热加载操作 SHALL 是线程安全的。

#### Scenario: 编辑模板后热加载
- **WHEN** 运维人员修改 `prompts/system_base.j2` 并保存
- **THEN** 调用 `registry.reload()` 后，新模板内容立即生效

#### Scenario: 并发读取安全
- **WHEN** 多个请求同时读取 prompt 模板
- **THEN** 所有请求都能正常获取模板，无并发错误

### Requirement: 模板语法错误兜底
如果模板文件存在 Jinja2 语法错误，`PromptRegistry` SHALL 回退到内置默认 prompt，并记录错误日志。服务 SHALL 不因模板错误而崩溃。

#### Scenario: 模板语法错误
- **WHEN** `prompts/system_base.j2` 包含未闭合的 `{% if %}`
- **THEN** 启动时记录错误日志，使用代码内置的默认 system prompt，服务正常启动
