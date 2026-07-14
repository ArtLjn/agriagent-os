## MODIFIED Requirements

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
- **THEN** 【安全护栏】段包含"禁止"和"必须调用工具"的明确措辞，但不包含 `weather`、`get_farm_status` 等具体工具函数名

### Requirement: System prompt 包含 tool calling 硬约束
组合后的 system prompt SHALL 包含明确的硬约束指令（归入 P1 Safety 层级），禁止 LLM 在 skill 覆盖领域编造数据。约束措辞 SHALL 使用"禁止"、"必须"等规范性语言。约束 SHALL NOT 包含具体工具名到触发场景的映射规则。

#### Scenario: prompt 包含禁止编造指令
- **WHEN** 渲染 `system_base` 组合
- **THEN** 输出的 prompt 中包含"禁止凭记忆回答天气、成本、记录等实时数据，必须调用工具获取"的硬约束语句

#### Scenario: prompt 不包含工具路由规则
- **WHEN** 渲染 `system_base` 组合
- **THEN** 输出的 prompt 中不包含"用户提到天气 → 调用 weather"等触发规则文本

#### Scenario: LLM 遵循约束调用 tool
- **WHEN** 用户询问"明天天气"，且 LLM 已接收强化后的 system prompt
- **THEN** LLM 通过 `Tool.description` + `tool_selector` 匹配并调用 `weather` tool
