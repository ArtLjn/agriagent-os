## ADDED Requirements

### Requirement: 复合索引支持核心查询
MySQL schema SHALL 为账务、种植周期、农事日志、会话消息、Agent 记录和 trace 查询配置复合索引。

#### Scenario: 账务按农场和日期查询
- **WHEN** 系统按 `farm_id`、`record_date` 和 `deleted_at` 查询账务记录
- **THEN** MySQL 必须存在可覆盖该查询前缀的复合索引

#### Scenario: Trace 按请求轮次查询
- **WHEN** 管理端按 `request_id` 查看 trace 时间线
- **THEN** MySQL 必须存在以 `request_id`、`round_index` 和 `id` 组成的复合索引

### Requirement: 结构化字段使用 JSON 类型
MySQL schema SHALL 将明确存储结构化 JSON 的字段定义为 `JSON` 类型，而不是普通 `text`。

#### Scenario: Trace token usage 存储
- **WHEN** 系统写入 trace token usage
- **THEN** 数据库必须校验该字段为合法 JSON

#### Scenario: 仿真结果 JSON 存储
- **WHEN** 系统写入仿真错误、数据库差异或 pending action 数据
- **THEN** 数据库必须以 JSON 类型保存结构化内容

### Requirement: 时间和日期字段使用准确类型
MySQL schema SHALL 使用 `date`、`datetime` 或 `datetime(6)` 存储日期时间语义，不得用字符串列保存可计算时间。

#### Scenario: Token 统计日期
- **WHEN** 系统写入每日 token 统计
- **THEN** `token_daily_stats.date` 必须使用 `date` 类型

#### Scenario: Trace 节点时间
- **WHEN** 系统写入 trace 节点开始和结束时间
- **THEN** `trace_records.start_time` 和 `trace_records.end_time` 必须使用 datetime 类型

### Requirement: 布尔语义字段使用布尔兼容类型
MySQL schema SHALL 使用 `tinyint(1)` 或 SQLAlchemy Boolean 映射保存布尔语义字段。

#### Scenario: 当前阶段标识
- **WHEN** 系统保存生长阶段是否为当前阶段
- **THEN** `cycle_stages.is_current` 必须使用布尔兼容类型而不是普通 int 语义
