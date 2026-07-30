## 1. 配置与基础设施

- [x] 1.1 在 `backend/app/core/config.py` 的 `AIConfig` 新增字段：`enable_session_summary: bool = True`、`session_summary_message_threshold: int = 12`、`session_summary_debounce_minutes: int = 30`、`session_summary_max_tokens: int = 500`
- [x] 1.2 在 `backend/config.yaml` 与 `backend/config.yaml.example` 的 `ai:` 段补对应字段及注释（参考现有字段风格）
- [x] 1.3 在 `backend/app/api/admin_config.py` 暴露 `enable_session_summary` 到 admin 读取接口（便于线上热关闭）

## 2. 摘要 Prompt 模板

- [x] 2.1 新建 `backend/app/memory/prompts/summary.md`，包含字段保护要求（金额、日期、地块/作物名、人名、pending action 类型与关键参数）、输出格式（追加段落，非重写）、语言与人设对齐说明
- [x] 2.2 在 PromptComposer 注册该模板（或在 summarizer 内直接读取，按现有 prompt 工程约定选择）
- [x] 2.3 单测覆盖模板渲染：传入 current_summary、recent_messages、persona 变量后输出包含强制字段提示

## 3. Summarizer 实现

- [x] 3.1 新建 `backend/app/memory/summarizer.py`，定义 `async def generate_summary(llm, current_summary, old_messages, persona) -> str | None`
- [x] 3.2 复用 `backend/app/agent/runtime/llm_support.py` 的熔断器（`_build_circuit_key` / `_record_llm_failure` / `_record_llm_success`）记录摘要调用的成功失败
- [x] 3.3 调用失败 / 超时 / 内容为空时返回 None（不抛出），由上层降级
- [x] 3.4 摘要输入 / 输出 token、耗时通过 `get_collector()` 记录 trace 事件 `summary_generated`

## 4. MemoryService 集成

- [x] 4.1 在 `backend/app/memory/service.py` 新增 `async def maybe_summarize(db, conversation_id, farm_id, session_id, messages)`
- [x] 4.2 实现阈值判断：消息数 < `session_summary_message_threshold` 直接返回并记录 `summary_skipped` (reason=below_threshold)
- [x] 4.3 实现防抖：读取 `conversations.summary_updated_at`，距今 < 防抖窗口则跳过并记录 (reason=within_debounce_window)
- [x] 4.4 实现 feature flag 短路：`ai.enable_session_summary=false` 跳过 (reason=feature_disabled)
- [x] 4.5 实现熔断器短路：熔断开启时跳过 (reason=circuit_open)
- [x] 4.6 调用 summarizer 得到 summary 后，用乐观锁（基于 summary_updated_at）写入 `conversations.summary` 与 `summary_updated_at`；版本冲突时放弃本次写入
- [x] 4.7 同步调用 `set_session_summary` 更新 in-memory cache（保持向后兼容）
- [x] 4.8 整个方法 catch 所有异常，记录结构化日志，不向上抛出

## 5. Response 节点接入

- [x] 5.1 在 `backend/app/agent/application/chat_use_case.py` 的 `chat()` / `stream_chat_events()` 调用 `SessionFlywheelRecorder.finish_turn()` 完成助手消息落库后，`asyncio.create_task(memory_service.maybe_summarize(...))`
- [x] 5.2 异步任务设置 30s 超时；超时记录日志但不影响主流程
- [x] 5.3 通过依赖注入获取 `memory_service`，不直接 `import`（保持模块边界）
- [x] 5.4 单测覆盖：mock memory_service 验证任务被正确创建并捕获异常

## 6. ConversationSelector 注入摘要

- [x] 6.1 修改 `backend/app/context/selectors/conversation.py`，查询时按 `conversations` 表与 `session_id` 匹配
- [x] 6.2 当 `conversations.summary` 非空时，额外生成一个 ContextBlock（key=`conversation_summary`、source=`conversation.summary`、priority=50、compressible=True、min_tokens=64、metadata={layer: working, cache_scope: session}）
- [x] 6.3 当 summary 为空时不产生空 block
- [x] 6.4 单测覆盖：有 summary / 无 summary / summary 为 NULL 三种情况

## 7. 单元测试

- [x] 7.1 新建 `backend/tests/memory/test_summarizer.py`：3 类测试（Meta / Normal / Error）覆盖 prompt 渲染、LLM 调用成功、LLM 调用失败 / 超时 / 空响应
- [x] 7.2 新建 `backend/tests/memory/test_maybe_summarize.py`：覆盖阈值跳过、防抖跳过、feature flag 关闭、熔断开启、乐观锁冲突、正常写入 6 个场景
- [x] 7.3 扩展 `backend/tests/context/test_selectors.py`：覆盖新 conversation_summary block 的注入与空值降级
- [x] 7.4 扩展 `backend/tests/agent/test_chat_use_case.py`：验证 Response / 聊天完成后会触发 maybe_summarize 异步任务

## 8. 集成测试与仿真

- [x] 8.1 在 `backend/tests/agent/test_running_summary_flow.py` 增加多轮场景：模拟 13 轮对话后验证 `conversations.summary` 被写入且 ConversationSelector 注入了 conversation_summary block
- [x] 8.2 在 `backend/data/simulation_cases/` 新增 1 条多轮失忆回归用例：13 轮后追问前 6 轮的关键字段（金额/作物名），断言 LLM 能正确指代
- [ ] 8.3 跑 simulation smoke（当前项目未提供 `python -m app.simulation.run` CLI，待接入实际 runner 命令后执行）

## 9. 可观测性与告警

- [x] 9.1 验证 trace 事件 `summary_generated` / `summary_skipped` 含必要字段（farm_id、session_id、reason、tokens、duration_ms）
- [x] 9.2 在 `backend/app/observability/metrics.py` 增加计数器：`session_summary_generated_total`、`session_summary_skipped_total{reason}`、`session_summary_failed_total`
- [x] 9.3 在 Admin Web 的 Trace 详情页能查看 `summary_generated` 事件（验证现有 trace 渲染对新事件兼容，无需新组件）

## 10. 文档同步

- [x] 10.1 更新 `docs/farm-manager-design-spec/01_正式设计/03_Context工程.md` § 11 当前状态：summary 接通状态从 🚧 改为 ✅
- [x] 10.2 更新 `docs/farm-manager-design-spec/01_正式设计/04_Memory工程.md` § 14 当前状态：`set_session_summary` 接通状态从 🚧 改为 ✅
- [x] 10.3 更新 `docs/farm-manager-design-spec/README.md` 变更记录，加 v1.0 行（Phase A 落地）
- [x] 10.4 在 `docs/architecture/evolution-roadmap.md` 标记 Phase 4 中 "Memory 会话摘要自动生成" 子项进度

## 11. 上线与验证

- [ ] 11.1 合并 PR 到 main，CI 七道门全部通过
- [ ] 11.2 部署 staging，feature flag `ai.enable_session_summary=false`，观察 2 小时
- [ ] 11.3 staging 开启 feature flag，跑 24 小时；trace 抽检：摘要关键字段命中率 ≥ 90%
- [ ] 11.4 部署生产，feature flag 默认 false → 开启 5 个内测农户 → 观察 1 周 → 全量开启
- [ ] 11.5 上线 1 周后核查单户月增成本，确认 < ¥2
