## MODIFIED Requirements

### Requirement: 上下文选择器
系统 SHALL 为农场状态、种植周期、种植单元、作业单、工人、人工未结摘要、天气、账务、会话历史、用户设置、短时记忆、长期记忆和检索结果提供独立 selector。Selector SHALL 可独立测试，并可由 Skill metadata 的 context dependencies 触发。

#### Scenario: 新增账务上下文
- **WHEN** 开发者调整账务摘要注入逻辑
- **THEN** 修改发生在账务 selector 中，并可通过 selector 单元测试验证

#### Scenario: 更新茬口需要活跃批次上下文
- **WHEN** Tool selection includes `update_crop_cycle`
- **THEN** ContextPolicy selects crop cycle context and includes candidate active or planned cycles needed for target resolution

#### Scenario: 结算人工需要工人和未付摘要
- **WHEN** Tool selection includes `settle_labor_payment`
- **THEN** ContextPolicy selects worker context and unpaid labor summary context

### Requirement: 上下文可观测性
Context Builder SHALL 记录每次请求选中的 block、被压缩的 block、被丢弃的 block、token 估算、耗时和触发该 block 的 Skill metadata dependency。

#### Scenario: 调试上下文缺失
- **WHEN** Agent 回复缺少某项农场信息
- **THEN** 开发者可以通过 trace 查看该信息是否被 selector 选中、是否被预算策略丢弃

#### Scenario: 查看 Skill 触发的上下文
- **WHEN** 开发者查看一次 `update_crop_cycle` 请求 trace
- **THEN** trace shows which context blocks were selected because of `update_crop_cycle` context dependencies
