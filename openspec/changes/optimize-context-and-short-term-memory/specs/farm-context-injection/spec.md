## MODIFIED Requirements

### Requirement: Agent 调用前自动注入农场现状摘要
后端 SHALL 在 Agent 调用前通过 Context 工程模块选择农场相关上下文。农场上下文 SHALL 表示为 ContextBlock，并由 ContextPolicy 决定注入热上下文、摘要上下文或改由 tool 按需获取。每日建议可注入农场摘要；普通聊天 SHALL 根据 intent 和 token 预算决定是否注入完整摘要。

#### Scenario: 有活跃茬口时的摘要
- **WHEN** farm_id=1 存在 2 个活跃茬口（春季西瓜-伸蔓期、秋季豆角-播种期），近 3 天有 2 条农事记录，1 笔未结清欠账
- **THEN** 农场摘要候选 block 包含茬口名称和阶段、近期农事、欠账信息、天气（未来 3 天），总长度受 token 预算控制

#### Scenario: 无活跃茬口时的摘要
- **WHEN** farm_id=1 没有任何活跃茬口
- **THEN** 热上下文中的活跃茬口显示为空或「当前无种植计划」，其余上下文正常组装

#### Scenario: 摘要查询性能
- **WHEN** 调用农场上下文 selector
- **THEN** 常规缓存命中路径不查库，缓存未命中路径在可接受时间内完成并记录耗时 trace

#### Scenario: 普通闲聊不注入完整农场摘要
- **WHEN** 用户发送与农场业务无关的闲聊请求
- **THEN** 系统只注入热上下文，不默认注入完整农场现状摘要

### Requirement: 摘要内容裁剪规则
后端 SHALL 对摘要中各数据类型实施硬上限裁剪，防止摘要膨胀。裁剪结果 SHALL 作为 ContextBlock token 估算的一部分，并受统一 TokenBudget 管理。

#### Scenario: 多茬口裁剪
- **WHEN** farm_id=1 有 5 个活跃茬口
- **THEN** 摘要候选只包含最近或最相关的 3 个茬口

#### Scenario: 多农事记录裁剪
- **WHEN** 近 3 天有 10 条农事记录
- **THEN** 摘要候选只包含最近的 3 条

#### Scenario: 多债务裁剪
- **WHEN** 有 8 笔未结清欠账
- **THEN** 摘要候选只包含最近到期或最相关的 3 笔

#### Scenario: 预算不足时摘要被压缩
- **WHEN** 农场摘要候选超过剩余 token 预算
- **THEN** 系统压缩摘要或丢弃低优先级部分，并在 trace 中记录原因

### Requirement: 摘要缓存
后端 SHALL 以 farm_id 和上下文类型为键缓存可复用的农场上下文，默认 TTL 为 5 分钟。缓存 SHALL 在相关写操作后主动失效。

#### Scenario: 缓存命中
- **WHEN** 5 分钟内对同一 farm_id 再次请求相同上下文类型
- **THEN** 直接返回缓存，不重复查库

#### Scenario: 缓存失效
- **WHEN** 缓存超过 5 分钟
- **THEN** 重新查库组装摘要并更新缓存

#### Scenario: 写操作主动失效
- **WHEN** 该 farm 的周期、日志、账务、债务或用户设置发生变更
- **THEN** 系统主动清理相关农场上下文缓存

### Requirement: farm_context_service 作为兼容上下文入口
兼容期内 `services/farm_context_service.py` SHALL 保留 `build_summary()` 入口供旧链路调用；新 Agent Runtime SHALL 优先通过 `app/context` 的 ContextBuilder、selector 和 ContextPolicy 构建上下文。上层不得新增直接查库拼接 prompt 的逻辑。

#### Scenario: 旧接口继续可用
- **WHEN** 旧代码路径调用 `farm_context_service.build_summary(farm_id)`
- **THEN** 系统返回兼容的农场摘要文本

#### Scenario: 新 runtime 不直接拼接农场摘要
- **WHEN** Agent Runtime 需要农场上下文
- **THEN** 调用 ContextBuilder 或 Memory/Context Service，不直接 import models 拼接 prompt
