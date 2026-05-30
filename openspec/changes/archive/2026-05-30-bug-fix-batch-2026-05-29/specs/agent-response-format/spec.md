## ADDED Requirements

### Requirement: 移动端格式约束
系统 prompt SHALL 包含移动端输出格式约束：禁止 Markdown 表格、禁止代码块、禁止多级嵌套列表，要求使用扁平短句和简单列表。

#### Scenario: LLM 不输出表格
- **WHEN** 用户提问需要对比数据（如天气、收支）
- **THEN** LLM SHALL 用简短文字列表回复，不使用 Markdown 表格语法

#### Scenario: LLM 不输出代码块
- **WHEN** LLM 生成回复
- **THEN** 回复中 SHALL 不包含 ``` 代码块标记

#### Scenario: 报告模板包含格式约束
- **WHEN** 生成种植报告
- **THEN** report.j2 模板 SHALL 指导 LLM 使用 Markdown 格式，使用真实换行而非转义字符

## MODIFIED Requirements

### Requirement: LLM 初始化支持 thinking 模式配置
`get_llm()` 创建 `ChatOpenAI` 实例时 SHALL 读取 `config.yaml` 中的 `ai.enable_thinking` 配置，并通过 `extra_body` 传递给 API。当 `enable_thinking` 为 `false` 或未设置时，SHALL 传递 `enable_thinking: false`。

#### Scenario: 配置关闭思考模式
- **WHEN** `config.yaml` 中 `ai.enable_thinking` 为 `false`
- **THEN** `get_llm()` 创建的 `ChatOpenAI` 实例通过 `extra_body` 传递 `{"enable_thinking": false}`，LLM 不会进入思考模式
