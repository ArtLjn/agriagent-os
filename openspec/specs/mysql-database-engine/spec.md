## Purpose

定义 mysql-database-engine 能力的行为要求。
## Requirements
### Requirement: MySQL 连接引擎
系统 SHALL 使用 MySQL 8.x 作为唯一应用数据库后端，通过 `config.yaml` 的 `database.url` 字段配置，必须使用 `mysql+pymysql://` 连接串格式。

#### Scenario: MySQL 连接配置
- **WHEN** `config.yaml` 中 `database.url` 设置为 `mysql+pymysql://user:pass@host:3306/dbname?charset=utf8mb4`
- **THEN** 系统启动时使用 MySQL 引擎和连接池配置

#### Scenario: 拒绝 SQLite 应用配置
- **WHEN** `config.yaml` 中 `database.url` 以 `sqlite:///` 开头
- **THEN** 系统启动时报错，提示必须使用 `mysql+pymysql://` 连接串

#### Scenario: 测试夹具可使用 SQLite
- **WHEN** 测试代码显式创建独立 SQLite engine
- **THEN** 测试可继续使用 SQLite fixture，且不得依赖生产 `app.core.database.engine`

### Requirement: MySQL 连接池管理
当使用 MySQL 时，系统 SHALL 配置 SQLAlchemy 连接池参数以优化资源使用。

#### Scenario: 连接池参数
- **WHEN** 数据库引擎创建
- **THEN** 配置 `pool_size=10`、`max_overflow=20`、`pool_recycle=3600`、`pool_pre_ping=True`

#### Scenario: 连接回收
- **WHEN** MySQL 连接空闲超过 3600 秒
- **THEN** 连接池自动回收并重建连接

### Requirement: Alembic 迁移框架
系统 SHALL 使用 Alembic 管理数据库 schema 演进，替代 `Base.metadata.create_all()`。

#### Scenario: 初始化迁移
- **WHEN** 执行 `alembic upgrade head`
- **THEN** 自动创建所有 20 张表及其索引、外键约束

#### Scenario: 应用启动自动迁移
- **WHEN** FastAPI 应用启动
- **THEN** 自动执行 `alembic upgrade head`，确保 schema 为最新

#### Scenario: 迁移脚本生成
- **WHEN** 开发者修改模型后执行 `alembic revision --autogenerate -m "描述"`
- **THEN** 自动检测模型变更并生成迁移脚本

### Requirement: String 列显式长度
所有 `String` 类型的列 SHALL 指定显式长度，确保 MySQL 兼容。

#### Scenario: 模型审查
- **WHEN** 模型中存在 `Column(String)` 无长度参数
- **THEN** 启动时或 CI 检查中报错提示

#### Scenario: 合理长度设定
- **WHEN** 指定 String 长度
- **THEN** 按业务语义设置（如 phone=20, nickname=50, content=2000, api_key=256）

### Requirement: MySQL 字符集
MySQL 数据库和连接 SHALL 使用 `utf8mb4` 字符集，支持完整 Unicode（含 emoji）。

#### Scenario: 数据库字符集
- **WHEN** 创建 MySQL 数据库
- **THEN** 字符集为 `utf8mb4`，排序规则为 `utf8mb4_unicode_ci`

#### Scenario: 连接字符集
- **WHEN** 建立 MySQL 连接
- **THEN** 连接串包含 `charset=utf8mb4` 参数

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

