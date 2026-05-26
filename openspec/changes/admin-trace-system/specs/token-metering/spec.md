## ADDED Requirements

### Requirement: Token 用量实时记录
每次 LLM 调用完成后 SHALL 记录 token 消耗到 `token_daily_stats` 表（累加模式）。

#### Scenario: 记录 token 消耗
- **WHEN** `_llm_node` 收到 LLM 响应，response_metadata 包含 token 统计
- **THEN** `token_daily_stats` 对应 (farm_id, date, model, call_type) 行累加 prompt_tokens / completion_tokens / total_tokens / request_count

#### Scenario: LLM 响应无 token 元数据
- **WHEN** LLM 响应不包含 token 统计（某些模型不返回）
- **THEN** token_usage 记录为 null，不累加到 daily_stats

### Requirement: Token 用量查询 API
系统 SHALL 提供 `GET /admin/stats/tokens` 接口，返回指定 farm 的 token 用量统计。

#### Scenario: 查询近 7 天用量
- **WHEN** 调用 `GET /admin/stats/tokens?farm_id=1&days=7`
- **THEN** 返回每日汇总：
```json
{
  "summary": {"total_tokens": 892400, "total_cost_cny": 0, "total_requests": 1234},
  "daily": [
    {"date": "2026-05-26", "total_tokens": 45230, "requests": 56, "by_model": [...]},
    ...
  ]
}
```

#### Scenario: 按模型分组
- **WHEN** 返回数据包含 `by_model` 字段
- **THEN** 每个 model 单独列出 prompt_tokens / completion_tokens / request_count

### Requirement: Token 配额检查
系统 SHALL 在 LLM 调用前检查当日 token 用量是否超过配额。默认日配额 100,000 tokens。

#### Scenario: 配额内正常调用
- **WHEN** farm_id=1 今日已用 50,000 tokens，配额 100,000
- **THEN** LLM 正常调用

#### Scenario: 超配额拒绝
- **WHEN** farm_id=1 今日已用 101,000 tokens，超配额策略为 `reject`
- **THEN** 返回友好消息"今日用量已达上限"，不调用 LLM

#### Scenario: 超配额降级
- **WHEN** farm_id=1 今日已用 101,000 tokens，超配额策略为 `downgrade`
- **THEN** 切换到更便宜的模型（如 qwen-turbo）继续服务

### Requirement: 配额策略可配置
Token 配额策略 SHALL 可通过 `config.yaml` 配置：日配额数量、超配额行为（reject/downgrade/warn）。

#### Scenario: 配置配额
- **WHEN** `config.yaml` 包含 `token_quota: {daily_limit: 100000, over_quota_action: "warn"}`
- **THEN** 超配额时只记录 warning 日志，不拦截请求

#### Scenario: 未配置时使用默认值
- **WHEN** `config.yaml` 未配置 `token_quota`
- **THEN** 使用默认值 daily_limit=100000, over_quota_action="warn"

### Requirement: 费用估算
系统 SHALL 根据模型定价估算费用（单位：人民币）。qwen3.6-flash 免费模型费用为 0。

#### Scenario: 免费模型费用为 0
- **WHEN** 使用 qwen3.6-flash 模型
- **THEN** estimated_cost_cny = 0

#### Scenario: 付费模型费用计算
- **WHEN** 使用 qwen3.5-plus 模型（假设 ¥0.002/千 token）
- **THEN** estimated_cost_cny = total_tokens × 0.002 / 1000
