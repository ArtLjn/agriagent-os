## 1. Baseline And Scope Control

- [x] 1.1 Capture current backend complexity baseline with `bash scripts/check-complexity-budget.sh` and record historical warnings separately from new regressions
- [x] 1.2 Capture current layer baseline with `bash scripts/check-layer-deps.sh`
- [x] 1.3 Capture current targeted test baseline for auth startup, DataFlywheel, Agent router, and Agent runtime/tool executor suites
- [x] 1.4 Confirm unrelated existing worktree changes are not part of this change before editing

## 2. Compatibility Shim Cleanup

- [x] 2.1 Delete only re-export compatibility entries after all callers are migrated to real owner paths
- [x] 2.2 Update imports from `app.api.auth` and `app.services.auth_service` to `app.modules.auth.*`
- [x] 2.3 Update imports from `app.infra.settings`, `app.infra.database`, and `app.infra.json_repair` to `app.core.*`
- [x] 2.4 Update `docs/architecture/compatibility-entries.md` so completed compatibility entries are removed from the active list
- [x] 2.5 Verify old import paths return no matches in `backend/app`, `backend/tests`, and compatibility docs
- [x] 2.6 Run auth/startup targeted tests and `ruff check` for touched backend files

## 3. DataFlywheel Module Consolidation

- [x] 3.1 Create `backend/app/modules/data_flywheel/` with plain module files and no new repository/service/factory framework
- [x] 3.2 Move `backend/app/services/data_flywheel_case_builder.py`, `data_flywheel_issue_detector.py`, and `data_flywheel_judge_service.py` into the DataFlywheel module boundary
- [x] 3.3 Move repair-pack files into the DataFlywheel module boundary: `data_flywheel_repair_pack_*`
- [x] 3.4 Move review issue chain files into the DataFlywheel module boundary: `data_flywheel_review_issue_chain_*`
- [x] 3.5 Move session review/sync and main `data_flywheel_service.py` into the DataFlywheel module boundary
- [x] 3.6 Update API, tests, and internal imports from `app.services.data_flywheel_*` to the new module paths
- [x] 3.7 Run DataFlywheel service/API tests and verify request/response behavior remains unchanged
- [x] 3.8 Search for residual `app.services.data_flywheel_` imports and remove or justify any remaining compatibility path

## 4. Agent Router Complexity Reduction

- [x] 4.1 Inspect `backend/app/agent/router/classifier.py` and identify cohesive helper extraction points inside `classify`
- [x] 4.2 Extract deterministic pre-checks, model result normalization, fallback handling, and final decision shaping into named helpers
- [x] 4.3 Keep classification behavior unchanged and avoid new strategy/factory abstractions
- [x] 4.4 Remove or resolve the local TODO about redundant code if the extraction proves it obsolete
- [x] 4.5 Run Agent router/classifier tests and compare covered classification outputs

## 5. Agent Runtime And Tool Executor Complexity Reduction

- [x] 5.1 Inspect `backend/app/agent/runtime/nodes.py::_llm_node` and extract named helpers for context preparation, LLM invocation, retry/fallback handling, and response assembly
- [x] 5.2 Inspect `backend/app/agent/runtime/tool_executor.py::_parallel_tool_node` and `_call_one` and extract named helpers for permission checks, pending-action handling, tool invocation, and result metadata assembly
- [x] 5.3 Keep helper extraction local unless a support module is required to reduce file size below the agreed budget
- [x] 5.4 Run Agent runtime/tool executor tests, including metadata and dual-phase retry tests
- [x] 5.5 Search for behavior-changing rewrites and revert any extraction that changes covered outputs

## 6. Harness, Docs, And Final Verification

- [x] 6.1 Align `docs/architecture/boundaries.md`, `.claude/CLAUDE.md`, `AGENTS.md`, and harness scripts with the target backend dependency direction
- [x] 6.2 Ensure `scripts/check-complexity-budget.sh` is wired into `scripts/harness-check.sh` and Guide+Sensor pairing
- [x] 6.3 Run `ruff check app tests` or a documented narrower ruff command if full lint is blocked by unrelated historical issues
- [x] 6.4 Run targeted pytest suites for auth/startup, DataFlywheel, Agent router, and Agent runtime/tool executor
- [x] 6.5 Run `bash scripts/check-layer-deps.sh`, `bash scripts/check-complexity-budget.sh`, and `bash scripts/check-guide-sensor-pairing.sh`
- [x] 6.6 Clean generated `__pycache__`, `.pytest_cache`, and `*.pyc` under project code/tests after verification
- [x] 6.7 Summarize remaining historical warnings separately from this change's completed cleanup

## 7. Subagent Work Packages

- [x] 7.1 Subagent A: DataFlywheel module consolidation only, editing DataFlywheel service/API/test imports and running DataFlywheel tests
- [x] 7.2 Subagent B: Agent router classifier extraction only, editing router files/tests and running router tests
- [x] 7.3 Subagent C: Agent runtime/tool executor helper extraction only, editing runtime files/tests and running runtime/tool executor tests
- [x] 7.4 Subagent D: Harness/docs verification only, editing docs/scripts after implementation slices and running harness checks
- [x] 7.5 Main agent: integrate subagent outputs, resolve import conflicts, run final verification, and prepare final report
