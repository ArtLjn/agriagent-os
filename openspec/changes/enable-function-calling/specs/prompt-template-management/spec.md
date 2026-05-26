## ADDED Requirements

### Requirement: System prompt 包含 tool calling 硬约束
`prompts/base.j2` 的【能力范围】段 SHALL 包含明确的硬约束指令，禁止 LLM 在 skill 覆盖领域编造数据。约束措辞 SHALL 使用"禁止"、"必须"等规范性语言，而非"请"、"建议"等软性语言。

#### Scenario: prompt 包含禁止编造指令
- **WHEN** 渲染 `system_base` 模板
- **THEN** 输出的 prompt 中包含类似"禁止凭记忆回答天气、成本、记录等实时数据，必须调用工具获取"的硬约束语句

#### Scenario: LLM 遵循约束调用 tool
- **WHEN** 用户询问"明天天气"，且 LLM 已接收强化后的 system prompt
- **THEN** LLM 优先调用 `get_weather_forecast` tool 而非直接用自身知识回答

## MODIFIED Requirements

### Requirement: Prompt 模板文件集中存放
所有 Agent system prompt 和任务 prompt SHALL 存放在 `prompts/` 目录下，以 `.j2`（Jinja2 模板）和 `.yaml`（配置）文件形式管理。禁止在业务代码中硬编码超过 20 字的 prompt 字符串。**`prompts/base.j2` SHALL 包含 tool calling 硬约束指令，确保 LLM 在 skill 覆盖领域必须调用工具而非编造数据。**

#### Scenario: 启动时加载模板
- **WHEN** 后端服务启动
- **THEN** `PromptRegistry` 自动扫描 `prompts/` 目录，加载所有 `.j2` 模板和 `.yaml` 配置到内存

#### Scenario: 运行时获取模板
- **WHEN** `advisor.py` 调用 `registry.get("system_base")`
- **THEN** 返回渲染后的 system prompt 字符串，包含注入的变量（如 current_date）**及 tool calling 硬约束指令**

#### Scenario: tool calling 约束在模板中可见
- **WHEN** 查看 `prompts/base.j2` 原始内容
- **THEN** 【能力范围】段包含"禁止"和"必须调用工具"的明确措辞
