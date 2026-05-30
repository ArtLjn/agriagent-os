## ADDED Requirements

### Requirement: Provider 加权路由
系统 SHALL 根据 providers.json 中每个 provider 的 `weight` 字段进行加权随机路由。`weight` 缺省值为 1。路由时 MUST 跳过处于 cooldown、DEAD 或 `enabled: false` 状态的模型。

#### Scenario: 多 provider 加权随机
- **WHEN** providers.json 配置 ollama(weight=8)、nvidia(weight=2)、dashscope(weight=1)，且所有模型可用
- **THEN** 请求被分配到 ollama 的概率约为 8/11，nvidia 约 2/11，dashscope 约 1/11

#### Scenario: 某个 provider 全部 cooldown
- **WHEN** ollama 下所有模型均处于 cooldown 状态
- **THEN** 请求仅在 nvidia 和 dashscope 之间按权重分配

#### Scenario: weight 字段缺失
- **WHEN** providers.json 中某个 provider 未配置 weight 字段
- **THEN** 系统 SHALL 使用缺省值 weight=1

#### Scenario: 所有 provider 不可用
- **WHEN** 所有 provider 均处于 cooldown、DEAD 或 disabled 状态
- **THEN** 系统 SHALL 抛出 RuntimeError("所有 LLM Provider 均不可用")

### Requirement: 分级熔断
系统 SHALL 对每个 `provider/model` 组合维护三级熔断状态：COOLING（1-3 次失败，指数退避 2→4→8 min）、WARMING（4-9 次失败，24h cooldown）、DEAD（≥10 次失败，永久跳过）。

#### Scenario: 首次失败进入 COOLING
- **WHEN** 模型 `ollama/gemma4:31b` 首次调用失败
- **THEN** 该模型进入 COOLING 状态，cooldown 2 分钟，期间路由跳过该模型

#### Scenario: 连续失败升级到 WARMING
- **WHEN** 模型连续失败 5 次
- **THEN** 该模型进入 WARMING 状态，cooldown 24 小时

#### Scenario: 连续失败升级到 DEAD
- **WHEN** 模型连续失败 ≥10 次
- **THEN** 该模型进入 DEAD 状态，永久跳过，仅通过 reload API 或热更新恢复

#### Scenario: 成功调用重置熔断
- **WHEN** 处于 COOLING 或 WARMING 状态的模型调用成功
- **THEN** 该模型的失败计数和熔断状态 SHALL 被完全清除

### Requirement: Provider 级别联动熔断
系统 SHALL 监控每个 provider 下模型的整体健康度。当同一 provider 下 ≥50% 的模型处于 WARMING 或 DEAD 状态时，系统 MUST 跳过该 provider 下所有模型。

#### Scenario: Provider 过半模型故障
- **WHEN** ollama 有 4 个模型，其中 3 个处于 DEAD 状态
- **THEN** ollama 整个 provider 被标记为不可用，请求路由到其他 provider

#### Scenario: Provider 恢复
- **WHEN** 被标记不可用的 provider 通过 reload API 重新加载
- **THEN** 该 provider 下的模型 SHALL 重新参与路由

### Requirement: 配置化启用禁用
providers.json SHALL 支持在 provider 和 model 级别通过 `enabled` 字段控制启用/禁用。`enabled` 缺省值为 `true`。

#### Scenario: 禁用单个模型
- **WHEN** providers.json 中某模型配置 `"enabled": false`
- **THEN** 路由 MUST 跳过该模型，且该模型不计入 provider 健康度统计

#### Scenario: 禁用整个 provider
- **WHEN** providers.json 中某 provider 配置 `"enabled": false`
- **THEN** 该 provider 下所有模型 MUST 被跳过

#### Scenario: watchfiles 自动生效
- **WHEN** providers.json 中 enabled 字段被修改且文件保存
- **THEN** watchfiles 检测到变化后自动 reload，新配置立即生效
