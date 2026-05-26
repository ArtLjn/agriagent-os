## ADDED Requirements

### Requirement: SecretsConfig 统一密钥管理
系统 SHALL 在 `config.py` 中提供 `SecretsConfig` 类，集中持有所有第三方 API key。包括但不限于 `dashscope_api_key`、`qweather_api_key`、`langsmith_api_key`。

#### Scenario: 从 config.yaml 读取密钥
- **WHEN** `config.yaml` 包含 `secrets: { qweather_api_key: "QW123" }`
- **THEN** `settings.secrets.qweather_api_key` 返回 `"QW123"`

#### Scenario: 环境变量优先于 config.yaml
- **WHEN** 环境变量 `SECRETS__QWEATHER_API_KEY=QW456` 已设置，同时 config.yaml 也有 `secrets.qweather_api_key`
- **THEN** `settings.secrets.qweather_api_key` 返回环境变量值 `"QW456"`

#### Scenario: 密钥为空时安全降级
- **WHEN** `qweather_api_key` 未配置（空字符串）
- **THEN** 天气服务降级为纯 Open-Meteo 模式，服务不报错不崩溃

### Requirement: 业务 Config 不再直接持有 api_key
`AIConfig`、`LangSmithConfig` 等 SHALL 从各自类中移除 `api_key` 字段。业务代码通过 `settings.secrets.xxx_key` 访问密钥。

#### Scenario: AI 模块获取 API key
- **WHEN** `app/core/llm.py` 需要 DashScope API key
- **THEN** 通过 `settings.secrets.dashscope_api_key` 获取，而非 `settings.ai.api_key`

#### Scenario: 向后兼容过渡期
- **WHEN** 旧配置文件仍使用 `ai.api_key` 而非 `secrets.dashscope_api_key`
- **THEN** 系统优先使用 `secrets.dashscope_api_key`，若为空则 fallback 到 `ai.api_key`，并打印 deprecation warning

### Requirement: 密钥不写入日志或错误信息
系统 SHALL 确保任何 API key 不会出现在日志、错误消息、API 响应或 SkillResult 中。

#### Scenario: API 请求失败时脱敏
- **WHEN** 和风天气 API 返回 401（key 无效）
- **THEN** 错误日志记录"和风天气 API 认证失败"，不包含实际 key 值
