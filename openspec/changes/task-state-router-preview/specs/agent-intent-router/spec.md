## MODIFIED Requirements

### Requirement: Router r1 输入需感知 task_state

router r1 在调用前必须查询当前会话的 active task_state。当 `evaluate_task_state_relevance.should_inject=True` 时,r1 接收的路由输入必须为 `task_state_routing_input(user_input, active_task)` 拼接形式(含"当前任务/缺失信息/已知实体"前缀);should_inject=False 时路由输入与用户原始输入完全一致。

#### Scenario: 承接场景注入前缀

- **WHEN** 会话存在 active task(`task_type=crop_cycle_setup, missing_information=['面积']`)且用户输入 "20 亩"
- **THEN** router r1 接收的输入包含"当前任务:茬口创建 缺失信息:面积 用户输入:20 亩"格式前缀

#### Scenario: 闲聊场景不污染

- **WHEN** 会话存在 active task 但用户输入 "你好" 或 "明天苏州天气"
- **THEN** router r1 接收的输入为原始 "你好"/"明天苏州天气",不含任务态前缀

#### Scenario: 无 active task 时零开销

- **WHEN** 会话无 active task(`agent_task_states` 表无记录或已过期)
- **THEN** router r1 直接接收原始用户输入,不调 relevance 判定
