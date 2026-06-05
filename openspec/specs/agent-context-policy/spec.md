# agent-context-policy Specification

## Purpose
TBD - created by archiving change optimize-context-and-short-term-memory. Update Purpose after archive.
## Requirements
### Requirement: Agent 上下文分层策略
系统 SHALL 将 Agent 上下文分为热上下文、工作记忆和按需检索上下文三层，并在每次 Agent 调用前基于请求、intent 和 selected tools 构建最终上下文。

#### Scenario: 构建三层上下文
- **WHEN** Agent 处理一次聊天请求
- **THEN** 系统生成包含热上下文、工作记忆和按需检索上下文决策结果的 ContextBundle

#### Scenario: 闲聊请求使用最小上下文
- **WHEN** intent 为闲聊且未选择业务 tool
- **THEN** 系统只注入热上下文和必要的短时记忆，不默认注入账务、天气、日志或长期检索结果

### Requirement: 热上下文每次注入
系统 SHALL 在每次 Agent 调用中注入高可信、低 token 的热上下文。热上下文 SHALL 至少包含当前日期、季节、当前 farm 标识、用户称呼、默认位置、坐标和活跃茬口摘要；缺失字段 SHALL 使用空值或默认值，不得由 LLM 推断。

#### Scenario: 用户设置完整
- **WHEN** 当前 farm 绑定用户存在昵称、默认城市和坐标
- **THEN** 热上下文包含昵称、默认城市、坐标、当前日期、季节和活跃茬口摘要

#### Scenario: 用户位置缺失
- **WHEN** 用户默认城市和 farm 位置均为空
- **THEN** 热上下文不包含伪造位置，天气等依赖位置的问题由 Agent 追问用户或通过工具返回缺失位置错误

### Requirement: 意图驱动 selector 选择
系统 SHALL 通过 ContextPolicy 或等价策略，根据 intent、selected tools、session_id 和请求 metadata 决定启用哪些 selector。

#### Scenario: 账务查询启用账务 selector
- **WHEN** intent 为账务查询或 selected tools 包含账务相关 tool
- **THEN** 系统启用账务摘要 selector，并将其输出纳入 token 预算

#### Scenario: 天气查询启用天气相关上下文
- **WHEN** intent 为天气查询或 selected tools 包含天气 tool
- **THEN** 系统提供位置、坐标和必要天气摘要；天气详情 SHALL 由天气 tool 按需获取

#### Scenario: 作物问题启用周期 selector
- **WHEN** intent 为作物、周期或农事建议
- **THEN** 系统启用当前周期和农场状态 selector

### Requirement: 最终 token 预算控制
系统 MUST 在调用 LLM 前对最终上下文执行 token 预算控制。预算决策 SHALL 按 required、priority、可压缩性和 min_tokens 决定保留、压缩或丢弃 block。

#### Scenario: 上下文低于预算
- **WHEN** 候选上下文 token 估算低于预算
- **THEN** 系统保留所有候选 block，并记录 token_estimate

#### Scenario: 上下文超过预算
- **WHEN** 候选上下文超过预算
- **THEN** 系统保留 required 和高优先级 block，压缩可压缩 block，丢弃低优先级 block，并记录 dropped reason

#### Scenario: required block 超预算
- **WHEN** required block 本身导致预算超限
- **THEN** 系统仍保留 required block，并在 trace 中标记预算超限风险

### Requirement: 上下文可观测性
系统 SHALL 为每次上下文构建记录 trace，内容包括启用的 selector、候选 block、保留 block、压缩 block、丢弃 block、token 估算、耗时和 selector 错误。

#### Scenario: selector 抛出异常
- **WHEN** 某个非 required selector 构建失败
- **THEN** 系统记录 selector error，继续构建其他上下文，并不得中断 Agent 主流程

#### Scenario: 调试上下文缺失
- **WHEN** Agent 回复缺少某项业务背景
- **THEN** 开发者可以通过 trace 判断该 block 是否未被 selector 选中、被压缩或被预算丢弃

### Requirement: 缓存失效策略
系统 SHALL 在影响上下文准确性的写操作后清理相关 context cache 和 prompt cache。

#### Scenario: 用户设置变更
- **WHEN** 用户修改默认城市、坐标或昵称
- **THEN** 系统清理该用户当前 farm 相关的 farm context cache 和 prompt cache

#### Scenario: 活跃茬口变更
- **WHEN** 系统创建、更新、删除种植周期或推进阶段
- **THEN** 系统清理该 farm 的 context cache 和 prompt cache

#### Scenario: 账务或日志变更
- **WHEN** 系统创建、更新或删除账务记录、债务记录或农事日志
- **THEN** 系统清理该 farm 下与账务、日志和农场摘要相关的缓存

