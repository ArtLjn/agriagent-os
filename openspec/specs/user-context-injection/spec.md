## Purpose

定义 user-context-injection 能力的行为要求。
## Requirements
### Requirement: 用户上下文结构化注入
系统 SHALL 将用户关键信息以结构化上下文注入 Agent prompt。注入内容 SHALL 来源于认证绑定的当前 farm、用户资料和用户设置，包含用户所在城市/位置、坐标、称呼、当前日期和季节。系统 MUST 在字段缺失时保留缺失状态，不得由 LLM 编造。

#### Scenario: location 有值时注入
- **WHEN** 当前用户设置默认城市为"苏州"
- **THEN** system prompt 或 ContextBundle 热上下文包含 location="苏州"、用户称呼和当前季节

#### Scenario: location 为空时不注入 location 节点
- **WHEN** 用户默认城市和 Farm.location 均为空
- **THEN** system prompt 或 ContextBundle 热上下文不包含伪造 location，LLM 在位置必要时追问用户所在城市

#### Scenario: 季节自动计算
- **WHEN** 当前日期为 7 月 15 日
- **THEN** 热上下文中的 season 值为"夏季"（3-5月春、6-8月夏、9-11月秋、12-2月冬）

#### Scenario: 用户设置优先于 farm 位置
- **WHEN** 用户默认城市为"苏州"且 Farm.location 为"南京"
- **THEN** 注入的位置优先使用用户默认城市"苏州"，并可保留 Farm.location 作为低优先级 farm metadata

#### Scenario: 用户设置变更后缓存失效
- **WHEN** 用户修改默认城市、坐标或称呼
- **THEN** 下一次 Agent 调用不得继续使用修改前的用户上下文缓存

### Requirement: 城市信息传递给 skill
当 LLM 通过 function calling 调用需要 location 参数的 skill 时，LLM SHALL 使用结构化用户上下文中的 location 值作为参数；当 location 缺失但 tool 必须依赖位置时，LLM SHALL 追问用户或返回缺少位置的可理解提示。

#### Scenario: 天气查询使用注入的城市
- **WHEN** 用户问"明天天气怎么样"，结构化用户上下文中 location 为"苏州"
- **THEN** LLM 调用 `weather` 时传入 `location: "苏州"`

#### Scenario: location 为空时 LLM 追问
- **WHEN** 用户问"明天天气怎么样"，结构化用户上下文中无 location
- **THEN** LLM 回复询问用户所在城市，不调用天气 skill 或调用会返回缺失位置错误的安全路径

#### Scenario: 坐标优先用于天气 provider
- **WHEN** 结构化用户上下文同时包含 location 和坐标
- **THEN** 天气相关 tool 可以优先使用坐标查询，并保留 location 作为展示城市

