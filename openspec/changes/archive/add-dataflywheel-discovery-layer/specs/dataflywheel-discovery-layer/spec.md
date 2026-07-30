## ADDED Requirements

### Requirement: 规则引擎实时打标

系统 SHALL 在 agent turn 写入时同步评估业务规则，并将命中规则的 ID 与权重用于计算 `rule_score`。规则 SHALL 通过 `rules.yaml` 配置，支持文件 watcher 热更新。

#### Scenario: 工具错误被忽略命中规则

- **WHEN** agent turn 包含至少一个 `status=error` 的 tool_call 且 agent 在后续回复中未纠正
- **THEN** rule engine 命中 `tool_error_ignored` 规则（weight=0.95, severity=P0）
- **AND** 该 turn 的 `rule_score` 至少为 0.95

#### Scenario: 工资查询缺关键字段

- **WHEN** agent turn 意图为 `wage_query` 或 `labor_query`且回复不包含「基本工资」或「实发工资」
- **THEN** rule engine 命中 `missing_wage` 规则（weight=0.9, severity=P0）

#### Scenario: 规则配置热更新

- **WHEN** 管理员修改 `rules.yaml` 并保存
- **THEN** rule engine 在文件 watcher 触发后 ≤ 5 秒内重载规则
- **AND** 重载失败时保持旧规则不失效并打印结构化日志

#### Scenario: 规则定义格式

- **WHEN** rules.yaml 中定义规则
- **THEN** 每条规则包含 `id`、`weight`（0-1）、`severity`（P0/P1）、`description`、`when`（条件 DSL）

#### Scenario: 启动加载并校验

- **WHEN** rule engine 启动
- **THEN** 加载 `rules.yaml` 并校验格式与字段完整性
- **AND** 校验失败时拒绝启动并打印错误

### Requirement: LLM Judge 批处理评估

系统 SHALL 每天通过 cron 触发 LLM Judge Worker，对前 24 小时未标注且 `judge_bad_prob IS NULL` 的 agent turn 调用 Claude Haiku，输出 `bad_prob`、`issue_type`、`suggested_label`。

#### Scenario: 批处理 Judge 正常执行

- **WHEN** cron 在每天 02:00 触发
- **THEN** worker 找出前 24 小时 `judge_bad_prob IS NULL` 且 `label_source IS NULL` 的 turn
- **AND** 用 Claude Haiku 评估，并发上限 32
- **AND** 将结果写入 `judge_bad_prob`、`judge_issue_type`、`judge_suggested_label` 字段

#### Scenario: 成本上限触发降级

- **WHEN** 当月 Judge API 累计成本 > $200
- **THEN** worker 自动降级为 rule-only 模式（跳过 Judge 调用）
- **AND** 发出告警通知管理员
- **AND** 在 `risk_score` 计算中只使用 `rule_score`

#### Scenario: 跳过已有人工标注

- **WHEN** turn 的 `label_source = 'human'`
- **THEN** Judge worker 跳过该 turn 不重新评估

### Requirement: 风险评分计算

系统 SHALL 按公式 `risk_score = max(rule_score, judge_bad_prob)` 计算每个 agent turn 的综合风险分数，并记录主导信号 `risk_dominant_signal`。`risk_score` SHALL 在 rule 命中时同步更新，在 Judge 完成时异步更新。

#### Scenario: 规则主导

- **WHEN** turn 命中 `tool_error_ignored` 规则（`rule_score=0.95`）且 `judge_bad_prob=0.7`
- **THEN** `risk_score = 0.95`
- **AND** `risk_dominant_signal = 'rule'`

#### Scenario: Judge 主导

- **WHEN** turn 未命中任何规则（`rule_score=0`）且 `judge_bad_prob=0.82`
- **THEN** `risk_score = 0.82`
- **AND** `risk_dominant_signal = 'judge'`

#### Scenario: 两者都为空时风险为零

- **WHEN** turn 未命中规则且尚未被 Judge 评估
- **THEN** `risk_score = 0.0`
- **AND** `risk_dominant_signal = NULL`

### Requirement: 标注工作台默认按风险排序

DataFlywheel 标注工作台的会话列表 SHALL 默认按 `risk_score DESC, created_at DESC` 排序，并提供「隐藏低风险（`risk_score < 0.3`）」开关。

#### Scenario: 默认按风险倒序

- **WHEN** 标注员打开 DataFlywheel 工作台首页
- **THEN** 会话列表按 `risk_score DESC` 排序
- **AND** 同分时按 `created_at DESC` 排序

#### Scenario: 隐藏低风险开关

- **WHEN** 标注员勾选「隐藏低风险（score < 0.3）」
- **THEN** 列表过滤掉 `risk_score < 0.3` 的会话

#### Scenario: 卡片显示风险分数

- **WHEN** 列表渲染会话卡片
- **THEN** 卡片显示 `Risk: 0.xx` 数值
- **AND** 显示主导信号图标（🔧 rule 或 🤖 judge）

#### Scenario: 时间排序回退

- **WHEN** URL 参数 `?sort=time`
- **THEN** 列表回退到 `created_at DESC` 排序（用于灰度切流与 fallback）

### Requirement: P0 风险顶置告警

系统 SHALL 对 P0 级风险（幻觉执行 / 工具错误被忽略 / 业务关键字段缺失 / 安全问题）在工作台提供独立筛选入口并视觉强调。

#### Scenario: P0 规则命中视觉强调

- **WHEN** turn 命中 `severity=P0` 的规则
- **THEN** 卡片用红色边框或徽标标识
- **AND** 卡片显示 P0 标签

#### Scenario: P0 规则独立筛选

- **WHEN** 标注员切换到「P0 严重」筛选
- **THEN** 列表只显示命中 P0 规则的 turn

### Requirement: Judge 不写入最终标注真值

LLM Judge 的输出 SHALL 仅作为 `risk_score` 输入信号，不直接写入 turn 的最终标注字段（`label`、`label_source`）。Judge 仅写入 `judge_*` 前缀字段。

#### Scenario: Judge 不覆盖人工标注

- **WHEN** turn 已有人工标注（`label_source='human'`）
- **THEN** Judge worker 跳过该 turn 不重新评估
- **AND** 已有的人工 `label` 和 `label_source='human'` 不被覆盖

#### Scenario: Judge 来源不污染标注来源

- **WHEN** Judge 评估完成
- **THEN** turn 的 `judge_bad_prob`、`judge_issue_type`、`judge_suggested_label` 字段写入
- **AND** `label_source` 保持空（未标注）或 `human`（人工标注），绝不写入 `llm_judge`
