## ADDED Requirements

### Requirement: Trace Monitor API 管理员访问
Trace Monitor 使用的 `/admin/traces*` 接口 SHALL 仅允许管理员访问。

#### Scenario: 管理员查看 Trace 列表
- **WHEN** 管理员在 Trace Monitor 页面请求 `GET /admin/traces`
- **THEN** 系统 SHALL 返回符合筛选条件的 trace 列表

#### Scenario: 管理员查看 Trace 节点详情
- **WHEN** 管理员请求 `GET /admin/traces/{request_id}/nodes/{node_id}`
- **THEN** 系统 SHALL 返回该节点的 input_data、output_data、token_usage 和状态信息

#### Scenario: 未授权访问 Trace 内容
- **WHEN** 匿名用户或普通用户请求 `/admin/traces*` 接口
- **THEN** 系统 SHALL 返回 401 或 403，且不得返回 trace 输入输出内容

#### Scenario: 管理员清理 Trace
- **WHEN** 管理员请求 `DELETE /admin/traces?before={date}`
- **THEN** 系统 SHALL 按日期清理历史 trace 并返回删除数量
