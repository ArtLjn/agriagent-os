## 1. 标签与后端契约

- [ ] 1.1 将 `tool_parameter_mismatch` 加入后端 DataFlywheel 允许标签集合和相关校验测试
- [ ] 1.2 将 `tool_parameter_mismatch` 加入前端 `DataFlywheelLabel` 类型、筛选选项和展示文案
- [ ] 1.3 将 IssueChain 审核面板标签选项扩展为设计文档 §6 的完整固定标签集合
- [ ] 1.4 增加后端测试覆盖 accepted ReviewIssueChain 保存 `tool_parameter_mismatch`

## 2. ReviewIssueChain 证据状态增强

- [ ] 2.1 扩展 ReviewIssueChain evidence checklist，区分 `event_log`、`chat_messages`、`router_decision`、`tool_result`、`pending_lifecycle`、`trace`、`db_diff` 和 `backfilled_event`
- [ ] 2.2 在回填事件或 message meta 中检测 `backfilled/event_backfilled` 并透出到 timeline/checklist
- [ ] 2.3 缺少 trace 或 db diff 时返回明确 missing/needs_human 状态，避免空对象被当作无问题证据
- [ ] 2.4 增加后端单测覆盖 missing trace、missing db diff、backfilled event 三类证据状态

## 3. Chain 闭环出口

- [ ] 3.1 在前端 API 层补齐或确认 `createReviewIssueChainCaseDraft(chainId)` 和 `createReviewIssueChainRepairPack(chainId)` 方法
- [ ] 3.2 在 `IssueChainReviewPanel` 增加“生成回归草稿”和“导出修复包”按钮
- [ ] 3.3 按 chain 状态控制按钮可用性：未 accepted、缺 expected behavior、needs_evidence 时禁用并显示阻断原因
- [ ] 3.4 成功生成 regression draft 后展示 `CaseDraftPreview`，并保留 `chain_id` 和 related turns
- [ ] 3.5 成功导出 repair pack 后展示 `RepairPackPreview`，并保留 `source_chain_ids`
- [ ] 3.6 增加前端测试覆盖 chain draft、chain repair pack、阻断原因和成功预览

## 4. 高级搜索边界收口

- [ ] 4.1 从 Advanced Search 的默认详情栏移除最终人工标注保存入口
- [ ] 4.2 从 Advanced Search / Turn Review 兼容视图移除正式 regression draft 和 repair pack 按钮
- [ ] 4.3 在 raw turn 详情中提供“创建候选链 / 打开每日质检”动作占位或入口
- [ ] 4.4 保留 Debug JSON、Evidence Pack、trace 跳转和原始证据查看能力
- [ ] 4.5 增加前端测试确认高级搜索不能保存 final label、不能直接导出正式 repair pack、不能直接创建正式 regression draft

## 5. Sample 级兼容路径限制

- [ ] 5.1 对 sample 级 regression draft API 或响应增加 compatibility/debug 标识
- [ ] 5.2 对 sample 级 repair pack API 或响应增加 compatibility/debug 标识
- [ ] 5.3 确保产品 UI 的正式导出路径不再调用 sample 级 repair/regression API
- [ ] 5.4 增加后端测试覆盖 sample 级兼容路径不会伪装为正式 IssueChain 资产

## 6. 验证与文档

- [ ] 6.1 更新 `farm-manager-design-spec/01_正式设计/06_数据飞轮与评测.md` 当前状态，标明本 change 收口页面边界和旧入口状态
- [ ] 6.2 运行后端 DataFlywheel 相关测试
- [ ] 6.3 运行前端 DataFlywheel 相关测试
- [ ] 6.4 运行 `openspec validate align-dataflywheel-issue-chain-closure --type change --strict`
- [ ] 6.5 用批量作用域错配样本手工验收：每日质检 → `tool_parameter_mismatch` → expected behavior → regression draft → repair pack
