## ADDED Requirements

### Requirement: 写操作 Tool 通过 Regex 模式确定性匹配
`tool_selector.py` SHALL 为每个写操作 Tool 维护一组编译好的 regex pattern。当用户消息匹配任一 pattern 时，该 Tool SHALL 被加入候选列表。写操作 Tool 包括：`create_cost_record`、`settle_debt`、`create_crop_cycle`、`log_farm_activity`、`update_crop_stage`。

#### Scenario: 记账 — 包含金额
- **WHEN** 用户消息为"卖了西瓜5000块"
- **THEN** `create_cost_record` 在候选列表中（匹配"卖了"和"\d+块"模式）

#### Scenario: 记账 — 显式触发词
- **WHEN** 用户消息为"记一笔，买了化肥"
- **THEN** `create_cost_record` 在候选列表中（匹配"记一笔"模式）

#### Scenario: 还账 — 变体表达
- **WHEN** 用户消息为"把欠老王的账结了"
- **THEN** `settle_debt` 在候选列表中（匹配"欠.*结"模式）

#### Scenario: 建茬口 — 含作物名
- **WHEN** 用户消息为"创建春茬种植西瓜"
- **THEN** `create_crop_cycle` 在候选列表中（匹配"创建.*茬口"和"种植西瓜"模式）

#### Scenario: 记农事 — 动作+了
- **WHEN** 用户消息为"今天浇了水"
- **THEN** `log_farm_activity` 在候选列表中（匹配"浇了"模式）

#### Scenario: 更新阶段 — 阶段名称
- **WHEN** 用户消息为"西瓜进苗期了"
- **THEN** `update_crop_stage` 在候选列表中（匹配"进.*期"模式）

#### Scenario: 歧义输入不误触发写操作
- **WHEN** 用户消息为"买化肥"（无金额、无触发词）
- **THEN** 无写操作 Tool 被匹配，进入 fallback

### Requirement: 查询操作 Tool 通过策划触发词表匹配
`tool_selector.py` SHALL 维护一个查询 Tool 触发词字典 `{tool_name: set[str]}`。当用户消息包含某 Tool 的任一触发词时，该 Tool SHALL 加入候选列表。查询 Tool 包括：`weather`、`get_cost_summary`、`get_cost_analytics`、`get_crop_cycle_info`、`get_recent_farm_logs`。

#### Scenario: 天气查询
- **WHEN** 用户消息为"今天天气"
- **THEN** `weather` 在候选列表中（触发词"天气"匹配）

#### Scenario: 余额查询
- **WHEN** 用户消息为"我的月额"
- **THEN** `get_cost_summary` 在候选列表中（触发词"月额"匹配）

#### Scenario: 多意图查询
- **WHEN** 用户消息为"看看天气和成本"
- **THEN** `weather` 和 `get_cost_summary` 都在候选列表中

### Requirement: 预筛函数合并两层结果并支持 fallback
`select_tools(user_message: str, all_tools: list, top_k: int = 3) -> list` SHALL 执行 Layer 1（regex）和 Layer 2（keyword），合并去重后返回候选 Tool。当两层均无命中时，SHALL 返回全量 Tool 列表作为 fallback。

#### Scenario: 只命中写操作
- **WHEN** 用户消息为"花了200买化肥"且 regex 命中 create_cost_record 但无查询 Tool 匹配
- **THEN** 返回 `["create_cost_record"]`

#### Scenario: 写操作 + 查询操作同时命中
- **WHEN** 用户消息为"看看天气和成本"且查询命中 weather + cost_summary
- **THEN** 返回两个 Tool 的合并列表

#### Scenario: 无命中 fallback
- **WHEN** 用户消息为"你好"且 regex 和 keyword 均无匹配
- **THEN** 返回全量 10 个 Tool

### Requirement: 预筛结果通过 trace 日志记录
`select_tools` 的调用结果 SHALL 以 INFO 级别记录日志，包含：用户消息摘要、候选 Tool 名称列表、全量 Tool 数量。

#### Scenario: 记录预筛日志
- **WHEN** `select_tools` 返回 2 个候选 Tool
- **THEN** 日志输出 `tool_pre_filter | input="今天天气" | candidates=["weather"] | total=10`
