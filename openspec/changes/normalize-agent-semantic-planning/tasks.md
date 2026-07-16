## 1. Regression First

- [x] 1.1 Add router/classifier regression for "李海这个月干了15天压瓜" expecting `create_operation_work_order` or clarification, and forbidding no-tool success text.
- [x] 1.2 Add parameter extraction regression for "今天李海去6号棚压蔓工资100一天" expecting worker "李海", unit "6号棚", operation "压蔓", and unit price 100.
- [x] 1.3 Add multi-step regression for "新来一个工人李丽工资100一天，今天去6号棚收水稻" expecting pending plan steps `manage_workers` then `create_operation_work_order`.
- [x] 1.4 Add reflection regression for selected-tools-empty final replies that claim "已记录" on write-like user input.
- [x] 1.5 Add repair-pack/regression-draft regression for no-tool success claims producing actionable issue assertions.

## 2. Semantic Gate And Routing

- [x] 2.1 Extend router models or metadata to carry semantic planning evidence and missing-field reasons without changing external API responses.
- [x] 2.2 Implement lightweight farm labor semantic detection for worker + operation + quantity/pay hints.
- [x] 2.3 Fix worker, planting unit, operation type, quantity, and unit price extraction boundaries for farm labor sentences.
- [x] 2.4 Route implicit farm labor work to `create_operation_work_order` or produce a structured clarification when key fields are missing.
- [x] 2.5 Preserve existing query, greeting, and chitchat behavior with negative regression cases.

## 3. Pending Action And Pending Plan

- [x] 3.1 Ensure deterministic single-operation labor work creates a pending action for `create_operation_work_order`.
- [x] 3.2 Ensure deterministic worker-plus-work-order inputs create a pending plan with dependency from worker creation to work order creation.
- [x] 3.3 Block pending action or pending plan creation when write step params are empty or required fields are not inferable.
- [x] 3.4 Include inferred wage/default wage context in confirmation text when worker default wage is used.

## 4. Reflection Guard

- [x] 4.1 Add pre-final no-tool write success guard for replies containing "已记录", "已创建", "已保存", "已执行", or equivalent write-success claims.
- [x] 4.2 Emit `reflection_check` trace evidence with issue code `no_tool_write_success_claim` when the guard blocks a reply.
- [x] 4.3 Return safe clarification or fail-closed text instead of claiming a write happened.
- [x] 4.4 Verify the new guard does not block greetings, ordinary explanations, or safe read replies.

## 5. Data Flywheel And Evaluation

- [x] 5.1 Update issue detection or repair-pack generation so no-tool write success claims map to actionable assertions.
- [x] 5.2 Add skill regression cases for semantic planning, selection, pending creation, and final-response guard outcomes.
- [x] 5.3 Ensure evaluation reports distinguish semantic planning, selection, pending creation, execution, and response-quality failures.

## 6. Documentation And Validation

- [x] 6.1 Update Agent design docs if implementation differs from `docs/farm-manager-design-spec/01_正式设计/13_Agent范式规范化设计.md`.
- [x] 6.2 Run focused backend tests for router, reflection, pending plan, data flywheel repair pack, and skill regression evaluation.
- [x] 6.3 Run OpenSpec validation for `normalize-agent-semantic-planning`.
- [x] 6.4 Summarize residual risks and any intentionally unsupported multi-agent scenarios.

Residual risks:

- The main chat path remains a single master Agent. Multi-agent coordination is intentionally not introduced for normal routing, write confirmation, or final replies.
- Regex remains only as a lightweight Rule Gate and high-frequency fallback. It is not the long-term semantic parser; future broad semantic coverage should move into Structured Planner + Domain Validator.
- Unsupported for now: destructive multi-step plans, ambiguous historical record updates without unique target resolution, and write flows requiring external real-time data without a read-tool evidence step.
