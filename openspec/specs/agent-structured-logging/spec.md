## Purpose

定义 agent-structured-logging 能力的行为要求。

## Requirements

### Requirement: _llm_node 记录 LLM 工具选择决策
`_llm_node` 在获取 LLM 响应后 SHALL 以 INFO 级别记录日志，包含以下字段：
- `tool_calls`：LLM 选择的工具名称列表（如无 tool_calls 则为 `[]`）
- `model`：当前使用的模型名称
- 当 LLM 直接回复文本时，记录回复长度（`reply_len` 字段）

#### Scenario: LLM 选择调用工具
- **WHEN** LLM 返回包含 tool_calls 的响应
- **THEN** 日志输出 `LLM 工具选择 | tool_calls=[get_weather_forecast] | model=qwen3.6-flash`

#### Scenario: LLM 直接回复
- **WHEN** LLM 返回纯文本回复
- **THEN** 日志输出 `LLM 直接回复 | reply_len=42 | model=qwen3.6-flash`

### Requirement: Skill 发现日志
`get_skill_manager()` 初始化时 SHALL 以 INFO 级别记录每个已加载 Skill 的名称和描述。`_build_registry()` 构建注册表时 SHALL 以 DEBUG 级别记录每个注册的 Skill。

#### Scenario: 服务启动时 Skill 发现
- **WHEN** SkillManager 首次初始化
- **THEN** 日志输出每个 Skill 的名称，如 `Skill 已加载 | name=get_weather_forecast | desc=获取天气预报...`

### Requirement: Skill 执行结构化日志
`_parallel_tool_node` 中每个 Skill 调用 SHALL 记录：
- 开始：INFO 级别，包含 `skill` 名称和参数摘要
- 完成：INFO 级别，包含 `skill` 名称、结果摘要（截断 120 字符）、耗时毫秒
- 失败：ERROR 级别，包含 `skill` 名称和异常信息

#### Scenario: Skill 正常执行
- **WHEN** Skill `ainvoke` 成功返回
- **THEN** 日志输出 `Skill 完成 | name=get_weather_forecast | duration_ms=230 | result=明天晴，最高温 28°C...`

#### Scenario: Skill 执行失败
- **WHEN** Skill `ainvoke` 抛出异常
- **THEN** 日志输出 `Skill 失败 | name=get_weather_forecast | error=API timeout`

### Requirement: Prompt 渲染日志
`render_prompt` SHALL 以 DEBUG 级别记录模板名称、是否命中注册表（`hit=true/false`）、渲染变量 key 列表。渲染失败回退时 SHALL 以 WARNING 级别记录。

#### Scenario: 模板命中注册表
- **WHEN** 请求的模板在注册表中存在
- **THEN** 日志输出 `模板渲染 | name=system_base | hit=true | vars=[farm_context_summary, display_name]`

#### Scenario: 模板未命中回退默认
- **WHEN** 请求的模板不在注册表中
- **THEN** 日志输出 `模板未注册 | name=system_base | 使用内置默认`（WARNING 级别，已有行为保持不变）

### Requirement: Pending Action 生命周期日志
`pending_actions.py` 的 `store_pending`、`get_pending`、`remove_pending` SHALL 以 INFO 级别记录操作。`get_pending` 超时清理时 SHALL 以 WARNING 级别记录。`detect_user_intent` SHALL 以 DEBUG 级别记录检测结果。

#### Scenario: 存储 pending action
- **WHEN** 调用 `store_pending`
- **THEN** 日志输出 `Pending action 已存储 | farm_id=1 | action_id=abc123 | skill=create_cost_record`

#### Scenario: Pending action 超时
- **WHEN** `get_pending` 发现 action 已超过 5 分钟
- **THEN** 日志输出 `Pending action 已超时 | farm_id=1 | skill=create_cost_record`（WARNING 级别）

#### Scenario: 用户意图检测
- **WHEN** 调用 `detect_user_intent`
- **THEN** 日志输出 `意图检测 | message=确认 | intent=confirm`（DEBUG 级别）

### Requirement: LLM 客户端初始化日志
`get_llm()` 首次创建 `ChatOpenAI` 实例时 SHALL 以 INFO 级别记录模型名称和 base_url（脱敏）。

#### Scenario: 首次初始化 LLM
- **WHEN** `get_llm()` 首次被调用且 `LLM_INSTANCE` 为 None
- **THEN** 日志输出 `LLM 客户端初始化 | model=qwen3.6-flash | base_url=https://dashscope.aliyuncs.com/...`

### Requirement: Report Agent 日志覆盖
`report.py` 的 `generate_cycle_report` 函数 SHALL 在开始生成时记录 INFO 日志（report 类型、cycle_id），在完成时记录 INFO 日志（结果长度、耗时）。

#### Scenario: 生成报告
- **WHEN** 调用 `generate_cycle_report`
- **THEN** 日志输出 `报告生成开始 | type=cycle | cycle_id=1` 和 `报告生成完成 | len=1024 | duration_ms=3200`
