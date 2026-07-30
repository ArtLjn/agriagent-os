## Why

Backend code has accumulated compatibility shims, oversized modules, long functions, and feature files grouped by legacy technical layers. This makes AI-assisted changes faster to produce than humans can review, and increases the risk that small feature work spreads across too many files.

This change establishes a focused backend complexity reduction pass: remove redundant code only when behavior is preserved, move cohesive feature code toward clear module boundaries, and turn the existing scan findings into measurable implementation tasks.

## What Changes

- Remove redundant compatibility entry files whose callers can use the real module directly.
- Move DataFlywheel service code out of the generic `services/` pile into a cohesive backend module boundary without changing API behavior.
- Split the highest-risk long functions in Agent runtime/router code into smaller, named steps while preserving current tests and public behavior.
- Align architecture docs and harness checks so they reward simpler direct dependencies instead of encouraging empty wrapper modules.
- Keep behavior unchanged for existing HTTP APIs, Agent flows, database schema, and response contracts.

## Capabilities

### New Capabilities

- `backend-complexity-governance`: Defines backend redundancy removal, module consolidation, complexity budget, and verification requirements for safe refactoring.

### Modified Capabilities

None.

## Impact

Affected areas:

- `backend/app/api/`, `backend/app/bootstrap/`, `backend/app/modules/`, `backend/app/services/`, `backend/app/agent/`, `backend/app/infra/`
- `backend/tests/` targeted tests for auth, DataFlywheel services/API, Agent router/runtime, and startup behavior
- `docs/architecture/` module boundary and compatibility-entry documents
- `scripts/check-layer-deps.sh`, `scripts/check-complexity-budget.sh`, and harness entry points

Non-impact:

- No intentional HTTP API contract changes.
- No database schema changes.
- No new abstraction framework, plugin system, service container, or broad rewrite.
- Frontend, mobile app, archive/output repository cleanup, and unrelated existing worktree changes are out of scope for this change.
