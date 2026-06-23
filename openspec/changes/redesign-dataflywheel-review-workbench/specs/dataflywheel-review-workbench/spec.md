## ADDED Requirements

### Requirement: Daily Review Inbox 默认入口
DataFlywheel 工作台 SHALL 默认展示每日质检入口。每日质检入口 SHALL 按 session 聚合风险候选，并按最高风险、证据完整度和待处理状态排序。

#### Scenario: 默认进入每日质检
- **WHEN** 管理员打开 DataFlywheel 工作台
- **THEN** 系统 SHALL 默认展示风险 Session Inbox，而不是默认展示全量 turn 表格
- **AND** 每个 session 卡片 SHALL 显示最高风险问题链、P0/P1、候选链数量、证据状态、主导信号和下一步动作

#### Scenario: 高级搜索保留全量 turn
- **WHEN** 管理员需要按 request_id、session_id 或时间范围查找原始样本
- **THEN** 系统 SHALL 在高级搜索入口提供全量 session / turn 检索能力
- **AND** 高级搜索结果 SHALL 不作为每日质检默认排序入口

### Requirement: ReviewIssueChain 问题链
系统 SHALL 使用 ReviewIssueChain 表示 session 内围绕某个风险点形成的审核任务。ReviewIssueChain SHALL 至少包含 trigger turn、context turns、result turns、candidate type、诊断摘要、证据 checklist、状态、建议标签和人工审核结果。

#### Scenario: 从候选 turn 生成虚拟问题链
- **WHEN** 风险候选 turn 被纳入每日质检
- **THEN** 系统 SHALL 生成一个虚拟 ReviewIssueChain
- **AND** 虚拟链 SHALL 包含候选 turn 作为 trigger turn
- **AND** 虚拟链 SHALL 包含候选 turn 前 1-3 轮相关上下文作为 context turns
- **AND** 虚拟链 SHALL 包含候选 turn 后 1-2 轮确认或执行结果作为 result turns

#### Scenario: 人工调整问题链 turn
- **WHEN** 管理员在 Session Timeline 中认为某个 turn 与当前问题链相关或无关
- **THEN** 系统 SHALL 允许管理员将该 turn 加入或移出问题链
- **AND** 保存审核结果时 SHALL 保留最终 related turn ids

### Requirement: Session Timeline 问题链高亮
每日质检详情 SHALL 展示完整 session timeline，并以视觉标记区分上下文来源 turn、触发 turn、结果 turn 和无关 turn。

#### Scenario: 查看问题链上下文
- **WHEN** 管理员选择一个风险 session 的问题链
- **THEN** 系统 SHALL 在中间区域展示完整 session timeline
- **AND** 系统 SHALL 高亮 trigger turn
- **AND** 系统 SHALL 标记 context turns 和 result turns
- **AND** 无关 turn SHALL 默认弱化或折叠

#### Scenario: 展开 turn 调试证据
- **WHEN** 管理员展开 timeline 中的一个 turn
- **THEN** 系统 SHALL 显示该 turn 的 user message、assistant reply、selected tools、actual tools、pending lifecycle、trace/debug 摘要和事件证据状态

### Requirement: 判断流程优先审核面板
问题链审核面板 SHALL 按固定判断流程展示：诊断摘要、证据 checklist、人工判断、expected behavior、闭环出口。

#### Scenario: 审核面板显示诊断和证据
- **WHEN** 管理员打开一条 ReviewIssueChain
- **THEN** 审核面板 SHALL 显示问题标题、severity、dominant signal、suggested labels 和诊断摘要
- **AND** 审核面板 SHALL 显示证据 checklist，包括已有证据、缺失证据和对应来源 turn

#### Scenario: 缺失证据阻止导出修复包
- **WHEN** ReviewIssueChain 状态为 `needs_evidence`
- **THEN** 系统 SHALL 禁止从该链直接导出 repair pack
- **AND** 审核面板 SHALL 显示缺失的 event、trace、db diff 或上下文证据

### Requirement: 问题链人工结论
系统 SHALL 支持管理员对 ReviewIssueChain 保存人工结论。人工结论 SHALL 包含最终状态、root cause、质量标签、expected behavior、评论和 reviewer 信息。

#### Scenario: 采纳坏例并保存 expected behavior
- **WHEN** 管理员确认问题链为坏例并选择需要回归
- **THEN** 系统 SHALL 要求填写 expected behavior
- **AND** 系统 SHALL 保存 final labels、root cause、expected behavior、comment、reviewer_id 和 reviewed_at
- **AND** 问题链状态 SHALL 更新为 `accepted`

#### Scenario: 驳回误报
- **WHEN** 管理员确认问题链是误报
- **THEN** 系统 SHALL 将问题链状态更新为 `rejected`
- **AND** 系统 SHALL 保存误报原因用于后续规则或 judge 调优

### Requirement: 页面入口收敛
DataFlywheel 工作台 SHALL 将主入口收敛为每日质检、高级搜索、修复包、数据集/评测。原问题候选、Session 复盘、Turn 审核 SHALL 成为每日质检内部工作区或高级搜索能力。

#### Scenario: 原问题候选作为候选来源
- **WHEN** rule、context 或 judge 产生问题候选
- **THEN** 系统 SHALL 将候选纳入每日质检的风险 Session Inbox
- **AND** 系统 SHALL 不要求管理员进入独立问题候选 Tab 才能处理候选

#### Scenario: 原 Turn 审核作为详情能力
- **WHEN** 管理员需要查看单个 turn 的完整调试证据
- **THEN** 系统 SHALL 从 Session Timeline 或审核面板提供展开详情入口
- **AND** 系统 SHALL 不要求管理员从全量 turn 表格进入审核流程
