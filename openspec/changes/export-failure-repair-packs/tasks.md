## 1. 后端修复路由与模型

- [ ] 1.1 新增 repair pack 修复路由服务，输入 sample detail、labels、prelabels、issue candidates、case draft，输出 `fix_target`、`priority`、`suggested_action`、`regression_ready` 和 `verification_commands`
- [ ] 1.2 为 `pending_missed`、`wrong_tool_selection`、`hallucinated_execution`、`tool_error_ignored`、`missing_wage`、`disabled_worker_used`、`sensitive_info_leak`、`bad_reply`、`off_topic` 编写路由单元测试
- [ ] 1.3 新增 repair pack 元数据模型和迁移，记录 `pack_id`、`farm_id`、`fix_target`、`labels`、`source_sample_ids`、`status`、`export_path`、`created_by` 和时间字段
- [ ] 1.4 实现 repair pack 状态更新逻辑，支持导出成功、导出失败、验证失败、已修复 resolved 状态

## 2. Repair Pack 导出服务

- [ ] 2.1 实现 repair pack builder，生成 `manifest.json`、`cases.jsonl`、`README.md`、`debug/` 和 `regression-drafts/` 目录结构
- [ ] 2.2 实现导出筛选，支持按标签、`fix_target`、优先级、样本数量、`regression_ready` 筛选样本
- [ ] 2.3 实现单包修复目标一致性校验，混合多个主 `fix_target` 时返回分组建议并拒绝导出
- [ ] 2.4 实现 debug evidence 脱敏工具，覆盖 API key、token、secret、`.env`、手机号和精确地址等敏感内容
- [ ] 2.5 在导出证据缺失时写入 `manifest.json.warnings`，并将对应 case 标记为 `regression_ready=false`
- [ ] 2.6 为 repair pack builder 增加单元测试，验证文件结构、manifest 字段、case 字段、README 指令和脱敏结果

## 3. Admin API 与 Data Flywheel 集成

- [ ] 3.1 新增获取修复候选 API，返回样本级 `fix_target`、优先级、建议动作、回归准备状态和验证命令
- [ ] 3.2 新增生成 repair pack API，接收筛选条件和可选人工覆盖 `fix_target`
- [ ] 3.3 新增获取 repair pack 详情 API，返回 manifest 摘要、关联样本、状态、导出路径和 warnings
- [ ] 3.4 新增 repair pack 标记已修复 API，写入修复说明和验证摘要，并将关联 open labels 标记为 resolved
- [ ] 3.5 新增 repair pack 验证失败回写 API，保留 labels 为 open 并记录失败摘要
- [ ] 3.6 为新增 API 增加权限、错误码、混合 `fix_target`、脱敏和 resolved 回写测试

## 4. 前端工作流

- [ ] 4.1 在 Data Flywheel 列表或详情中展示修复候选信息，包括 `fix_target`、优先级、`regression_ready` 和建议动作
- [ ] 4.2 增加“生成修复包”交互，支持按当前筛选结果或选中样本导出，并在混合修复目标时展示分组建议
- [ ] 4.3 增加 repair pack 详情面板，展示 manifest 摘要、cases 数量、warnings、验证命令和 vibecoding README 预览
- [ ] 4.4 增加“标记已修复”和“记录验证失败”操作，分别调用 resolved 回写和失败回写 API
- [ ] 4.5 为前端 API 封装和页面交互增加测试，覆盖导出、混合目标拦截、warnings 展示和 resolved 后列表更新

## 5. Simulation / Evaluation 衔接

- [ ] 5.1 扩展 case draft metadata，保留 `pack_id`、`source_sample_id`、`fix_target` 和原始标签
- [ ] 5.2 支持从 repair pack regression draft 导入或生成 evaluation replay case，并保留 issue assertions
- [ ] 5.3 支持 Simulation 运行 repair pack regression cases 时返回 `pack_id`、`source_sample_id`、`fix_target` 和失败断言
- [ ] 5.4 将 Simulation / Evaluation 结果提供给 Data Flywheel，用于 repair pack 验证摘要和 resolved 判断

## 6. 验证与文档

- [ ] 6.1 补充面向 vibecoding 的 repair pack README 模板说明，明确读取顺序、修复限制和完成回报格式
- [ ] 6.2 更新 Data Flywheel 相关文档，说明 bad case 如何导出为 repair pack 并进入 vibecoding 修复循环
- [ ] 6.3 运行后端相关测试：Data Flywheel service/API、repair pack builder、Simulation/Evaluation 衔接测试
- [ ] 6.4 运行前端相关测试：Data Flywheel 页面和 API 封装测试
- [ ] 6.5 执行项目 lint 和 OpenSpec 校验，确认规格、任务和实现一致
