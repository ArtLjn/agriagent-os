## Context

DataFlywheel 已具备样本列表、详情、标注、AI 预判、case draft 和 repair pack 基础能力；`add-dataflywheel-discovery-layer` 已补充 risk score、rule/judge 信号和风险排序。但当前工作台的信息架构仍以全量 turn 表格和右侧日志详情为主，用户很难从单轮详情里理解多轮上下文问题。

Farm Manager 的高价值坏例常常是一条问题链，例如「欠款查询列出未付工人 → 批量结算意图 → pending 参数收窄 → 确认后实际只处理一个人」。因此审核对象需要从单个 turn 升级为 session 内的 `ReviewIssueChain`，同时保留 turn 作为最小证据单元。

设计基线已记录在 `farm-manager-design-spec/01_正式设计/06_数据飞轮与评测.md` 第 10 节。

## Goals / Non-Goals

**Goals:**

- 默认首页改为每日质检待办，按风险 session 分组，而不是默认平铺全部 turn。
- 引入 `ReviewIssueChain` 作为审核任务对象，包含 trigger/context/result turns、诊断、证据、人工 expected 和状态。
- 将 DataFlywheel 主工作流调整为：风险 Session Inbox → Session Timeline → 问题链审核面板 → regression / repair pack / dataset。
- MVP 使用虚拟问题链，避免第一阶段引入大规模 schema 迁移。
- 人工审核必须能沉淀 expected behavior，作为 regression draft 和 repair pack 的前置条件。

**Non-Goals:**

- 不替代 `add-dataflywheel-discovery-layer` 的 rule/judge/risk 发现层。
- 不在 MVP 做完整语义任务链识别或聚类。
- 不引入 Kafka、Flink、向量库或新数据基础设施。
- 不要求一次性移除现有样本队列、问题候选、Session 复盘和 Turn 审核组件；先迁移入口和组合方式。
- 不让 AI judge 自动写最终真值。

## Decisions

### D1: 默认入口使用 Daily Review Inbox，而不是全量 turn 列表

选择：DataFlywheel 默认显示风险 Session Inbox，按 session 聚合待处理问题链。

理由：

- 标注员的第一问题是“今天先处理什么”，不是“数据库里有哪些 turn”。
- session 是理解多轮上下文的最小自然容器。
- turn 平铺适合搜索和底层调试，不适合质检主流程。

替代方案：

- 继续使用 turn-first：实现成本低，但无法解决上下文无从查看的问题。
- 修复流水线首页：适合工程管理，但对每日质检入口过重。

### D2: 审核对象使用 ReviewIssueChain

选择：引入 `ReviewIssueChain` 作为 session 内问题链，关联 trigger/context/result turns。

理由：

- 单 turn 标签丢失上下文来源和执行后果。
- 整个 session 标签太粗，难以生成精确 regression。
- 问题链能同时服务人工审核、expected behavior、case draft 和 repair pack。

替代方案：

- 只增强 turn detail：仍然要求人自己拼上下文。
- 只做 session 级标注：难以定位具体修复目标和断言。

### D3: MVP 使用虚拟问题链，保存后再持久化

选择：第一阶段由 API 根据候选 turn 动态返回虚拟链：前 1-3 轮作为 context，候选 turn 作为 trigger，后 1-2 轮确认/执行 turn 作为 result；人工保存后再生成稳定 `chain_id`。

理由：

- 快速改善体验，避免 schema 先行造成设计冻结。
- 可复用现有 `agent_turns`、`conversation_messages`、event JSONL、sample detail API。
- 后续可以平滑迁移到持久化 `review_issue_chains` 表。

替代方案：

- 立即建完整表：更规范，但会拉长实现周期。
- 前端自行拼链：后端与前端逻辑容易不一致。

### D4: 右侧面板使用判断流程优先，而不是字段堆叠

选择：审核面板顺序固定为诊断摘要 → 证据 checklist → 人工判断 → expected behavior → 闭环出口。

理由：

- 这符合人工审核的认知顺序。
- expected behavior 是回归和修复闭环的关键资产。
- checklist 能明确“缺什么证据”，避免标注员盯着风险分数无从下手。

替代方案：

- 标签优先：接近现状，但仍无法沉淀可执行 expected。
- 修复出口优先：工程闭环强，但会在判断前过早进入修复。

### D5: 入口收敛为每日质检 / 高级搜索 / 修复包 / 数据集评测

选择：原样本队列、问题候选、Session 复盘、Turn 审核从主 Tab 降级为新入口下的工作区或组件。

理由：

- 降低认知负担。
- 保留现有能力但重新组织。
- 高级搜索仍支持 request_id、session_id、时间范围等调试场景。

### D6: 问题链人工结论使用独立持久化表

选择：MVP 保存人工审核结果时新增 `agent_review_issue_chains` 表，而不是塞入 label metadata。

理由：

- `expected_behavior`、最终 related turns、误报原因和缺失证据是 chain-level 资产，不适合作为单个 turn label comment。
- 独立表可用 `chain_id` 稳定定位同一条链，并与 `AgentCaseDraft`、`AgentRepairPack` 的独立元数据表风格一致。
- accepted 时仍可复用 trigger sample 的质量标签，保持现有样本标签和 repair candidate 能力可见。

替代方案：

- 存入 label metadata：迁移成本低，但会混淆单 turn 标签和问题链结论，且难以表达人工调整后的 context/result turns。

## Risks / Trade-offs

- **虚拟问题链误包含无关 turn** → 在 UI 提供人工增删相关 turn，保存时记录最终 related turn ids。
- **按 session 分组后列表密度下降** → session 卡片展示问题链数量和最高风险，支持展开链列表。
- **现有组件复用导致过渡期 UI 不一致** → MVP 只重排组合，随后逐步抽出专用组件。
- **expected behavior 填写增加人工成本** → 仅在 accepted + needs_regression 时强制；误报和暂不处理不要求填写。
- **新增 chain 状态与现有 label 状态不一致** → 保存时由后端统一写 chain status、label status 和 repair candidate 状态。
- **与 discovery-layer 变更重叠** → 本 change 消费 risk/rule/judge/context 信号，不重新定义发现层评分实现。

## Migration Plan

1. 新增 review inbox API，按 session 聚合现有 risk samples，返回虚拟问题链摘要。
2. 新增 issue chain detail API，返回 session timeline、trigger/context/result turns、诊断摘要、证据 checklist 和现有 labels/prelabels。
3. 前端新增 Daily Review 页面组合：左侧 Inbox、中间 Timeline、右侧 Review Panel。
4. 将原全量 turn 列表迁移到高级搜索入口，保留 URL 和调试能力。
5. 修改 case draft 创建入口：从 chain 的 expected behavior 和 related turns 生成草稿。
6. 修改 repair pack 创建入口：支持 chain source，并保留兼容 sample source。
7. 灰度阶段保留旧 Tab 开关或隐藏入口，验证标注员完成率和 regression_ready_rate 后再移除旧主入口。

Rollback：

- 将 DataFlywheel 默认 active tab 切回旧样本队列。
- 保留新增 API 不影响旧列表和标注 API。
- chain-created labels 可继续显示为普通 labels，repair pack 仍兼容 sample source。

## Open Questions

- `ReviewIssueChain` 是否在 MVP 保存人工结论时立即持久化为独立表，还是先存入 label metadata？
- 高级搜索入口是否继续保留原 Tab 视觉，还是拆成单独页面？
- 首批 `candidate_type` 是否只覆盖 `bulk_intent_narrowed_to_single_entity`、`referential_scope_lost`、`confirmation_text_contradicts_intent` 三类上下文问题？
