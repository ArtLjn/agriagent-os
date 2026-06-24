## 1. Review Issue Chain API

- [x] 1.1 定义虚拟 `ReviewIssueChain` response schema，包含 `chain_id`、`session_id`、`trigger_turn_id`、`context_turn_ids`、`result_turn_ids`、`status`、`severity`、`dominant_signal`、`diagnosis`、`ai_judge`、`human_review`、`regression` 和 `repair`
- [x] 1.2 新增 Daily Review Inbox API，按 session 聚合风险样本并返回 session 卡片、最高风险链、候选链数量、证据状态和下一步动作
- [x] 1.3 新增 ReviewIssueChain detail API，返回 session timeline、trigger/context/result turns、turn 调试摘要、证据 checklist、已有标签和 AI 预判
- [x] 1.4 实现虚拟问题链生成逻辑：候选 turn 为 trigger，前 1-3 轮作为 context，后 1-2 轮确认/执行 turn 作为 result
- [x] 1.5 支持人工增删 related turns 并在保存审核结果时保留最终 related turn ids
- [x] 1.6 后端单测覆盖 session 聚合、虚拟链生成、证据缺失、related turn 调整和权限边界

## 2. Chain Review Persistence

- [x] 2.1 设计 MVP 持久化方案：使用独立 `review_issue_chains` 表或 label metadata，并记录迁移决策
- [x] 2.2 实现保存问题链人工结论 API，支持 `accepted`、`rejected`、`not_actionable`、`needs_evidence`
- [x] 2.3 保存 accepted 结论时要求 `root_cause`、`final_labels` 和 `expected_behavior`
- [x] 2.4 保存 rejected 结论时要求误报原因，并保留用于规则或 judge 调优
- [x] 2.5 保存 needs_evidence 时记录缺失 event、trace、db diff 或上下文证据
- [x] 2.6 后端单测覆盖状态转换、required fields、误报原因和 expected behavior 校验

## 3. DataFlywheel Frontend IA

- [x] 3.1 将 DataFlywheel 默认入口改为 `每日质检`
- [x] 3.2 新增或重组顶部入口为 `每日质检`、`高级搜索`、`修复包`、`数据集/评测`
- [x] 3.3 将原全量 turn / session 检索能力迁移到 `高级搜索`
- [x] 3.4 将原问题候选、Session 复盘、Turn 审核降级为每日质检内部工作区或详情能力
- [x] 3.5 前端单测覆盖默认入口、入口切换和旧搜索能力仍可访问

## 4. Daily Review Inbox UI

- [x] 4.1 实现左侧 Risk Session Inbox，展示 session id、摘要、最高风险链、P0/P1、候选链数量、证据状态、主导信号、处理状态和下一步动作
- [x] 4.2 实现 inbox 排序：最高风险、证据完整度、处理状态、最近时间
- [x] 4.3 支持筛选 P0、needs_evidence、ready_for_review、AI 待审和已处理状态
- [x] 4.4 点击 session 后加载默认最高风险问题链详情
- [x] 4.5 前端单测覆盖 session 卡片字段、排序、筛选和选择行为

## 5. Session Timeline UI

- [x] 5.1 实现中间 Session Timeline，展示完整会话消息但默认弱化无关 turn
- [x] 5.2 高亮 trigger turn，并标记 context turns 与 result turns
- [x] 5.3 每个 turn 默认展示 user/assistant 摘要、selected/actual tools、pending 摘要和事件证据状态
- [x] 5.4 支持展开 turn 查看完整工具、pending lifecycle、router JSON、trace/debug 摘要
- [x] 5.5 支持人工将 turn 加入或移出当前问题链
- [x] 5.6 前端单测覆盖高亮、展开、related turn 调整和空/缺证据状态

## 6. Chain Review Panel UI

- [x] 6.1 实现右侧审核面板，固定展示诊断摘要、证据 checklist、人工判断、expected behavior、闭环出口
- [x] 6.2 证据 checklist 支持 present、missing、needs_human 状态，并可跳转到来源 turn
- [x] 6.3 人工判断支持 accepted、rejected、not_actionable、needs_evidence
- [x] 6.4 accepted + needs_regression 时必须填写 expected behavior
- [x] 6.5 rejected 时必须填写误报原因
- [x] 6.6 审核成功后支持保存并进入下一条风险链
- [x] 6.7 前端单测覆盖 required fields、状态切换、保存 payload 和下一条行为

## 7. Regression Draft Integration

- [x] 7.1 修改 case draft 创建 API，支持从 `chain_id` 或虚拟链 payload 创建 regression draft
- [x] 7.2 从问题链生成 draft 时保留 trigger/context/result turns、expected behavior、root cause、quality labels 和 issue assertions
- [x] 7.3 缺少 expected behavior 时拒绝生成 regression draft
- [x] 7.4 Evaluation replay 导入 chain-derived draft 时保留 `chain_id` 和 related turns
- [x] 7.5 后端测试覆盖 chain draft 创建、缺 expected 拒绝和 evaluation metadata 保留

## 8. Repair Pack Integration

- [x] 8.1 修改 repair candidate routing，支持 `ReviewIssueChain` 来源
- [x] 8.2 将 `tool_parameter_mismatch` / `bulk_intent_narrowed_to_single_entity` 路由到 `router` fix target
- [x] 8.3 支持从 accepted 且 regression-ready 的问题链导出 repair pack
- [x] 8.4 repair pack manifest 和 cases.jsonl 保留 `source_chain_ids`、trigger/context/result turns、root cause、expected behavior 和证据缺失 warnings
- [x] 8.5 needs_evidence 或缺 expected behavior 的问题链禁止导出 repair pack
- [x] 8.6 后端测试覆盖链路由、导出、追溯字段和禁止导出条件

## 9. Verification and Documentation

- [x] 9.1 更新 `farm-manager-design-spec/01_正式设计/06_数据飞轮与评测.md` 的当前状态为实现中或已落地
- [x] 9.2 增加面向标注员的简短使用说明：每日质检如何处理一条问题链
- [x] 9.3 运行后端相关 pytest：DataFlywheel API、judge/prelabel、case draft、repair pack service
- [x] 9.4 运行前端 DataFlywheel 测试
- [ ] 9.5 用 `repair-manual_triage-2ced95bdeea1` 对应会话做手工验收：风险 session → 问题链 → expected → regression draft
- [x] 9.6 运行 `openspec validate redesign-dataflywheel-review-workbench --type change --strict`
