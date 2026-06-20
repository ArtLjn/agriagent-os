## 1. 配置与基础设施

- [ ] 1.1 在 `backend/app/core/config.py` 的 `AIConfig` 新增字段：`enable_session_summary: bool = True`、`session_summary_message_threshold: int = 12`、`session_summary_debounce_minutes: int = 30`、`session_summary_max_tokens: int = 500`
- [ ] 1.2 在 `backend/config.yaml` 与 `backend/config.yaml.example` 的 `ai:` 段补对应字段及注释（参考现有字段风格）
- [ ] 1.3 在 `backend/app/api/admin_config.py` 暴露 `enable_session_summary` 到 admin 读取接口（便于线上热关闭）

## 2. 摘要 Prompt 模板

- [ ] 2.1 新建 `backend/app/memory/prompts/summary.md`，包含字段保护要求（金额、日期、地块/作物名、人名、pending action 类型与关键参数）、输出格式（追加段落，非重写）、语言与人设对齐说明
- [ ] 2.2 在 PromptComposer 注册该模板（或在 summarizer 内直接读取，按现有 prompt 工程约定选择）
- [ ] 2.3 单测覆盖模板渲染：传入 current_summary、recent_messages、persona 变量后输出包含强制字段提示

## 3. Summarizer 实现

- [ ] 3.1 新建 `backend/app/memory/summarizer.py`，定义 `async def generate_summary(llm, current_summary, old_messages, persona) -> str | None`
- [ ] 3.2 复用 `backend/app/agent/runtime/llm_support.py` 的熔断器（`_build_circuit_key` / `_record_llm_failure` / `_record_llm_success`）记录摘要调用的成功失败
- [ ] 3.3 调用失败 / 超时 / 内容为空时返回 None（不抛出），由上层降级
- [ ] 3.4 摘要输入 / 输出 token、耗时通过 `get_collector()` 记录 trace 事件 `summary_generated`

## 4. MemoryService 集成

- [ ] 4.1 在 `backend/app/memory/service.py` 新增 `async def maybe_summarize(db, conversation_id, farm_id, session_id, messages)`
- [ ] 4.2 实现阈值判断：消息数 < `session_summary_message_threshold` 直接返回并记录 `summary_skipped` (reason=below_threshold)
- [ ] 4.3 实现防抖：读取 `conversations.summary_updated_at`，距今 < 防抖窗口则跳过并记录 (reason=within_debounce_window)
- [ ] 4.4 实现 feature flag 短路：`ai.enable_session_summary=false` 跳过 (reason=feature_disabled)
- [ ] 4.5 实现熔断器短路：熔断开启时跳过 (reason=circuit_open)
- [ ] 4.6 调用 summarizer 得到 summary 后，用乐观锁（基于 summary_updated_at）写入 `conversations.summary` 与 `summary_updated_at`；版本冲突时放弃本次写入
- [ ] 4.7 同步调用 `set_session_summary` 更新 in-memory cache（保持向后兼容）
- [ ] 4.8 整个方法 catch 所有异常，记录结构化日志，不向上抛出

## 5. Response 节点接入

- [ ] 5.1 在 `backend/app/agent/runtime/nodes.py` 的 `_llm_node` 完成 LLM 响应后（写入 conversation_message 之后），`asyncio.create_task(memory_service.maybe_summarize(...))`
- [ ] 5.2 异步任务设置 30s 超时；超时记录日志但不影响主流程
- [ ] 5.3 通过依赖注入获取 `memory_service`，不直接 `import`（保持模块边界）
- [ ] 5.4 单测覆盖：mock memory_service 验证任务被正确创建并捕获异常

## 6. ConversationSelector 注入摘要

- [ ] 6.1 修改 `backend/app/context/selectors/conversation.py`，查询时 LEFT JOIN `conversations` 表，按 `session_id` 匹配
- [ ] 6.2 当 `conversations.summary` 非空时，额外生成一个 ContextBlock（key=`conversation_summary`、source=`conversation.summary`、priority=50、compressible=True、min_tokens=64、metadata={layer: working, cache_scope: session}）
- [ ] 6.3 当 summary 为空时不产生空 block
- [ ] 6.4 单测覆盖：有 summary / 无 summary / summary 为 NULL 三种情况

## 7. 单元测试

- [ ] 7.1 新建 `backend/tests/memory/test_summarizer.py`：3 类测试（Meta / Normal / Error）覆盖 prompt 渲染、LLM 调用成功、LLM 调用失败 / 超时 / 空响应
- [ ] 7.2 新建 `backend/tests/memory/test_maybe_summarize.py`：覆盖阈值跳过、防抖跳过、feature flag 关闭、熔断开启、乐观锁冲突、正常写入 6 个场景
- [ ] 7.3 扩展 `backend/tests/context/selectors/test_conversation_selector.py`：覆盖新 conversation_summary block 的注入与空值降级
- [ ] 7.4 扩展 `backend/tests/agent/runtime/test_nodes.py`：验证 Response 节点会触发 maybe_summarize 异步任务

## 8. 集成测试与仿真

- [ ] 8.1 在 `backend/tests/agent/test_advisor_flow.py` 增加多轮场景：模拟 13 轮对话后验证 `conversations.summary` 被写入且 ConversationSelector 注入了 conversation_summary block
- [ ] 8.2 在 `backend/simulation/cases/` 新增 1 条多轮失忆回归用例：13 轮后追问前 6 轮的关键字段（金额/作物名），断言 LLM 能正确指代
- [ ] 8.3 跑 `python -m app.simulation.run --suite smoke`，确保通过

## 9. 可观测性与告警

- [ ] 9.1 验证 trace 事件 `summary_generated` / `summary_skipped` 含必要字段（farm_id、session_id、reason、tokens、duration_ms）
- [ ] 9.2 在 `backend/app/observability/metrics.py` 增加计数器：`session_summary_generated_total`、`session_summary_skipped_total{reason}`、`session_summary_failed_total`
- [ ] 9.3 在 Admin Web 的 Trace 详情页能查看 `summary_generated` 事件（验证现有 trace 渲染对新事件兼容，无需新组件）

## 10. 文档同步

- [ ] 10.1 更新 `farm-manager-design-spec/01_正式设计/03_Context工程.md` § 11 当前状态：compressors / summary 接通状态从 🚧 改为 ✅
- [ ] 10.2 更新 `farm-manager-design-spec/01_正式设计/04_Memory工程.md` § 14 当前状态：`set_session_summary` 接通状态从 🚧 改为 ✅
- [ ] 10.3 更新 `farm-manager-design-spec/Readme.md` 变更记录，加 v0.4 行（Phase A 落地）
- [ ] 10.4 在 `docs/architecture/evolution-roadmap.md` 标记 Phase 4 中 "Memory 长期 / 会话摘要自动生成" 子项进度

## 12. 长期记忆数据模型与迁移

- [ ] 12.1 新建 `backend/app/models/memory_record.py`，定义 `MemoryRecord` 模型（字段：id / farm_id / user_id / type / content / importance / status / confidence / source / superseded_by_id / created_at / confirmed_at / last_referenced_at）
- [ ] 12.2 索引：`idx_memory_records_farm_id`、`idx_memory_records_status_importance`、`idx_memory_records_last_referenced`
- [ ] 12.3 Alembic 生成迁移：`alembic revision --autogenerate -m "add memory_records table"`
- [ ] 12.4 检查迁移脚本，确认 `superseded_by_id` 外键、status 枚举约束（candidate/confirmed/superseded/archived）
- [ ] 12.5 应用到开发库，验证表结构与索引

## 13. Extractor 实现（与 Summarizer 共触发）

- [ ] 13.1 新建 `backend/app/memory/extractor.py`，定义 `async def extract_observations(llm, current_summary, recent_messages) -> list[ObservationCandidate]`
- [ ] 13.2 新建 `backend/app/memory/prompts/observations.md`，要求 LLM 输出 JSON 数组 `[{type, content, confidence}]`，5 类枚举，confidence 0-1
- [ ] 13.3 **关键**：与 `summarizer.py` 合并为一次 LLM 调用，输出 `{summary, observations}`——在 MemoryService 内做编排，不重复调 LLM
- [ ] 13.4 失败 / 超时 / JSON 不合法 → 返回空数组，不抛错
- [ ] 13.5 通过熔断器记录成功失败；超阈值后短时间内跳过抽取

## 14. MemoryService 长期记忆方法

- [ ] 14.1 `extract_observations(...)`：调用 extractor，按 confidence + type 分流入库（高置信 preference/habit/alias → candidate importance=0.5；其他 → candidate importance=0.3）
- [ ] 14.2 `confirm_observation(record_id, user_id)`：用户显式确认 → status=confirmed, importance=0.8, confirmed_at=now()
- [ ] 14.3 `record_explicit(user_id, farm_id, type, content)`：用户显式说"记一下"→ 直接 status=confirmed, importance=0.8, source=user_explicit
- [ ] 14.4 `check_implicit_repeat(record)`：写入前查同 type + content 前 50 字符 hash，若已存在 2 条 candidate，本次升级为 confirmed (importance=0.7)，旧候选 superseded
- [ ] 14.5 `archive_stale()`：定时任务（每日凌晨）扫 `importance < 0.5 AND last_referenced_at < now-90d` → status=archived
- [ ] 14.6 `supersede(old_id, new_id)`：偏好软覆盖（type != fact 时），写 superseded_by_id

## 15. Response 节点共触发改造

- [ ] 15.1 `backend/app/agent/runtime/nodes.py` Response 节点末尾异步任务从 `maybe_summarize` 改为 `maybe_summarize_and_extract`，一次调用同时产出 summary + observations
- [ ] 15.2 触发条件：messages ≥ 12 且防抖窗口外（同 D1-D2）
- [ ] 15.3 显式记忆触发词检测（"记一下"、"记住"、"以后都"）→ 优先调 `record_explicit`，不走 extractor
- [ ] 15.4 用户确认触发词检测（"对"、"是的"、"以后都这样"）→ 调 `confirm_observation` 升级最近一条候选
- [ ] 15.5 单测覆盖：共触发 / 仅 summary / 仅 observations / 显式记忆 / 用户确认 5 个场景

## 16. MemorySelector 注入长期记忆

- [ ] 16.1 修改 `backend/app/context/selectors/memory.py`，扩展查询：`SELECT * FROM memory_records WHERE farm_id=:farm_id AND status IN ('confirmed','candidate') AND importance >= 0.3 ORDER BY importance DESC, last_referenced_at DESC LIMIT 5`
- [ ] 16.2 注入为 ContextBlock（key=`memory_long_term`、source=`memory.long_term`、priority=45、compressible=True、min_tokens=64、metadata={layer:working, cache_scope:farm}）
- [ ] 16.3 注入时更新 `last_referenced_at = now()`
- [ ] 16.4 单测：confirmed 优先 / candidate 后 / 无记忆不注入 / farm_id 隔离

## 17. 长期记忆单元测试

- [ ] 17.1 新建 `backend/tests/memory/test_extractor.py`：3 类测试（Meta / Normal / Error），覆盖 prompt 渲染、LLM 输出解析、失败/超时/空响应
- [ ] 17.2 新建 `backend/tests/memory/test_long_term_flow.py`：覆盖 candidate→confirmed 显式升级 / 隐式重复升级 / 偏好软覆盖 / fact 不被覆盖 / 90 天 archive / 跨农场隔离
- [ ] 17.3 扩展 `backend/tests/context/selectors/test_memory_selector.py`：覆盖 memory_long_term block 注入

## 18. 长期记忆集成测试与仿真

- [ ] 18.1 在 `backend/tests/agent/test_advisor_flow.py` 增加多轮场景：用户说"记一下我用万元" → 后续对话验证 memory_long_term block 被注入 + Agent 用万元单位
- [ ] 18.2 在 `backend/simulation/cases/` 新增 1 条用例：用户先说"喜欢下午浇水"，3 轮后问"什么时候给我浇水建议" → 验证 Agent 回答含"下午"
- [ ] 18.3 跑 `python -m app.simulation.run --suite smoke` 通过

## 19. 长期记忆可观测性

- [ ] 19.1 trace 事件 `observations_extracted`（含 type / confidence / count）、`observations_skipped{reason}`（timeout / invalid_output / circuit_open / below_threshold / within_debounce_window）
- [ ] 19.2 metrics 计数器：`memory_observations_extracted_total{type}`、`memory_observations_confirmed_total{source}`（user_explicit / llm_repeat）、`memory_observations_archived_total`
- [ ] 19.3 Admin Web Trace 详情页可查看 observations_extracted 事件

## 20. 长期记忆文档同步

- [ ] 20.1 `farm-manager-design-spec/01_正式设计/04_Memory工程.md` § 14 当前状态：long_term 从 🚧 改为 ✅
- [ ] 20.2 `farm-manager-design-spec/Readme.md` 变更记录加 v0.9 行
- [ ] 20.3 `farm-manager-design-spec/04_相关规范/03_数据库与迁移规范.md` 表清单加 `memory_records`

## 21. 上线与验证

- [ ] 21.1 合并 PR 到 main，CI 七道门全部通过
- [ ] 21.2 部署 staging，feature flag `ai.enable_session_summary` + `ai.enable_long_term_memory` 默认 false，观察 2 小时
- [ ] 21.3 staging 开启 feature flag，跑 24 小时；trace 抽检：摘要关键字段命中率 ≥ 90%、抽取准确率（人工评分）≥ 70%
- [ ] 21.4 部署生产，feature flag 默认 false → 开启 5 个内测农户 → 观察 1 周 → 全量开启
- [ ] 21.5 上线 1 周后核查单户月增成本，确认 < ¥3（summary + observations 合计）
