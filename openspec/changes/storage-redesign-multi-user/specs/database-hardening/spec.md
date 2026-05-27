## ADDED Requirements

### Requirement: SQLite WAL 模式
系统启动时 SHALL 自动配置 SQLite WAL 模式，确保读写不互阻塞。

#### Scenario: 启动时自动配置
- **WHEN** FastAPI 应用启动，数据库连接建立
- **THEN** 自动执行 PRAGMA journal_mode=WAL, synchronous=NORMAL, foreign_keys=ON, busy_timeout=5000

#### Scenario: WAL 模式验证
- **WHEN** 查询 `PRAGMA journal_mode`
- **THEN** 返回 "wal"

### Requirement: 外键约束生效
所有外键关系 SHALL 在 SQLite 层面强制执行（PRAGMA foreign_keys=ON）。

#### Scenario: 删除农场级联清理
- **WHEN** 删除一条 Farm 记录
- **THEN** 关联的 crop_cycles、cost_records、conversations 等记录自动级联删除

### Requirement: 定时备份
系统 SHALL 提供备份脚本，每小时在线热备 SQLite 数据库，保留 7 天滚动备份。

#### Scenario: 正常备份
- **WHEN** cron 每小时触发备份脚本
- **THEN** 使用 `sqlite3 .backup` 命令生成备份文件，命名含时间戳，自动清理 7 天前的备份

### Requirement: users 和 farms 表使用 UUID 主键
`users` 和 `farms` 表的主键 SHALL 使用 UUID v4（String(36)），防止 ID 枚举攻击。

#### Scenario: 注册时生成 UUID
- **WHEN** 用户注册成功
- **THEN** users.id 和 farms.id 为 UUID v4 格式（如 "a1b2c3d4-e5f6-7890-abcd-ef1234567890"）

#### Scenario: API 使用 UUID
- **WHEN** 前端请求 `GET /farms/<uuid>`
- **THEN** 使用 UUID 查询，无法通过递增 ID 猜测其他农场
