# Agent Context Task State 最小持久化

## 背景

Sectioned Context 已提供 Task 分区，外部 RAG 已以只读方式进入 Evidence 分区。本轮补齐最小 Task Context 持久化能力，让多轮任务在同一 session 内可恢复，并能作为 `active_task_state` block 注入 Task 分区。

## 范围

- 新增 `agent_task_states` 表，只保存每个 `farm_id` / `user_id` / `session_id` 最近一个 `active` 或 `waiting_user` 任务状态。
- 新增 `AgentTaskStateStore`，支持 upsert active task、读取 active/waiting_user task、标记 completed/cancelled。
- 新增 `TaskStateSelector`，默认随 ContextPolicy base selectors 读取一次当前 session 任务状态。
- `active_task_state` 进入 ContextRenderer 的 Task 分区，并加入 ContextBuilder allowlist。
- JSON 字段使用 SQLAlchemy JSON 类型，prompt 内容只包含目标、已知实体、观察信息、缺失信息、下一步动作和状态。

## 表结构

核心字段：

- `task_id`：业务任务 ID，唯一。
- `farm_id` / `user_id` / `session_id`：多租户与会话隔离边界。
- `task_type`：任务类型，例如 plan_draft、diagnosis_followup。
- `goal`：当前任务目标。
- `entities_json`：已知实体。
- `observations_json`：已观察信息。
- `missing_information_json`：缺失信息。
- `next_action`：建议下一步动作。
- `status`：`active`、`waiting_user`、`completed`、`cancelled`。
- `expires_at`：过期后 selector 和 store 读取会忽略。

## 生命周期

第一版写入入口保持为 service API：调用方通过 `AgentTaskStateStore.upsert_active_task(...)` 保存或更新当前 session 最近任务。恢复时 `TaskStateSelector` 只查询同 `farm_id`、`user_id`、`session_id` 下最近一个未过期 `active` 或 `waiting_user` 状态。任务结束后由调用方显式标记 `completed` 或 `cancelled`。

## 明确不做

- 不做多任务调度。
- 不做复杂 planner。
- 不做自动长期记忆。
- 不做 RAG ingest 或 memory sync。
- 不接 Mongo trace 写入。
- 不重写 pending_actions 主确认链路。
