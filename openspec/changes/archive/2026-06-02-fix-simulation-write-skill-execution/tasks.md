## 1. 执行引擎 Session 生命周期修复

- [ ] 1.1 修改 `_execute_run`：创建新的 `SessionLocal()` session 和新的 `SimulationRunner`
- [ ] 1.2 确保 `run_batch` 完成后关闭后台任务的 session
- [ ] 1.3 删除 `start_run` 中的 `task_runner` 创建逻辑（改为在 `_execute_run` 中创建）

## 2. 测试数据隔离

- [ ] 2.1 实现 `SimulationRunner._setup_precondition` 的 `clean_tables` 逻辑
- [ ] 2.2 为涉及 write 操作的测试用例添加 `precondition.clean_tables` 字段
- [ ] 2.3 确保 `clean_tables` 只删除与当前 farm_id 匹配的记录

## 3. 一致性检查增强

- [ ] 3.1 修改 `check_consistency`：新增 `execution_failure` 错误类型
- [ ] 3.2 集成 trace 查询：通过 `trace_collector` 判断 skill 是否被真正调用
- [ ] 3.3 修改 `_check_expected_changes`：`match_fields` 字符串字段支持子串匹配
- [ ] 3.4 修改 `_check_expected_changes`：数字字段支持 `int == float` 等值匹配
- [ ] 3.5 修复取消操作误判：当 `expected_db_changes` 为空且用户取消时，不标记 hallucination

## 4. 前端适配

- [ ] 4.1 在错误类型展示中新增 `execution_failure` 的 Tag 样式
- [ ] 4.2 验证历史运行点击查看详情功能正常

## 5. 测试验证

- [ ] 5.1 运行全部 14 个测试用例，记录通过/失败情况
- [ ] 5.2 验证 TC-WRITE-001（记账）通过且 DB 有实际变化
- [ ] 5.3 验证取消用例（TC-ADV-001）不被误判为 hallucination
- [ ] 5.4 检查 `simulation_results` SQLite 表是否正确写入运行记录
