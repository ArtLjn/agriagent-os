## ADDED Requirements

### Requirement: 用户级 Token 统计
系统 SHALL 在 TokenDailyStats 中记录每条 token 用量的 user_id，并保留 farm_id、model、call_type 维度，支持按用户、农场或全量查询 token 统计。

#### Scenario: 新 token 用量记录包含 user_id
- **WHEN** LLM 调用完成并记录 token 用量
- **THEN** TokenDailyStats 行中 user_id 字段 SHALL 为发起请求的用户 ID
- **AND** farm_id SHALL 为本次请求的可信农场 ID
- **AND** call_type SHALL 反映本次调用来源（chat、stream_chat、daily_advice、report 等）

#### Scenario: 同一用户不同农场分别统计
- **WHEN** 同一用户在两个 farm_id 下分别产生同一日期、模型和调用类型的 token 用量
- **THEN** 系统 SHALL 生成或更新两条不同的 TokenDailyStats 聚合行
- **AND** 用户级查询 SHALL 聚合这两条记录

#### Scenario: 按用户查询用量汇总
- **WHEN** 管理员请求某用户的 token 统计
- **THEN** 系统 SHALL 返回该用户在指定时间范围内的 prompt_tokens、completion_tokens、total_tokens 总和

### Requirement: Provider Usage 真实账本
系统 SHALL 仅使用 LLM provider 返回的 usage 或 LangChain usage_metadata 累计 TokenDailyStats；本地 token 估算 SHALL 只用于调用前预算和 trace。

#### Scenario: 使用 provider usage 累计
- **WHEN** LLM 响应包含 prompt_tokens、completion_tokens、total_tokens
- **THEN** 系统 SHALL 将这些真实 token 数累计到 TokenDailyStats
- **AND** usage_source SHALL 记录为 provider 或 usage_metadata

#### Scenario: 本地估算不进入配额账本
- **WHEN** FinalPromptBudget 生成 prompt token 估算
- **THEN** 系统 SHALL 将估算写入 trace
- **AND** SHALL NOT 将估算值累计到 TokenDailyStats

#### Scenario: 缺失 usage 不扣量
- **WHEN** LLM 响应缺少 usage 和 usage_metadata
- **THEN** 系统 SHALL 记录 usage_source 为 missing 的 trace warning
- **AND** SHALL NOT 写入 TokenDailyStats

#### Scenario: 流式调用要求 usage
- **WHEN** 系统发起流式 LLM 调用
- **THEN** 系统 SHALL 尽可能启用 provider 的 streaming usage 返回能力
- **AND** 若最终未获得真实 usage，SHALL 标记 missing_stream_usage 且不累计 TokenDailyStats

#### Scenario: 单一统计写入口
- **WHEN** 系统记录 LLM token 用量
- **THEN** 系统 SHALL 只通过 TraceCollector.record(node_type="llm_call") 累计 TokenDailyStats
- **AND** API 层、Agent 层和预算估算层 SHALL NOT 直接累计 TokenDailyStats

### Requirement: 月/周双周期配额
系统 SHALL 为每个用户同时支持月限额和周限额两种配额周期。

#### Scenario: 月限额检查
- **WHEN** 用户发起 LLM 请求
- **THEN** 系统 SHALL 计算当前自然月（1日 至 月末）的累计 token 用量，与月限额比较

#### Scenario: 周限额检查
- **WHEN** 用户发起 LLM 请求
- **THEN** 系统 SHALL 计算当前自然周（周一 至 周日）的累计 token 用量，与周限额比较

#### Scenario: 双周期取较严
- **WHEN** 月限额和周限额中任一超限
- **THEN** 系统 SHALL 拒绝请求，返回消息指明超限周期（"本月"/"本周"）

### Requirement: 全局默认配额
系统 SHALL 提供全局默认的月限额和周限额配置，适用于所有未单独设置配额的用户。

#### Scenario: 用户无自定义限额时使用默认值
- **WHEN** 用户的 token_monthly_limit 为 NULL
- **THEN** 系统 SHALL 使用全局配置 token_quota.monthly_limit 作为该用户的月限额

#### Scenario: 用户有自定义限额时优先使用
- **WHEN** 用户的 token_monthly_limit 为具体数值
- **THEN** 系统 SHALL 使用该数值作为月限额，忽略全局默认值

### Requirement: 超限拒绝
系统 SHALL 在用户超过配额时拒绝 LLM 调用，返回周期感知的提示消息。

#### Scenario: 月限额超限拒绝
- **WHEN** 用户本月累计 token 用量 >= 月限额
- **THEN** Agent SHALL 返回"本月用量已达上限，配额将在下月重置"消息，不调用 LLM

#### Scenario: 周限额超限拒绝
- **WHEN** 用户本周累计 token 用量 >= 周限额（月限额未超）
- **THEN** Agent SHALL 返回"本周用量已达上限，配额将在下周一重置"消息，不调用 LLM

#### Scenario: 配额正常允许调用
- **WHEN** 用户月/周用量均未超限
- **THEN** 系统 SHALL 正常执行 LLM 调用

#### Scenario: warn 模式允许调用
- **WHEN** 用户超过月限额或周限额且 token_quota.over_quota_action 为 "warn"
- **THEN** 系统 SHALL 记录超限日志并继续执行 LLM 调用

#### Scenario: 缺少用户身份拒绝
- **WHEN** LLM 请求没有可信 user_id
- **THEN** 系统 SHALL 拒绝调用 LLM
- **AND** 返回缺少可信用户上下文的提示消息

### Requirement: 管理员查询用户配额
系统 SHALL 提供管理员 API 查询单个用户的配额状态。

#### Scenario: 查询单用户配额
- **WHEN** 管理员请求 GET /admin/users/{user_id}/quota
- **THEN** 返回该用户的月限额、月已用、月剩余、周限额、周已用、周剩余、周期起止日期、状态（normal/warning/exceeded）

#### Scenario: 查询全量用户配额概览
- **WHEN** 管理员请求 GET /admin/users/quota-overview
- **THEN** 返回分页列表，每项包含用户昵称、手机号、月限额、月已用、月百分比、周限额、周已用、周百分比、状态

### Requirement: 管理员修改用户配额
系统 SHALL 允许管理员修改单个用户的月/周 token 限额。

#### Scenario: 设置用户月限额
- **WHEN** 管理员请求 PUT /admin/users/{user_id}/quota，body 包含 {"token_monthly_limit": 5000000}
- **THEN** 该用户的 token_monthly_limit 更新为指定值，后续配额检查使用新值

#### Scenario: 恢复全局默认
- **WHEN** 管理员请求 PUT /admin/users/{user_id}/quota，body 包含 {"token_monthly_limit": null}
- **THEN** 该用户的 token_monthly_limit 清空，后续回退到全局默认值
