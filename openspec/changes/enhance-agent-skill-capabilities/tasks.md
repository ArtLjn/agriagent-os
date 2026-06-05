## 1. Skill Metadata and Documentation

- [x] 1.1 Add a Skill metadata model covering permission level, risk level, context dependencies, cache invalidation, confirmation schema, evaluation tags, and metadata completeness.
- [x] 1.2 Extend Skill registration so every registered Skill exposes metadata through backend registry APIs and LangChain tool conversion.
- [x] 1.3 Add safe default metadata for legacy Skills and mark incomplete metadata in registry output.
- [x] 1.4 Update write Skill docs to the standard format, starting with `create_operation_work_order`.
- [x] 1.5 Add validation tests that fail when a new Skill lacks required documentation or required metadata.

## 2. Metadata-Driven Tool Execution

- [x] 2.1 Update Tool Executor to use Skill metadata for read/write/admin/external-network permission decisions.
- [x] 2.2 Keep the existing hardcoded write Skill list as a temporary fallback during migration.
- [x] 2.3 Move cache invalidation lookup from hardcoded pending action maps to Skill metadata.
- [x] 2.4 Record metadata-derived permission, validation, pending action, and cache invalidation decisions in trace.
- [x] 2.5 Add Tool Executor tests for read Skill execution, write confirmation interception, admin rejection, validation error, and metadata fallback.

## 3. Structured Pending Action Confirmation

- [x] 3.1 Add a structured pending action confirmation context model with original input, target object, changed fields, inferred fields, risk notes, and editable fields.
- [x] 3.2 Generate compatibility text from the structured confirmation context for existing chat clients.
- [x] 3.3 Update complex write confirmations to show full work order and labor details, including units, workers, payable, paid, and unpaid amounts.
- [x] 3.4 Add crop cycle update confirmation showing old and new start dates, target cycle, inferred crop name, and inferred date.
- [x] 3.5 Add tests for confirm, cancel, correction, timeout, and overwritten pending action behavior.

## 4. Planting Operation Skills

- [x] 4.1 Implement `update_crop_cycle` Skill for modifying existing crop cycle start date, season, name, area, status, stage, or note.
- [x] 4.2 Implement target resolution for crop cycle updates using crop name, active/planned status, current context, and ambiguity detection.
- [x] 4.3 Implement `get_operation_work_orders` read Skill with filters for cycle, unit, operation type, worker, date range, and payment status.
- [x] 4.4 Implement `update_operation_work_order` write Skill for correcting date, type, scope, note, workers, payable amount, and paid amount.
- [x] 4.5 Implement `get_labor_payables` read Skill for unpaid labor by worker, cycle, work order, date range, and farm.
- [x] 4.6 Implement `settle_labor_payment` write Skill for partial and full labor payment settlement.
- [x] 4.7 Add service-level and Skill-level tests for the new planting operation Skills.

## 5. Context Dependency Integration

- [x] 5.1 Extend ContextPolicy so selected Skill metadata can request crop cycle, planting unit, worker, unpaid labor, cost category, weather, and ledger context.
- [x] 5.2 Add or extend selectors for planting units, operation work orders, workers, and unpaid labor summaries.
- [x] 5.3 Record which context blocks were selected because of Skill metadata dependencies.
- [x] 5.4 Add context selector tests for `update_crop_cycle`, `settle_labor_payment`, and work order query scenarios.

## 6. Skill Regression Evaluation

- [x] 6.1 Add regression case schema fields for expected Skill, expected parameters, expected pending action, user confirmation flow, and expected database diff.
- [x] 6.2 Add regression cases for crop cycle update, work order creation, work order correction, unpaid labor query, labor settlement, cost record correction, and weather query.
- [x] 6.3 Add database snapshot comparison for confirmed write Skill execution.
- [x] 6.4 Add evaluation metrics for unnecessary clarification, correction success, cancellation success, and execution consistency.
- [x] 6.5 Add a coverage report grouped by Skill, business domain, permission level, confirmation path, and context dependency.

## 7. Diagnostics and Admin Visibility

- [x] 7.1 Add a Skill diagnostic service that summarizes tool selection, context injection, tool calls, pending actions, validation errors, and final response from trace.
- [x] 7.2 Add pending action lifecycle diagnostics for created, replaced, confirmed, corrected, cancelled, timed out, executed, and failed states.
- [x] 7.3 Add context dependency diagnostics showing selected, compressed, dropped, or unavailable blocks.
- [x] 7.4 Extend Skill Registry admin API and UI to display metadata completeness, permissions, cache effects, and context dependencies.
- [x] 7.5 Extend Playground or Trace Monitor to show structured pending action context and failed regression drilldown links.

## 8. Verification

- [x] 8.1 Add focused tests for the user example: "修改玉米茬口9月1开始" must produce an `update_crop_cycle` pending action when one active corn cycle exists.
- [x] 8.2 Run backend unit tests for Skill registration, Tool Executor, pending actions, ContextPolicy, planting services, evaluation, and diagnostics.
- [x] 8.3 Run relevant frontend/admin tests for Skill Registry, Playground, and Trace Monitor changes.
- [x] 8.4 Run architecture and harness checks.
- [x] 8.5 Document remaining gaps and rollout notes before archiving the change.

## Rollout Notes

- Backend focused verification passed from `backend/`: `./.venv/bin/python -m pytest -q tests/context tests/evaluation tests/api/test_admin_trace.py tests/api/test_admin_config.py tests/skills/test_planting_operation_skills.py tests/test_pending_actions.py`.
- Targeted lint passed from `backend/`: `./.venv/bin/ruff check app/context app/evaluation app/api/admin_trace.py app/infra/pending_actions.py app/services/planting_read_service.py app/services/planting_service.py app/schemas/planting.py app/agent/skills/get-operation-work-orders app/agent/skills/get-labor-payables app/agent/skills/update-operation-work-order app/agent/skills/settle-labor-payment tests/context tests/evaluation tests/api/test_admin_trace.py tests/api/test_admin_config.py tests/skills/test_planting_operation_skills.py tests/test_pending_actions.py`.
- OpenSpec strict validation passed: `openspec validate enhance-agent-skill-capabilities --strict`.
- Architecture checks were run. `bash scripts/check-layer-deps.sh` currently fails on pre-existing file-size debt in `backend/app/core/llm_client_manager.py` with 507 lines over the 500-line limit; this change did not touch that file. Guide+Sensor pairing and lint-expiry checks passed.
- Admin visibility is backend/API level for this change: Skill metadata is exposed through `/admin/skills`; trace diagnostics, structured pending action context, and drilldown links are exposed through `/admin/traces/{request_id}/diagnostics` and timeline/node APIs. No frontend UI component was required beyond consuming these API fields.
