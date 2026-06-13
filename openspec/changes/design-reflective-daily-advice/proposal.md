## Why

当前今日建议接口只稳定返回首页缩略字段，详情页需要的判断依据、执行步骤、关联事项仍缺少可追溯结构，容易出现页面展示丰富但内容信源不稳的问题。项目已经引入 Agent Reflection 框架，现在需要把今日建议升级为一个可校验、可重试、可兜底的结构化接口，让 App 首次打开只请求一次也能支撑首页和详情页。

## What Changes

- 将 `GET /agent/daily` 和 `POST /agent/daily/refresh` 升级为同一份 v2 响应结构，单次返回首页经营态势、首页缩略建议和详情页完整建议信息。
- 每条建议拆为 `compact` 与 `detail` 两层：`compact` 给首页列表使用，`detail` 给建议详情页使用。
- 保留 `advice` 兼容字段和旧版 `items[].title/detail/priority/icon` 映射，避免 admin-web 与旧移动端立即破坏。
- 接入 `backend/app/agent/reflector/` 作为今日建议生成后的质检节点，输出通过、重试或兜底决策。
- 建立代码硬校验：JSON schema、候选 ID、禁止内容、字段长度、非空详情、steps/evidence 完整性、priority 不越权。
- 建立有限 retry：LLM 草稿未通过校验时最多修复重试 2 次，仍失败则使用规则层候选生成 fallback 结构。
- 缓存只写入通过校验或规则兜底生成的结构化结果，并在 meta 中记录 schema 版本、候选指纹、生成模式、retry 次数和反思结果。

## Capabilities

### New Capabilities
- `reflective-daily-advice`: 约束今日建议如何接入 Reflection 校验、retry、fallback、缓存元数据和质量追踪。

### Modified Capabilities
- `structured-daily-advice`: 将每日建议响应从简单 `preview + items` 扩展为可同时支撑首页缩略和详情页展示的 v2 结构，同时保留旧字段兼容。
- `daily-advice-preview`: 将首页预览行为调整为消费同一接口中的 `items[].compact`，不再要求详情页二次请求单条建议。

## Impact

- 后端 schema：`backend/app/schemas/agent.py` 需要新增 DailyAdvice v2 子模型，并兼容旧字段。
- 后端服务：`backend/app/services/agent_service.py` 需要将 LLM 生成、结构校验、Reflection、retry、fallback、缓存写入串成稳定链路。
- 反思框架：`backend/app/agent/reflector/` 需要增加今日建议专用检查入口或通用结构化生成检查能力。
- 候选模型：`backend/app/services/daily_advice_models.py` 可扩展为生成稳定 `compact/detail` fallback 所需的类别、来源、默认 actions 和默认 steps。
- Prompt：`backend/prompts/daily_advice.j2` 需要改为 v2 JSON 输出约束，强调只补全文案，不允许新增候选外建议。
- 移动端：`mobile-app/lib/data/api/api_models.dart` 和首页/详情页 view model 需要消费同一份响应结构。
- 测试：新增后端 schema/validator/retry/fallback/cache 测试，以及移动端解析和首页到详情传参测试。
