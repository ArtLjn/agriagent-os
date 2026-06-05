# skill-capability-governance Specification

## Purpose
TBD - created by archiving change enhance-agent-skill-capabilities. Update Purpose after archive.
## Requirements
### Requirement: Skill metadata contract
Every Skill SHALL declare runtime metadata including permission level, risk level, context dependencies, cache invalidation groups, confirmation schema, and evaluation tags.

#### Scenario: Skill registry exposes metadata
- **WHEN** the system lists registered Skills through the Skill registry
- **THEN** each Skill entry includes `permission_level`, `risk_level`, `context_dependencies`, `cache_invalidation`, `confirmation_schema`, and `evaluation_tags`

#### Scenario: Legacy Skill uses defaults
- **WHEN** an existing Skill has not yet declared full metadata
- **THEN** the registry provides safe default metadata and marks the Skill as `metadata_incomplete`

### Requirement: Skill documentation standard
Every Skill SHALL have a consistent `skill.md` document with name, description, parameters, when-to-use, when-not-to-use, missing-parameter strategy, confirmation behavior, cache effects, context dependencies, and examples.

#### Scenario: New Skill documentation validation
- **WHEN** a new Skill is added under `backend/app/agent/skills`
- **THEN** validation fails unless its `skill.md` contains all required documentation sections

### Requirement: Confirmation schema for write Skills
Every write Skill SHALL define a confirmation schema that identifies target object, changed fields, inferred fields, risk notes, and editable fields.

#### Scenario: Complex work order confirmation
- **WHEN** `create_operation_work_order` creates a pending action with workers and partial payment
- **THEN** the confirmation context includes operation type, date, cycle, units, workers, payable amount, paid amount, unpaid amount, inferred values, and editable fields

### Requirement: Cache invalidation metadata
Write Skill cache invalidation SHALL be declared in Skill metadata and consumed by the pending action executor after successful execution.

#### Scenario: Work order invalidates accounting and farm status
- **WHEN** `create_operation_work_order` is confirmed and executed successfully
- **THEN** the executor clears farm logs, cost summary, cost analytics, and farm status cache groups based on Skill metadata

