## MODIFIED Requirements

### Requirement: Agent 调用前自动注入农场现状摘要
后端 SHALL 在 Agent 调用前通过 Context 工程模块选择农场相关上下文。农场上下文 SHALL 表示为 ContextBlock，并由 ContextPolicy 决定注入热上下文、摘要上下文或改由 tool 按需获取。每日建议可注入农场摘要；普通聊天 SHALL 根据 intent 和 token 预算决定是否注入完整摘要。摘要中的天气 SHALL 使用当前 farm 的经营地区作为主位置来源。

#### Scenario: 有活跃茬口时的摘要
- **WHEN** farm_id=1 存在 2 个活跃茬口（春季西瓜-伸蔓期、秋季豆角-播种期），近 3 天有 2 条农事记录，1 笔未结清欠账，farm location 为"睢宁县"
- **THEN** 农场摘要候选 block 包含茬口名称和阶段、近期农事、欠账信息、基于"睢宁县"的天气（未来 3 天），总长度受 token 预算控制

#### Scenario: 无活跃茬口时的摘要
- **WHEN** farm_id=1 没有任何活跃茬口
- **THEN** 热上下文中的活跃茬口显示为空或「当前无种植计划」，其余上下文正常组装

#### Scenario: 摘要查询性能
- **WHEN** 调用农场上下文 selector
- **THEN** 常规缓存命中路径不查库，缓存未命中路径在可接受时间内完成并记录耗时 trace

#### Scenario: 普通闲聊不注入完整农场摘要
- **WHEN** 用户发送与农场业务无关的闲聊请求
- **THEN** 系统只注入热上下文，不默认注入完整农场现状摘要

### Requirement: 摘要缓存
后端 SHALL 以 farm_id 和上下文类型为键缓存可复用的农场上下文，默认 TTL 为 5 分钟。缓存 SHALL 在相关写操作后主动失效。相关写操作 SHALL 包含当前 farm 的经营地区变更。

#### Scenario: 缓存命中
- **WHEN** 5 分钟内对同一 farm_id 再次请求相同上下文类型
- **THEN** 直接返回缓存，不重复查库

#### Scenario: 缓存失效
- **WHEN** 缓存超过 5 分钟
- **THEN** 重新查库组装摘要并更新缓存

#### Scenario: 写操作主动失效
- **WHEN** 该 farm 的周期、日志、账务、债务、用户设置或经营地区发生变更
- **THEN** 系统主动清理相关农场上下文缓存

#### Scenario: 经营地区变更后重新生成天气摘要
- **WHEN** farm_id=1 的经营地区从"睢宁县"修改为"邳州市"
- **THEN** 下一次构建农场摘要时 SHALL 重新获取"邳州市"对应天气，不返回旧地区缓存
