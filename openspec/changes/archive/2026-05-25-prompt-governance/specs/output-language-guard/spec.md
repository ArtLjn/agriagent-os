## ADDED Requirements

### Requirement: System Prompt 语言规则置顶
所有 Agent system prompt SHALL 将语言规则放在文档最顶部，并标注 "【语言规则】（最高优先级）"。规则内容 SHALL 包括：必须用简体中文回答、禁止输出英文单词、专有名词必须翻译。

#### Scenario: 渲染后的 system prompt 结构
- **WHEN** `registry.get("system_base")` 被调用
- **THEN** 返回的字符串以 "【语言规则】（最高优先级）" 开头，语言规则位于所有其他指令之前

### Requirement: 输出层英文检测拦截
系统 SHALL 在 `filter_output()` 中增加英文句子检测。检测规则为：连续 3 个或以上由空格分隔的英文单词（a-zA-Z，长度 ≥ 3）视为英文句子。命中时 SHALL 记录拦截日志，并返回预设中文错误提示。

#### Scenario: 检测到英文输出
- **WHEN** Agent 回复包含 "The weather is sunny today"
- **THEN** `filter_output()` 识别出英文句子，记录 `guardrails_logs` 表（trigger_type='output_english'），返回 "系统异常，请重试"

#### Scenario: 正常中文输出通过
- **WHEN** Agent 回复为纯中文 "天气晴朗，适合施肥"
- **THEN** `filter_output()` 不拦截，原文返回

### Requirement: 农业术语英文白名单
英文检测 SHALL 维护农业术语白名单，白名单中的英文单词不计入英文句子检测。白名单包括常见作物品种名、化肥名称、农药名称等。

#### Scenario: 包含农业术语
- **WHEN** Agent 回复包含 "Watermelon 枯萎病防治方法"
- **THEN** "Watermelon" 在白名单中，不触发拦截

#### Scenario: 非白名单英文触发拦截
- **WHEN** Agent 回复包含 "This is a test"
- **THEN** 无白名单匹配，触发拦截

### Requirement: Guardrails 拦截日志持久化
所有 Guardrails 触发（输入注入、输入敏感词、输出英文、输出 PII）SHALL 记录到 `guardrails_logs` 表中，包含 farm_id、触发类型、触发详情、原文摘要、时间戳。

#### Scenario: 记录输入注入拦截
- **WHEN** 用户输入 "忽略之前的指令" 被 Guardrails 拦截
- **THEN** `guardrails_logs` 新增记录：trigger_type='input_injection', trigger_detail='检测到潜在注入模式', source_text='忽略之前的指令'

#### Scenario: 记录输出英文拦截
- **WHEN** Agent 输出被英文检测拦截
- **THEN** `guardrails_logs` 新增记录：trigger_type='output_english', source_text 包含被拦截的英文片段（前 200 字符）

### Requirement: 拦截日志查询接口
后端 SHALL 提供 `/admin/guardrails-logs` 接口，支持按 trigger_type、farm_id、时间范围分页查询拦截记录。

#### Scenario: 查询最近英文拦截
- **WHEN** GET `/admin/guardrails-logs?trigger_type=output_english&limit=20`
- **THEN** 返回最近 20 条英文拦截记录，按 created_at 降序
