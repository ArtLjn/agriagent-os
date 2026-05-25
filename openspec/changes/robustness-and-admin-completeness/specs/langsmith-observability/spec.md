## ADDED Requirements

### Requirement: LangSmith 自动追踪
系统 SHALL 在配置了 `LANGSMITH_API_KEY` 环境变量时，自动将所有 LLM 调用、工具调用和 Agent 图执行步骤上报到 LangSmith。

#### Scenario: 配置了 API Key 自动上报
- **WHEN** 环境变量 `LANGSMITH_API_KEY` 已设置且 `LANGCHAIN_TRACING_V2=true`
- **THEN** 每次 Agent 调用的完整 trace（包含 LLM 输入/输出、工具调用/返回、耗时）上报到 LangSmith

#### Scenario: 未配置 API Key 不上报
- **WHEN** 环境变量 `LANGSMITH_API_KEY` 未设置
- **THEN** 系统正常运行，不上报 trace，不影响功能

### Requirement: Trace 元数据标注
每次 Agent 调用 SHALL 在 LangSmith trace 上附加元数据：farm_id、请求类型（chat/daily_advice/report）。

#### Scenario: Chat 请求标注元数据
- **WHEN** 用户发起 Agent 对话请求
- **THEN** LangSmith trace 包含 `metadata.farm_id` 和 `metadata.request_type="chat"`

#### Scenario: 报告请求标注元数据
- **WHEN** 用户请求生成周报
- **THEN** LangSmith trace 包含 `metadata.farm_id` 和 `metadata.request_type="report"`

### Requirement: LangSmith 配置项
后端 config.yaml SHALL 新增 `langsmith` 配置段，包含 `api_key`、`project_name`、`enabled` 字段。

#### Scenario: 通过 config.yaml 配置
- **WHEN** config.yaml 中设置 `langsmith.enabled: true` 和 `langsmith.project_name: "farm-manager"`
- **THEN** LangSmith 使用指定项目名上报 trace

#### Scenario: 环境变量优先
- **WHEN** 同时设置了 config.yaml 和环境变量 `LANGSMITH_API_KEY`
- **THEN** 环境变量优先级高于 config.yaml

### Requirement: pip 依赖
后端 requirements.txt SHALL 新增 `langsmith` 依赖。

#### Scenario: 安装依赖后可运行
- **WHEN** 执行 `pip install -r requirements.txt`
- **THEN** langsmith 包正确安装，LangChain 自动集成
