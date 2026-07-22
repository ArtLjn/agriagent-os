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

第一轮已落地的读路径保持不变：恢复时 `TaskStateSelector` 只查询同 `farm_id`、`user_id`、`session_id` 下最近一个未过期 `active` 或 `waiting_user` 状态，并作为 `active_task_state` 注入 Task 分区。

本轮补齐最小写入闭环：

- 非流式 chat 在生成回复、读取 pending action/plan 元数据之后，调用 `app.application.chat.task_state_updater.update_task_state_after_turn(...)`。
- 流式 chat 在后台保存回复后，用同一个 updater 更新 TaskState；后台 payload 会带上 `pending_action`、`pending_plan` 和 pending 决策是否已处理。
- updater 只接收本轮用户输入、助手最终回复、farm/user/session 和 pending 状态，不直接调用 LLM，不访问 Runtime 内部节点。
- 如果本轮仍有 pending action 或 pending plan，或本轮已经处理 pending 确认/取消，updater 直接跳过，避免 TaskState 覆盖确认链路。
- 如果没有 session_id、user_id，或只是问候、普通查账/记账确认流程，updater 不写 TaskState。
- 如果用户提出计划、诊断、方案等任务，且助手明确追问缺失信息，updater 创建或更新当前 session 最近一个 `waiting_user` task。
- 如果已有 active/waiting_user task，用户下一轮补充信息时 updater 更新同一条 task，合并 observations/entities，并在缺失信息补齐后转为 `active`。
- 如果用户取消，标记 `cancelled`；如果助手明确表示方案/诊断建议已完成，标记 `completed`。`completed`、`cancelled` 和过期任务不会被 selector 注入。

第一版规则解析字段只覆盖：

- `goal`：使用触发任务时的用户原文。
- `entities`：保守抽取作物和棚室等轻量实体。
- `observations`：记录用户已经提供或补充的信息摘要。
- `missing_information`：从“还需要补充/缺少/请告诉我”等明确追问中抽取。
- `next_action`：缺信息时等待用户补充；信息补齐后继续处理当前任务。
- `status`：仅在 `active`、`waiting_user`、`completed`、`cancelled` 间转换。

## 明确不做

- 不做多任务调度。
- 不做复杂 planner。
- 不做自动长期记忆。
- 不做 RAG ingest 或 memory sync。
- 不接 Mongo trace 写入。
- 不重写 pending_actions 主确认链路。
- 不新增数据库表或配置项。
- 不把普通账务查询/记账确认流程提升为 TaskState。
- 不在信号不足时猜测长期目标。
