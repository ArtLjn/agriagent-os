## ADDED Requirements

### Requirement: Trace 查询 API
系统 SHALL 提供 `GET /admin/traces` 接口，支持按 request_id、session_id、farm_id 筛选 trace 记录，按 created_at 倒序返回。

#### Scenario: 按 request_id 查询
- **WHEN** 调用 `GET /admin/traces?request_id=abc-123`
- **THEN** 返回该请求的所有 trace 节点（LLM、Skill、Prompt），按 start_time 正序

#### Scenario: 按 session_id 查询最近请求
- **WHEN** 调用 `GET /admin/traces?session_id=s1&limit=50`
- **THEN** 返回该 session 最近的 50 条 trace 记录

#### Scenario: 无权限控制（当前单用户）
- **WHEN** 调用 `/admin/traces` 不带认证
- **THEN** 正常返回数据（当前 farm_id=1 硬编码，后续 change 加认证）

### Requirement: Timeline Gantt 数据 API
系统 SHALL 提供 `GET /admin/traces/{request_id}/timeline` 接口，返回按 round 分组的 Gantt 图数据。

#### Scenario: 正常返回 timeline
- **WHEN** 调用 `GET /admin/traces/abc-123/timeline`
- **THEN** 返回格式：
```json
{
  "request_id": "abc-123",
  "total_duration_ms": 2100,
  "rounds": [
    {
      "round_index": 0,
      "total_ms": 1200,
      "nodes": [
        {"node_type": "prompt_render", "node_name": "system_prompt", "start_ms": 0, "duration_ms": 5, "status": "success"},
        {"node_type": "llm_call", "node_name": "qwen3.6-flash", "start_ms": 5, "duration_ms": 800, "token_usage": {...}},
        {"node_type": "skill_call", "node_name": "get_weather_forecast", "start_ms": 805, "duration_ms": 400}
      ]
    }
  ]
}
```

#### Scenario: request_id 不存在
- **WHEN** 调用 `GET /admin/traces/nonexistent/timeline`
- **THEN** 返回 404

### Requirement: Trace 节点详情 API
系统 SHALL 提供 `GET /admin/traces/{request_id}/nodes/{node_id}` 接口，返回单个节点的完整 input/output 数据。

#### Scenario: 查看节点详情
- **WHEN** 调用 `GET /admin/traces/abc-123/nodes/42`
- **THEN** 返回完整 input_data 和 output_data（不截断）

### Requirement: Trace 清理 API
系统 SHALL 提供 `DELETE /admin/traces` 接口，按日期清理历史 trace。

#### Scenario: 清理 7 天前的数据
- **WHEN** 调用 `DELETE /admin/traces?before=2026-05-19`
- **THEN** 删除 created_at < 2026-05-19 的所有 trace_records
