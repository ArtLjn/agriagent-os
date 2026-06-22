## ADDED Requirements

### Requirement: 长期记忆 block 注入
ContextBuilder SHALL 通过 MemorySelector 查询当前农场的长期记忆（详见 `long-term-memory-policy` capability），作为独立 ContextBlock（key=`memory_long_term`）注入。该 block SHALL 与会话摘要、最近窗口、pending_action 互相独立，便于 TokenBudget 单独决策。

block 元数据 SHALL 满足：
- key=`memory_long_term`
- source=`memory.long_term`
- priority 介于 conversation_summary（50）与 retrieval 之间，默认 45
- compressible=True，min_tokens ≥ 64
- metadata 包含 `layer=working`、`cache_scope=farm`

#### Scenario: 存在长期记忆时注入
- **WHEN** 当前农场有 status=confirmed/candidate 且 importance ≥ 0.3 的记忆
- **THEN** ContextBundle 包含 key=`memory_long_term` 的 block，内容为记忆列表（type + content）

#### Scenario: 无长期记忆时不注入
- **WHEN** 当前农场无符合条件记忆
- **THEN** ContextBundle 不包含 `memory_long_term` block

#### Scenario: 与其他工作记忆 block 独立
- **WHEN** ContextBuilder 同时构造出 pending_action、conversation_summary、memory_long_term、short_term_recent 多个 block
- **THEN** 每个 block 有独立 key、priority、compressible 标记；TokenBudget 按各自 priority 独立决策保留/压缩/丢弃
