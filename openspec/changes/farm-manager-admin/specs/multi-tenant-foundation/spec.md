## ADDED Requirements

### Requirement: Farm 实体与数据库表
系统 SHALL 新增 Farm 模型和 farms 数据库表，包含 id、name、owner_name、location、created_at 字段。Farm 为顶级实体，所有业务数据通过 farm_id 关联到 Farm。

#### Scenario: Farm 表自动创建
- **WHEN** 后端启动时执行数据库迁移
- **THEN** 自动创建 farms 表，并插入一条默认种子数据（id=1, name="默认农场"）

#### Scenario: Farm 模型可被其他模型引用
- **WHEN** 其他模型定义 farm_id 外键
- **THEN** 外键正确指向 farms.id，支持级联查询

### Requirement: 业务数据表添加 farm_id 外键
系统 SHALL 在以下 6 张表中添加 farm_id 整型列和外键约束：crop_templates、crop_cycles、farm_logs、cost_records、advice_records、report_records。外键 SHALL 指向 farms.id。growth_stages 和 cycle_stages 不添加 farm_id（通过父表间接隔离）。

#### Scenario: crop_templates 按 farm_id 隔离
- **WHEN** 查询作物模板
- **THEN** 仅返回当前 farm_id 下的模板记录，不泄漏其他农场数据

#### Scenario: 新建记录自动关联 farm_id
- **WHEN** 通过 API 创建任意业务记录
- **THEN** 系统自动填充当前 farm 的 id，无需前端传递

### Requirement: get_current_farm 依赖注入
系统 SHALL 提供 get_current_farm FastAPI 依赖注入函数，返回当前请求关联的 Farm 对象。当前阶段 SHALL 硬编码返回 farm_id=1 的农场实例。函数签名和注入位置 SHALL 预留 JWT 解析扩展点。

#### Scenario: 当前阶段返回默认农场
- **WHEN** 任意 API 请求到达
- **THEN** get_current_farm 返回 id=1 的 Farm 实例

#### Scenario: 默认农场不存在时
- **WHEN** 数据库中无 id=1 的农场
- **THEN** 返回 HTTP 404 错误，提示"No default farm found"

### Requirement: API 路由注入 farm 上下文
系统 SHALL 修改所有 6 个路由模块（crop、cycle、log、cost、agent、weather），使每个端点的处理函数接收 farm: Farm = Depends(get_current_farm) 参数，并将 farm.id 传递给 service 层。service 层所有查询 SHALL 追加 farm_id 过滤条件。

#### Scenario: 查询自动按 farm 过滤
- **WHEN** 调用 GET /crops/templates
- **THEN** service 层查询 WHERE farm_id = current_farm.id，仅返回当前农场数据

#### Scenario: 创建记录自动绑定 farm
- **WHEN** 调用 POST /cycles 创建茬口
- **THEN** 新记录的 farm_id 自动设为当前 farm.id

### Requirement: 数据库种子数据脚本
系统 SHALL 提供种子数据脚本（seed.py 或内嵌于 lifespan），在首次启动时自动创建默认农场（id=1）及关联的基础数据。

#### Scenario: 首次启动自动播种
- **WHEN** 后端首次启动且 farms 表为空
- **THEN** 自动创建 id=1 的默认农场记录

#### Scenario: 已有数据不重复播种
- **WHEN** farms 表已有记录
- **THEN** 跳过播种，不创建重复数据
