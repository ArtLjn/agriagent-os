## ADDED Requirements

### Requirement: Redundant compatibility entries are removed only after caller migration

The backend SHALL delete compatibility entry files that only re-export another module once all in-repo callers have been migrated to the real owner path. Deleted compatibility entries MUST have no remaining imports in backend code, backend tests, or compatibility-entry architecture docs.

#### Scenario: Removed compatibility entry has no residual imports
- **WHEN** a compatibility file is deleted
- **THEN** repository search for its old import path returns no matches in `backend/app`, `backend/tests`, and `docs/architecture/compatibility-entries.md`

#### Scenario: Direct owner path remains tested
- **WHEN** callers are migrated from a compatibility entry to the real owner module
- **THEN** targeted tests for that behavior pass without `ImportError` or `ModuleNotFoundError`

### Requirement: Backend feature piles are consolidated by cohesive module ownership

The backend SHALL move cohesive feature files out of generic technical piles when a feature has enough files to make the generic directory hard to scan. DataFlywheel backend code MUST be organized under a cohesive `modules/data_flywheel` boundary or an equivalent documented module boundary, without changing API contracts.

#### Scenario: DataFlywheel imports use the module boundary
- **WHEN** DataFlywheel service files are migrated
- **THEN** API and test imports reference the new DataFlywheel module boundary instead of `app.services.data_flywheel_*`

#### Scenario: DataFlywheel API behavior is preserved
- **WHEN** DataFlywheel module files are moved
- **THEN** existing DataFlywheel API and service tests pass with unchanged request and response behavior

### Requirement: Long backend functions are split without behavior changes

The backend SHALL reduce review risk by splitting oversized functions into smaller named steps while preserving existing control flow and public behavior. Refactors MUST prefer helper extraction over new abstract frameworks unless there are multiple real implementations.

#### Scenario: Agent router classification remains stable
- **WHEN** Agent router classification helpers are extracted
- **THEN** existing router/classifier tests pass and classification outputs remain unchanged for covered cases

#### Scenario: Agent runtime tool execution remains stable
- **WHEN** Agent runtime or tool executor helpers are extracted
- **THEN** existing runtime/tool executor tests pass and tool call metadata behavior remains unchanged for covered cases

### Requirement: Complexity guardrails are aligned with target architecture

Architecture docs and harness checks SHALL encode the target dependency direction and complexity budget without encouraging empty wrapper modules. Guardrails MUST block new generated Python cache files and MUST keep historical complexity debt visible as warnings until a strict cleanup phase is explicitly started.

#### Scenario: Harness detects complexity regressions
- **WHEN** backend code is changed
- **THEN** `scripts/check-complexity-budget.sh` reports generated-file pollution, oversized files, long functions, tracked archive/output noise, nested repositories, mixed lock files, and abstraction keyword density

#### Scenario: Layer checks match documented service dependencies
- **WHEN** `services/` imports low-level `core` or `infra` primitives
- **THEN** layer checks allow those imports while still rejecting `services/` imports from `api/`

### Requirement: Refactoring verification is explicit and repeatable

Each cleanup slice SHALL declare and run targeted verification before completion. Verification MUST include import-path search, relevant pytest suites, lint, layer checks, complexity budget checks, and generated cache cleanup.

#### Scenario: Cleanup slice is complete
- **WHEN** a cleanup slice claims completion
- **THEN** the final report lists the commands run, their pass/fail result, and any remaining historical warnings

#### Scenario: Test-generated files are removed
- **WHEN** tests generate `__pycache__`, `.pytest_cache`, or `*.pyc` under project code or tests
- **THEN** those generated files are removed before final status is reported
