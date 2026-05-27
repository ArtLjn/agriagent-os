## ADDED Requirements

### Requirement: Trace 列表查询页
系统 SHALL 提供 `/dev/traces` 页面，展示 trace 记录列表，支持按 request_id、session_id、farm_id 筛选，按 created_at 倒序分页。

#### Scenario: 默认加载最近 trace
- **WHEN** 用户进入 `/dev/traces` 页面
- **THEN** 展示最近 20 条 trace 记录，每条显示 request_id（前 8 位）、farm_id、节点数、总耗时、创建时间

#### Scenario: 按 request_id 筛选
- **WHEN** 用户在搜索框输入 request_id
- **THEN** 列表过滤为匹配的 trace 记录

#### Scenario: 点击 trace 进入详情
- **WHEN** 用户点击某条 trace 记录
- **THEN** 展开该 request_id 的 Gantt 时间线视图

### Requirement: Gantt 时间线可视化
系统 SHALL 为每个 request_id 展示 Gantt 时间线图，按 round 分组，每个节点显示为水平条形图，长度代表耗时。

#### Scenario: 展示多轮 trace
- **WHEN** 查看 `/admin/traces/{request_id}/timeline` 返回多轮数据
- **THEN** 按 round_index 分行展示，每行包含该轮的 prompt_render、llm_call、skill_call 节点，条形图水平排列，位置对应 start_ms

#### Scenario: 节点颜色编码
- **WHEN** Gantt 图渲染节点
- **THEN** prompt_render 为蓝色、llm_call 为紫色、skill_call 为绿色、error 状态为红色

#### Scenario: 鼠标悬停显示摘要
- **WHEN** 鼠标悬停在某个节点条上
- **THEN** Tooltip 显示 node_name、duration_ms、status

### Requirement: 节点详情查看
系统 SHALL 支持点击 Gantt 图中的节点查看完整 input/output 数据。

#### Scenario: 点击节点打开详情
- **WHEN** 用户点击某个节点条
- **THEN** 右侧 Drawer 面板打开，调用 `GET /admin/traces/{request_id}/nodes/{node_id}` 展示完整 input_data 和 output_data（JSON 格式化）

#### Scenario: Token 详情展示
- **WHEN** 节点为 llm_call 类型且包含 token_usage
- **THEN** Drawer 中额外展示 prompt_tokens、completion_tokens、total_tokens 统计

### Requirement: Trace 清理操作
系统 SHALL 在 Trace Monitor 页面提供清理历史 trace 的操作。

#### Scenario: 按日期清理
- **WHEN** 用户选择日期并确认清理
- **THEN** 调用 `DELETE /admin/traces?before={date}`，清理后刷新列表
