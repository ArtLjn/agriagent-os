## ADDED Requirements

### Requirement: TraceMonitor 展示 Final 防泄漏诊断
TraceMonitor SHALL 在 trace timeline 和节点详情中展示 final_context、output_guard、final_reply_data_source 等节点，并突出 final 阶段工具隔离状态。

#### Scenario: 展示 final context 节点
- **WHEN** timeline 数据包含 `final_context.build`
- **THEN** TraceMonitor 显示该节点
- **AND** 节点详情展示 `dropped_tool_call_history`
- **AND** 节点详情展示工具结果摘要

#### Scenario: 展示 output guard 节点
- **WHEN** timeline 数据包含 `output_guard.final_json_leak_check`
- **THEN** TraceMonitor 显示泄漏检测结果
- **AND** 若 `passed=false`，使用异常或阻断状态突出显示

### Requirement: TraceMonitor 支持复制审计追踪块
TraceMonitor SHALL 支持将单个请求或单个阶段复制为审计追踪块，内容包含工单 ID、Run ID、Trace ID、边界、SOP、工具、最终动作、结果和耗时。

#### Scenario: 复制 final_response 审计块
- **WHEN** 管理员在 final_response 详情中点击复制审计追踪
- **THEN** 剪贴板内容包含 `工单 ID`
- **AND** 包含 `Trace ID`
- **AND** 包含 `边界`
- **AND** 包含 `最终动作`

#### Scenario: 旧 trace 缺少字段
- **WHEN** trace 缺少 final_context 或 output_guard 字段
- **THEN** TraceMonitor 显示“未记录”
- **AND** 页面不得崩溃

### Requirement: TraceMonitor 标识 trace 与 app.log 不一致风险
如果 trace 中的 final 阶段 tool_choice 与日志或诊断数据中的真实 invocation 参数不一致，TraceMonitor SHALL 展示不一致风险提示。

#### Scenario: tool_choice 不一致提示
- **WHEN** trace 展示 `tool_choice=none`
- **AND** 诊断数据标记真实 invocation 为 `auto`
- **THEN** TraceMonitor 显示 `trace_log_inconsistent` 风险提示
