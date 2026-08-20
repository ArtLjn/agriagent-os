## 1. 契约与数据模型

- [x] 1.1 在 `v2/agent/core/` 定义 `ConversationSnapshot`、`ContextBlock`、`ContextBundle`、`MemoryObservation` 和 source/status 枚举，补充序列化与租户字段测试
- [x] 1.2 在 `v2/agent/infra/chat_store.py` 增加 `conversationStates` 读写接口、租户过滤、revision CAS 和唯一索引初始化
- [x] 1.3 增加 Conversation state 的配置项、摘要 TTL、最近 Turn 数、预算 reserve 和 feature flags，并补充 `config.example.yaml`
- [x] 1.4 定义 Mongo/Redis/Trace 字段迁移和兼容映射，确保旧 `conversation_id`、`turn_id`、`trace_id` 能继续回放
- [x] 1.5 在设计和接口测试中明确 Session metadata、Short Memory、Long-term Memory 的存储位置、写入时机、读取入口和 Context Block 映射

## 2. Memory Service 与短时记忆

- [x] 2.1 把 `v2/agent/core/memory.py` 收敛为 Memory Service/adapter 入口，禁止 Runtime 直接依赖本地文件路径
- [ ] 2.2 实现基于完整 Turn 的最近窗口 projection，移除只按 `MAX_SHORT_TERM_MESSAGES` 截断的生产默认策略
- [ ] 2.3 将会话摘要从伪 assistant 消息迁移为独立 `conversationStates.summary`，修复摘要加载、source range、revision 和 content hash
- [ ] 2.4 为摘要生成增加 CAS、幂等 key、失败状态、重试和并发 Worker 测试
- [ ] 2.5 实现 pending action、临时任务状态和 reset generation 的读取与过期清理
- [x] 2.6 保留 Memory observation 接口和空长期记忆实现，禁止未确认事实写入长期 Memory
- [x] 2.7 实现 `get_session_view()` 与 `search()` 两个分离接口，分别返回 Short Memory projection 和 scoped Long-term Memory hits
- [x] 2.8 增加 Memory injection policy：Short Memory 默认注入，Long-term Memory 仅由 ContextPolicy/Skill dependency 按需检索和注入

## 3. ContextBuilder 与预算

- [x] 3.1 在 `v2/agent/core/context.py` 生成结构化 ContextBundle/ContextBlock，并保留静态 system prompt 的 cache prefix
- [x] 3.2 为 system、task、hot context、pending action、summary、recent turns、memory hits、tool schema 和 observation 定义 selector/priority
- [x] 3.3 升级 tokenizer 预算，计入 messages、Tool Schema、工具结果、response reserve 和 safety margin，并记录 approximate/actual 模式
- [x] 3.4 实现 required/priority/compressible/min_tokens 的保留、压缩、丢弃和 budget error 决策
- [ ] 3.5 将 `_try_compress_context` 改为基于 ContextBundle 和 summary revision 的同步/异步流程，避免与 Turn 持久化发生覆盖竞争
- [x] 3.6 为上下文裁剪、摘要回注、过长工具结果和 required 超预算增加 focused regression tests

## 4. Runtime、Tool Schema 与持久化边界

- [x] 4.1 在 `react.py` 中通过 application/Memory adapter 获取 snapshot，移除 Runtime 对具体 JSON/Mongo 存储的直接调用
- [ ] 4.3 为 Skill metadata 增加 Context dependency 和 candidate tool schema 选择入口，保留全量暴露兼容开关
- [ ] 4.4 将已完成 Turn 的用户消息、assistant 最终消息、observation 和 Memory observation 以幂等方式提交
- [ ] 4.5 明确错误、超时、取消、审批过期和 commit 后收尾失败时的 Session Memory 写入边界

## 5. API、reset 与恢复

- [ ] 5.1 更新 `/api/v2/chat`、conversation detail 和 Turn state，使 response 暴露 conversation revision、reset generation 和 source status
- [x] 5.2 更新 `/api/v2/reset`，实现 active Context/pending action/summary 清理和 generation 递增，保留默认可见历史
- [ ] 5.3 为 Worker 重启、SSE `after_seq` 重连和幂等 request 验证同一 Turn 不重复执行、不重复写消息
- [ ] 5.4 增加 Mongo 不可用、Redis 不可用、legacy JSON fallback 和 source divergence 的结构化错误/降级行为

## 6. Trace 与运行指标

- [x] 6.1 扩展 `trace_context_build` 记录 Block、预算、summary/memory revision、tool schema mode 和 source status
- [ ] 6.2 增加 summary compaction、memory read/observe、context source divergence 和 budget error Trace 节点/属性
- [ ] 6.3 扩展 Trace summary 聚合 Context token、reserve、压缩/丢弃计数、摘要次数、fallback 次数和持久化状态
- [ ] 6.4 增加敏感字段脱敏、payload 上限和不记录隐藏思维链/凭证的回归检查

## 7. 迁移与灰度

- [ ] 7.1 实现 Mongo snapshot 与 legacy JSON 的 shadow-read 对比，并记录 divergence 指标
- [ ] 7.2 灰度启用 `conversation_state_v2` 和 `summary_cas`，验证重启、多 Worker、摘要冲突和历史一致性
- [ ] 7.3 灰度启用 Mongo 优先 Context 读取，保留带 source status 的 JSON fallback，达到 parity 后关闭生产 fallback
- [ ] 7.4 灰度启用 candidate tool schema，基于回放集比较工具召回、误调用和 token 成本
- [ ] 7.5 完成旧本地 JSON 数据迁移/归档策略，确认可回滚且不删除 Mongo 用户可见历史

## 8. 验收与门禁

- [ ] 8.1 增加多轮追问、工具结果摘要、摘要回注、pending action、reset 和跨租户隔离测试
- [x] 8.2 增加 token budget、Tool Schema budget、response reserve、required overflow 和 drop reason 测试
- [ ] 8.3 增加真实 Redis/Mongo/Worker/SSE replay smoke，验证历史事实源与 Agent Context 一致
- [ ] 8.4 运行 v2 Agent focused tests、Ruff、格式化、复杂度和层依赖检查
- [x] 8.5 更新 `v2/docs/spec/` 实施状态、迁移开关、已知限制和验收证据
