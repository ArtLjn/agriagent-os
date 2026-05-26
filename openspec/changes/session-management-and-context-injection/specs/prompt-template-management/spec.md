## MODIFIED Requirements

### Requirement: Prompt 模板文件集中存放
所有 Agent system prompt 和任务 prompt SHALL 存放在 `prompts/` 目录下，以 `.j2`（Jinja2 模板）和 `.yaml`（配置）文件形式管理。禁止在业务代码中硬编码超过 20 字的 prompt 字符串。`prompts/base.j2` SHALL 包含 `<user_context>` XML 段，注入用户所在城市、称呼、当前季节等结构化信息。

#### Scenario: 启动时加载模板
- **WHEN** 后端服务启动
- **THEN** `PromptRegistry` 自动扫描 `prompts/` 目录，加载所有 `.j2` 模板和 `.yaml` 配置到内存

#### Scenario: 运行时获取模板
- **WHEN** `advisor.py` 调用 `registry.get("system_base")`
- **THEN** 返回渲染后的 system prompt 字符串，包含注入的变量（current_date、display_name）**及 `<user_context>` 结构化用户上下文**

#### Scenario: user_context 段正确渲染
- **WHEN** `render_prompt("system_base", variables={"farm_location": "苏州", "display_name": "老李", "current_season": "春季"})`
- **THEN** 输出包含 `<user_context><location>苏州</location><name>老李</name><season>春季</season></user_context>`

#### Scenario: location 为空时条件渲染
- **WHEN** `farm_location` 为空字符串或 None
- **THEN** `<user_context>` 段不包含 `<location>` 节点

### Requirement: 模板支持变量注入
Prompt 模板 SHALL 支持通过变量注入动态数据。内置变量包括 `current_date`、`current_time`、`current_weekday`，自定义变量由调用方传入。**新增内置变量 `farm_location`、`display_name`、`current_season`**，用于 `<user_context>` 段渲染。

#### Scenario: 注入当前日期
- **WHEN** `render_prompt("cost_parse", description="人工费300")` 被调用
- **THEN** 模板中 `{{ current_date }}` 被替换为 "2026-05-25"（客户端传入或服务端计算）

#### Scenario: 自定义变量注入
- **WHEN** `render_prompt("report", cycle_id=5)` 被调用
- **THEN** 模板中 `{{ cycle_id }}` 被替换为 5

#### Scenario: 注入农场位置
- **WHEN** `render_prompt("system_base", variables={"farm_location": "苏州"})` 被调用
- **THEN** 模板中 `{{ farm_location }}` 被替换为"苏州"
