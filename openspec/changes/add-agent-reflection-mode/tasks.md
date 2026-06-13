## 1. Reflection Core

- [x] 1.1 新增 `backend/app/agent/reflector/` 模块结构，包含 models、policy、checks、service 和 `__init__.py`
- [x] 1.2 定义 `ReflectionTrigger`、`ReflectionDecision`、`ReflectionIssue`、`ReflectionResult` 等结构化模型
- [x] 1.3 实现触发策略，覆盖 pre-write plan、pre-execution pending plan、post-tool result、fallback guard
- [x] 1.4 实现规则检查函数，覆盖参数缺失、确认文案不一致、工具失败成功话术、必需工具未调用、多步骤依赖异常
- [x] 1.5 添加配置开关，支持全局关闭 Reflection 和按 trigger 关闭

## 2. Write Flow Integration

- [x] 2.1 在 pending action 创建或展示前接入 pre-write Reflection 检查
- [x] 2.2 在 pending plan 创建或展示前接入多步骤计划一致性检查
- [x] 2.3 在用户确认 pending action 执行前接入 pre-execution Reflection 检查
- [x] 2.4 在用户确认 pending plan 执行前接入 pre-execution Reflection 检查
- [x] 2.5 对 `block_write`、`ask_clarification` 和检查异常实现 fail-closed 响应

## 3. Runtime And Response Integration

- [x] 3.1 在工具执行后、最终回复前接入 post-tool Reflection 检查
- [x] 3.2 对工具失败但回复声称成功的场景生成安全失败回复
- [x] 3.3 对 Router 已选择必需工具但 LLM 未调用工具的场景触发重试或安全兜底
- [x] 3.4 确保低风险闲聊和确定性直达读查询不触发 Reflection
- [x] 3.5 保持 `/agent/chat` 和 `/agent/chat/stream` 外部响应契约兼容

## 4. Observability And Evaluation

- [x] 4.1 在 trace collector 中记录 `reflection_check` 事件，包含 trigger、decision、issues、关联工具或 plan 标识和耗时
- [ ] 4.2 在 debug export 中暴露 reflection 事件摘要
- [x] 4.3 扩展 Agent diagnostics，展示 Reflection 阻断、降级和通过原因
- [ ] 4.4 为 Evaluation 增加 reflection issue 标签或指标汇总
- [ ] 4.5 确保 trace payload 不记录敏感完整参数或长文本

## 5. Tests And Verification

- [x] 5.1 添加 reflector 模型、策略和规则检查单元测试
- [x] 5.2 添加写操作缺参被 Reflection 阻断的测试
- [x] 5.3 添加 pending plan 确认文案与参数不一致被阻断的测试
- [x] 5.4 添加工具失败但最终回复声称成功时被安全改写的测试
- [x] 5.5 添加必需工具未调用时触发重试或兜底的测试
- [x] 5.6 添加低风险请求不触发 Reflection 的测试
- [ ] 5.7 运行 `poetry run pytest -v` 验证后端测试
- [ ] 5.8 运行 `ruff check . && ruff format .` 验证格式和 lint
- [ ] 5.9 运行 `bash scripts/check-layer-deps.sh` 验证架构边界

## 6. Architecture Guards And Documentation

- [x] 6.1 添加 Reflection 边界 guard，防止策略、模型和规则检查散落到 Runtime/Executor
- [x] 6.2 更新 Agent 平台边界文档，说明 `agent/reflector/` 职责和 Runtime/Executor 调用边界
- [x] 6.3 更新标准请求生命周期，纳入写入风险、工具结果和最终回复一致性检查
