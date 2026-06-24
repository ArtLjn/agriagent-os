## Context

The backend currently mixes mature target modules with migration-era technical layers. The first scan found three concrete forms of avoidable complexity:

- Compatibility files that only re-export another module and no longer carry behavior.
- DataFlywheel code spread across many `backend/app/services/data_flywheel_*` files, making the generic `services/` directory a feature pile.
- Agent runtime/router files with very long functions that hide several independent steps inside one function.

The project already has architecture documentation, layer checks, and complexity-budget scripts. This change should improve those guardrails while reducing code volume and call indirection. It must not introduce a new architecture framework or alter product behavior.

## Goals / Non-Goals

**Goals:**

- Remove compatibility shims when all callers can use the real module path.
- Consolidate DataFlywheel backend code under a cohesive module boundary, with API imports updated and tests preserved.
- Split the highest-risk Agent runtime/router long functions into smaller helpers without changing routing, tool execution, or response behavior.
- Keep docs and harness checks aligned with the actual target architecture.
- Produce a subagent-friendly task breakdown with independent workstreams and explicit verification commands.

**Non-Goals:**

- No database schema changes.
- No HTTP route, request, response, or authentication behavior changes.
- No broad rewrite of Agent runtime, DataFlywheel, or API layers.
- No migration of frontend/mobile large files.
- No cleanup of existing archive/output tracked files in this change.
- No new dependency injection framework, repository layer, or generic service abstraction.

## Decisions

### D1: Delete empty compatibility entries instead of replacing them with another wrapper

When a file only imports and re-exports another module, and all callers can be updated, the file MUST be deleted. Replacing `app.infra.settings` with a different empty adapter would preserve code volume and continue hiding the real owner.

Alternatives considered:

- Keep wrappers for perceived layering consistency. Rejected because it increases call indirection without behavior.
- Add deprecation wrappers. Rejected unless external package consumers still import the old path; this backend does not expose those paths as public API.

### D2: Move feature piles by cohesive domain, not by generic patterns

DataFlywheel files should move toward `backend/app/modules/data_flywheel/` because they form one feature surface with admin APIs, repair packs, review issue chains, annotation flows, and session sync. The module should use plain Python modules and current service functions/classes; it should not introduce repository/service/factory layers beyond what already exists.

Alternatives considered:

- Split into `repository/`, `service/`, `dto/`, `mapper/`, `factory/` packages. Rejected as over-designed for the current cleanup goal.
- Leave DataFlywheel in `services/`. Rejected because it keeps the highest file-count feature inside the generic pile.

### D3: Refactor long functions by extracting named steps under test

For Agent runtime/router files, the first pass should extract cohesive helper functions inside the same module or nearby support module. This lowers review cost without changing control flow. Only move helpers into new files when the original file remains over budget or when helpers form a clear standalone responsibility.

Alternatives considered:

- Rewrite runtime as a new state machine. Rejected because behavior risk is too high.
- Create abstract strategy classes for every branch. Rejected because the current issue is function size, not missing polymorphism.

### D4: Harness should block new complexity while warning on historical debt

The complexity-budget script should continue to detect generated files, oversized files, long functions, tracked archive/output noise, nested repositories, mixed lock files, and abstraction keyword density. Existing historical debt can remain warnings during this change, while touched files should move in the right direction.

Alternatives considered:

- Make all warnings strict immediately. Rejected because the existing repository has many historical warnings and this would block incremental cleanup.
- Disable warnings. Rejected because it would remove the signal that motivated this work.

### D5: Use subagents only for independent slices

Subagents can work independently on DataFlywheel module moves, Agent router extraction, Agent runtime extraction, and harness/docs verification. They should not edit the same files concurrently. Shared contract changes such as import paths and final verification stay with the main agent.

Alternatives considered:

- One subagent per file. Rejected because it fragments context too much.
- One subagent for all backend refactoring. Rejected because it loses parallelism and makes review harder.

## Risks / Trade-offs

| Risk | Mitigation |
| --- | --- |
| Import path migration misses a dynamic import or test-only import | Run `rg` for old paths, targeted pytest suites, and startup tests after each slice. |
| DataFlywheel move creates noisy diffs | Move files in small groups and avoid renaming functions/classes unless required. |
| Agent helper extraction changes subtle control flow | Extract without rewriting logic, run existing Agent router/runtime tests, and compare behavior through targeted tests. |
| Harness rule changes become too permissive | Keep explicit forbidden dependency checks for `services -> api` and platform boundary violations. |
| Subagents conflict in shared docs or scripts | Assign docs/scripts to one verification subagent or leave final integration to the main agent. |

## Migration Plan

1. Baseline current scan and tests for the targeted backend areas.
2. Remove completed compatibility shims and update docs.
3. Move DataFlywheel service files into `modules/data_flywheel/`, update imports, and run DataFlywheel tests.
4. Extract Agent router classification helpers until the main classifier path is easier to review.
5. Extract Agent runtime/tool executor helpers around LLM node and parallel tool execution, preserving tests.
6. Run `ruff check`, targeted pytest suites, `check-layer-deps`, `check-complexity-budget`, and guide/sensor pairing.
7. Clean generated cache files after tests.

Rollback is file-level: revert the affected slice if tests fail and import search cannot be resolved quickly. There is no database rollback because this change does not alter schema.

## Open Questions

- Should `backend/app/modules/data_flywheel/` expose a stable `service.py` facade for API imports, or should APIs import specific module files directly? Default decision: use specific module files unless a small facade reduces churn.
- Should historical complexity warnings become strict only for changed files in this change? Default decision: warn globally, enforce no new generated files or empty wrappers.
