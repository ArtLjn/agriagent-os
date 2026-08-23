# Agent 历史会话查询工程计划 - 待办清单

> 生成时间：2026-08-23
> 来源文档：2026-08-23-agent-conversation-history-query-engineering-plan.md

## Phase 0：契约冻结与兼容映射

- [x] 固化历史消息字段契约
  - [x] 明确 `message_id`、`turn_id`、`trace_id`、`role`、`content`、`created_at`、`message_kind`、`meta`
  - [x] 固化 `message_kind` 规范值及旧值兼容映射
  - [x] 固化 `meta` 脱敏白名单
  - [x] 固化 `events_status` 和来源状态枚举
- [x] 明确旧 `GET /conversations/{id}` 的兼容字段语义
- [x] 增加 API 和 TypeScript 基础契约测试
- [x] 补充旧消息缺少 `trace_id`、`message_kind`、`meta` 的兼容测试

## Phase 1：规范化 Message History

- [x] 增加 `GET /conversations/{id}/messages`
- [x] 实现无 cursor 首屏加载最新消息
- [x] 实现 opaque cursor 加载更早历史
- [x] 使用 `(created_at, message_id)` 作为稳定排序键
- [x] 增加 snapshot revision 和 cursor 失效校验
- [x] 返回 `message_count`、`page_count`、`has_more`、`next_cursor`
- [x] 管理端保留消息 ID、Turn/Trace 关联和 `meta`
- [x] Playground 向上滚动时自动加载更早历史并保持滚动位置
- [x] cursor 冲突时前端重新加载最新首屏
- [ ] 统一历史消息时间字段格式
- [ ] 增加新增消息并发下的重复/漏读测试
- [ ] 增加 Mongo、Redis 不可用时的完整来源状态测试

## Phase 2：Turn 汇总与执行详情

- [x] 增加会话范围 Turn 列表接口
  - [x] 支持 `limit` 和 opaque cursor
  - [x] 返回 `status`、`stop_reason`、`step_count`
  - [x] 返回 prompt/answer 的 `message_ids`
  - [x] 返回 `events_status`
- [x] 增加 Turn detail 聚合接口
  - [x] 关联 Trace summary
  - [x] 关联 Trace timeline
  - [x] 返回审批、业务提交、错误和终态摘要
  - [x] 返回 `evidence` 来源状态
- [x] 增加 Turn/Trace 权限投影测试
- [x] 确保不返回原始隐藏思维链

## Phase 3：Playground 历史执行恢复

- [x] 为历史消息增加 Turn/Trace 详情入口
- [x] 支持按需展开执行时间线
- [x] SSE 完成后根据 `conversation_revision` 刷新最新页
- [x] 支持 SSE 使用 `event_id`、`seq` 断线续读
- [x] 区分普通用户和管理员调试事件投影
- [x] Trace/Redis 不可用时展示明确的证据不可用状态
- [ ] 增加 Playground 历史恢复和滚动分页测试
- [x] 增加 SSE replay 回归测试

## Phase 4：兼容收敛

- [x] 新调用方统一切换到 `/messages`、`/turns` 和 `/turns/{turn_id}`
- [x] 标记旧响应中的 `items`、`count` 为兼容字段
- [ ] 评估收窄旧 `GET /conversations/{id}` 为会话元信息接口
- [x] 同步 API spec 和兼容矩阵
- [ ] 完成文档新鲜度检查

## 验收与质量门禁

- [x] 后端分页、cursor、revision focused tests
- [x] 前端 API cursor 测试
- [x] Ruff check/format
- [x] TypeScript 类型检查
- [x] 架构依赖检查
- [x] 完成 Turn/Trace 接口后补齐对应测试
- [x] 运行完整相关后端测试集
- [x] 运行完整相关前端测试集
- [ ] 完成真实 Mongo、Redis、SSE 联调验收

## 待评审决策

- [ ] 确认是否长期保留旧 `/conversations/{id}` 兼容响应
- [ ] 确认 `message_count` 是否要求实时精确
- [ ] 确认 Turn detail 是否直接复用 Trace timeline
- [ ] 确认 `tool_summary` 是否进入历史消息 `meta`
- [ ] 确认管理员调试 payload 上限和可见字段白名单
