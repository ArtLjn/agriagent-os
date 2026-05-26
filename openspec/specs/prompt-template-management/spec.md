## Requirements

### Requirement: Prompt 模板文件集中存放
所有 Agent system prompt 和任务 prompt SHALL 存放在 `prompts/` 目录下，以 `.j2`（Jinja2 模板）和 `.yaml`（配置）文件形式管理。禁止在业务代码中硬编码超过 20 字的 prompt 字符串。**`prompts/base.j2` SHALL 包含 tool calling 硬约束指令，确保 LLM 在 skill 覆盖领域必须调用工具而非编造数据。**

#### Scenario: 启动时加载模板
- **WHEN** 后端服务启动
- **THEN** `PromptRegistry` 自动扫描 `prompts/` 目录，加载所有 `.j2` 模板和 `.yaml` 配置到内存

#### Scenario: 运行时获取模板
- **WHEN** `advisor.py` 调用 `registry.get("system_base")`
- **THEN** 返回渲染后的 system prompt 字符串，包含注入的变量（如 `current_date`）**及 tool calling 硬约束指令**

#### Scenario: tool calling 约束在模板中可见
- **WHEN** 查看 `prompts/base.j2` 原始内容
- **THEN** 【能力范围】段包含"禁止"和"必须调用工具"的明确措辞

### Requirement: System prompt 包含 tool calling 硬约束
`prompts/base.j2` 的【能力范围】段 SHALL 包含明确的硬约束指令，禁止 LLM 在 skill 覆盖领域编造数据。约束措辞 SHALL 使用"禁止"、"必须"等规范性语言，而非"请"、"建议"等软性语言。

#### Scenario: prompt 包含禁止编造指令
- **WHEN** 渲染 `system_base` 模板
- **THEN** 输出的 prompt 中包含类似"禁止凭记忆回答天气、成本、记录等实时数据，必须调用工具获取"的硬约束语句

#### Scenario: LLM 遵循约束调用 tool
- **WHEN** 用户询问"明天天气"，且 LLM 已接收强化后的 system prompt
- **THEN** LLM 优先调用 `get_weather_forecast` tool 而非直接用自身知识回答

### Requirement: 模板支持变量注入
Prompt 模板 SHALL 支持通过变量注入动态数据。内置变量包括 `current_date`、`current_time`、`current_weekday`，自定义变量由调用方传入。

#### Scenario: 注入当前日期
- **WHEN** `render_prompt("cost_parse", description="人工费300")` 被调用
- **THEN** 模板中 `{{ current_date }}` 被替换为 "2026-05-25"（客户端传入或服务端计算）

#### Scenario: 自定义变量注入
- **WHEN** `render_prompt("report", cycle_id=5)` 被调用
- **THEN** 模板中 `{{ cycle_id }}` 被替换为 5

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
