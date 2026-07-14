## ADDED Requirements

### Requirement: Skill 列表 API
系统 SHALL 提供 `GET /admin/skills` 接口，返回所有已注册 skill 的名称、描述、参数 schema、状态。

#### Scenario: 查询 skill 列表
- **WHEN** 调用 `GET /admin/skills`
- **THEN** 返回所有已注册 skill 列表：
```json
[
  {"name": "weather", "description": "获取天气预报", "parameters_schema": {...}, "status": "active"},
  {"name": "get_cost_summary", "description": "成本汇总", "parameters_schema": {...}, "status": "active"}
]
```

### Requirement: Prompt 模板列表 API
系统 SHALL 提供 `GET /admin/prompts` 接口，返回所有已加载 prompt 模板的名称、版本、活跃状态。

#### Scenario: 查询模板列表
- **WHEN** 调用 `GET /admin/prompts`
- **THEN** 返回模板列表：name、version、active、source_file_path

### Requirement: Prompt 渲染预览 API
系统 SHALL 提供 `GET /admin/prompts/{name}/render` 接口，传入变量值后返回渲染后 prompt。

#### Scenario: 渲染预览
- **WHEN** 调用 `GET /admin/prompts/system_base/render?variables={"display_name":"老李"}`
- **THEN** 返回渲染后的完整 prompt 文本

### Requirement: Prompt 热加载 API
系统 SHALL 提供 `POST /admin/prompts/reload` 接口，触发 `PromptRegistry.reload()` 重新加载模板文件。

#### Scenario: 热加载
- **WHEN** 调用 `POST /admin/prompts/reload`
- **THEN** 返回 `{reloaded: true, templates_count: 5}`，后续请求使用新模板

### Requirement: 运行时配置查看 API
系统 SHALL 提供 `GET /admin/config` 接口，返回当前运行时配置。API key SHALL 脱敏显示（仅显示前 4 位 + `***`）。

#### Scenario: 查看配置
- **WHEN** 调用 `GET /admin/config`
- **THEN** 返回 AI 模型名、base_url、enable_thinking、天气坐标、Secrets key 脱敏状态

#### Scenario: Key 脱敏
- **WHEN** `secrets.dashscope_api_key` = `sk-ce0d2f9f940644d5...`
- **THEN** 返回 `sk-ce***...7983c`，完整 key 不出现在响应中

### Requirement: API Key 连通性测试 API
系统 SHALL 提供 `POST /admin/config/validate-key?service=qweather` 接口，验证指定服务的 API key 是否有效。

#### Scenario: 和风天气 key 验证
- **WHEN** 调用 `POST /admin/config/validate-key?service=qweather`
- **THEN** 用 key 调用和风天气 GeoAPI，返回 `{valid: true, latency_ms: 230}` 或 `{valid: false, error: "401 Unauthorized"}`

#### Scenario: 服务不存在
- **WHEN** 调用 `POST /admin/config/validate-key?service=unknown`
- **THEN** 返回 400，提示"未知服务"

### Requirement: 缓存清空 API
系统 SHALL 提供 `POST /admin/cache/clear` 接口，清空所有内存缓存（天气缓存、农场上下文缓存）。

#### Scenario: 清空缓存
- **WHEN** 调用 `POST /admin/cache/clear`
- **THEN** 清空 `@cached` 装饰器的所有缓存，返回 `{cleared: true}`
