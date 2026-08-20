---
spec_id: 2026-08-18-agent-trace-observability-and-recall-tasks
last_updated: 2026-08-18
status: completed
---

# v2 Agent Trace 实施任务

设计基线：[2026-08-18-agent-trace-observability-and-recall-design.md](./2026-08-18-agent-trace-observability-and-recall-design.md)

- [x] 建立实现任务清单，锁定 `trace_id`、`turn_id`、`event_id`、`seq` 和兼容 `request_id` 边界
- [x] 补充 MongoDB 四集合、字段职责、唯一约束和跨集合回链设计
- [x] 实现 Trace/SSE 统一事件 envelope、稳定事件 ID、单调序号和唯一 `done`
- [x] 实现 Trace `nodes`、`events`、`timeline` 查询接口及结构化证据状态
- [x] 实现四集合显式配置、幂等索引和 `conversationMessages` 的 Trace 回链字段
- [x] 将统一 SSE envelope 持久化到 `traceEvents`，并实现丢失状态与幂等写入
- [x] 扩展 `trace-chain-debugger` 的 v2 单轮和整段会话召回
- [x] 补充 SSE、Trace API、timeline 和 Skill 召回的 focused regression tests
- [x] 运行 lint、复杂度检查和可用环境下的真实 SSE/Trace 验证
- [x] 完成主线程审查，记录兼容性、未实现接口和剩余风险

## 验证记录

- `ruff check`：目标 Trace、SSE、Worker 和测试文件通过。
- `pytest`：Trace collector、Trace store、运行时 streaming、Skill 召回共 `47 passed`。
- `bash scripts/check-layer-deps.sh`：通过；复杂度预算通过，保留归档文件、锁文件和历史大文件警告。
- `bash v2/scripts/test_trace_sse_rounds.sh`：真实本地环境完成 `3/3` 轮；每轮 SSE、唯一 `done`、连续 `seq`、同请求重放、Turn completed、`traceEvents` 和 `conversationMessages` 回链均通过。

## 剩余风险

- 兼容路径 `/api/v2/traces/{request_id}` 和 `/summary` 仍保留，参数语义按 `trace_id` 解释；新调用方应优先使用 `/nodes`、`/events`、`/timeline`。
- 复杂度检查仍有仓库历史归档文件、双锁文件和前端大文件警告，本次未扩大范围处理。
- 修复前写入的旧 `traceEvents` 文档可能缺少 `user_id`、`farm_uid`，需要按上线迁移策略回填或自然过期；新写入事件已包含这两个租户隔离字段。
- 生产环境仍需补充审批、失败、取消、超时和断线重连场景的真实验收。

执行规则：任务完成且对应测试或检查通过后才勾选；只完成静态代码检查不能替代真实 Redis/Mongo/SSE 验收。
