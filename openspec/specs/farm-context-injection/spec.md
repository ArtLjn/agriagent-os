## ADDED Requirements

### Requirement: Agent 调用前自动注入农场现状摘要
后端 SHALL 在每次 Agent 调用（每日建议、聊天）前，通过 `farm_context_service.build_summary(farm_id)` 查询数据库组装农场现状摘要文本，注入到 prompt 模板的 `{{ farm_context_summary }}` 变量中。

#### Scenario: 有活跃茬口时的摘要
- **WHEN** farm_id=1 存在 2 个活跃茬口（春季西瓜-伸蔓期、秋季豆角-播种期），近 3 天有 2 条农事记录，1 笔未结清欠账
- **THEN** 生成的摘要包含：茬口名称和阶段、近期农事、欠账信息、天气（未来 3 天），总长度 ≤300 字

#### Scenario: 无活跃茬口时的摘要
- **WHEN** farm_id=1 没有任何活跃茬口
- **THEN** 摘要中茬口部分显示「当前无种植计划」，其余部分正常组装

#### Scenario: 摘要查询性能
- **WHEN** 调用 `build_summary(farm_id)`
- **THEN** 查库时间 <10ms，总组装时间 <50ms

### Requirement: 摘要内容裁剪规则
后端 SHALL 对摘要中各数据类型实施硬上限裁剪，防止摘要膨胀。

#### Scenario: 多茬口裁剪
- **WHEN** farm_id=1 有 5 个活跃茬口
- **THEN** 摘要只包含最近的 3 个茬口

#### Scenario: 多农事记录裁剪
- **WHEN** 近 3 天有 10 条农事记录
- **THEN** 摘要只包含最近的 3 条

#### Scenario: 多债务裁剪
- **WHEN** 有 8 笔未结清欠账
- **THEN** 摘要只包含最近到期的 3 笔

### Requirement: 摘要缓存
后端 SHALL 以 farm_id 为键将摘要缓存 5 分钟，减少重复查库。

#### Scenario: 缓存命中
- **WHEN** 5 分钟内对同一 farm_id 再次请求摘要
- **THEN** 直接返回缓存，不查库

#### Scenario: 缓存失效
- **WHEN** 缓存超过 5 分钟
- **THEN** 重新查库组装摘要并更新缓存

### Requirement: farm_context_service 作为唯一上下文组装入口
所有农场上下文组装逻辑 SHALL 收拢到 `services/farm_context_service.py`，agent_service 只调用 `build_summary()` 接口。上层（agent_service、graph.py、base.j2）不直接查库组装上下文。

#### Scenario: agent_service 不直接查库
- **WHEN** agent_service 需要上下文摘要
- **THEN** 调用 `farm_context_service.build_summary(farm_id)`，不直接 import models 或执行 SQL
