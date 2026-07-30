## 1. Regression Seeds and Test Harness

- [ ] 1.1 Add a targeted backend regression fixture for the `eda446a0` class of failure: tool result exists, final response must not leak tool JSON or say “需要先调用工具”.
- [ ] 1.2 Add unit tests proving final LLM input does not contain raw `AIMessage.tool_calls` or raw `ToolMessage`.
- [ ] 1.3 Add unit tests proving final LLM invocation receives `tools=[]` and `tool_choice=none`.
- [ ] 1.4 Add unit tests for Output Guard leak detection: native `tool_calls`, content tool JSON, protocol keywords, and raw JSON object output.

## 2. Final Context Boundary

- [ ] 2.1 Create `FinalResponseRequest`, `ToolResultSummary`, `FinalResponseConstraints`, and related typed models under the Runtime boundary.
- [ ] 2.2 Implement `FinalContextBuilder` to project AgentState messages into user query, tool result summaries, safe context blocks, and trace metadata.
- [ ] 2.3 Ensure `FinalContextBuilder` drops raw `AIMessage.tool_calls` and raw `ToolMessage` while preserving tool facts needed for the final reply.
- [ ] 2.4 Add `final_context.build` trace recording with source message count, final message count, tool result count, and `dropped_tool_call_history`.

## 3. Final LLM Invocation Contract

- [ ] 3.1 Update Runtime final-response flow to call the final LLM from `FinalResponseRequest` instead of raw ReAct message history.
- [ ] 3.2 Ensure final-response flow binds no tools and passes real `tool_choice=none` into the LLM invocation layer.
- [ ] 3.3 Fix LLM invocation logging and trace input so recorded `tool_choice` always equals the real invocation parameter.
- [ ] 3.4 Keep tool-phase behavior unchanged: selected read tools still use `tool_choice=auto`, forced retries still use `tool_choice=required`.

## 4. Output Guard and Fail-Closed Behavior

- [ ] 4.1 Implement Output Guard for final responses, detecting native tool calls, content tool-call JSON, protocol keywords, and raw JSON output.
- [ ] 4.2 Add one retry path that reuses the same `FinalResponseRequest` with a stricter final-only system prompt.
- [ ] 4.3 Implement safe natural-language extraction for second leak attempts where extraction is unambiguous.
- [ ] 4.4 Implement separate fail-closed messages for “had tool results” and “no reliable tool results”; the former must not say “需要先调用工具”.
- [ ] 4.5 Record `output_guard.final_json_leak_check` trace with `passed`, `leak_type`, `action`, and `retry_count`.

## 5. Agent Audit Logging

- [ ] 5.1 Add a shared audit-log payload helper for route, tool, final_response, output_guard, and summary phases.
- [ ] 5.2 Emit single-line `app.log` audit events with stable `event`, `phase`, `boundary`, `sop`, `status`, and duration fields.
- [ ] 5.3 Ensure audit logs record parameter summaries such as `arg_keys`, not full tool argument JSON.
- [ ] 5.4 Add an audit-block formatter that renders 工单 ID, Run ID, Trace ID, 边界, SOP, 工具, 工具结果, 最终动作, 结果, and 耗时 from structured trace data.

## 6. Trace and DataFlywheel Diagnostics

- [ ] 6.1 Add final reply data-source trace values for context-only, tool-backed, and output-guard fail-closed replies.
- [ ] 6.2 Add DataFlywheel issue types for `json_leak_detected`, `tool_result_discarded_reply`, and `trace_log_inconsistent`.
- [ ] 6.3 Create issue extraction logic for final JSON leak retry failure, tool-result-discarded replies, and trace/log tool_choice mismatch.
- [ ] 6.4 Add tests proving bad cases include request_id, session_id, user input, final reply, tool summary, final context summary, and guard diagnosis.

## 7. TraceMonitor and Debugger UI

- [ ] 7.1 Update TraceMonitor timeline to display `final_context.build` and `output_guard.final_json_leak_check` nodes.
- [ ] 7.2 Update node drawer to show `dropped_tool_call_history`, tool result summaries, leak type, action, and retry count.
- [ ] 7.3 Add “复制审计追踪” action for a request or final-response phase.
- [ ] 7.4 Ensure old traces with missing final-context or output-guard fields render “未记录” without crashing.
- [ ] 7.5 Update `trace-chain-debugger` output to optionally render the same audit tracking block.

## 8. Verification and Documentation Sync

- [ ] 8.1 Run focused backend tests for Runtime final context, LLM invocation logging, Output Guard, reflection, and DataFlywheel issue extraction.
- [ ] 8.2 Run focused frontend tests for TraceMonitor timeline, drawer, and copy audit block behavior.
- [ ] 8.3 Run `ruff check` and project complexity budget checks for touched backend files.
- [ ] 8.4 Update `docs/farm-manager-design-spec/01_正式设计/15_Agent运行协议与防泄漏设计.md` and `16_Agent日志与诊断设计.md` if implementation details differ from the design.
- [ ] 8.5 Add final verification notes with remaining risks and rollback guidance.
