## ADDED Requirements

### Requirement: Enabled Skill metadata completeness
Every enabled production Skill SHALL declare complete runtime metadata rather than relying indefinitely on default incomplete metadata.

#### Scenario: Existing Skill migrated
- **WHEN** an existing Skill remains enabled after this change
- **THEN** its metadata SHALL include permission level, risk level, context dependencies, cache invalidation groups, confirmation schema, evaluation tags, business domain, and enabled state
- **AND** `metadata_incomplete` SHALL be false unless the Skill is explicitly marked legacy with an owner and migration task

#### Scenario: New Skill rejected without metadata
- **WHEN** a new Skill is added under `backend/app/agent/skills`
- **THEN** validation SHALL fail unless it declares complete metadata and documentation

### Requirement: Skill enablement state
Every Skill SHALL expose whether it is enabled, disabled, or admin-only, including a machine-readable reason for disabled state.

#### Scenario: Disabled external search
- **WHEN** `web_search` is unavailable because the search provider is unstable or disabled by config
- **THEN** the Skill registry SHALL expose it as disabled
- **AND** the registry SHALL include a disabled reason

### Requirement: Skill domain taxonomy
Every Skill SHALL declare a business domain used by coverage matrix, evaluation reports, and admin diagnostics.

#### Scenario: Labor Skill domain
- **WHEN** the system lists `settle_labor_payment`
- **THEN** the Skill metadata SHALL include a labor or planting domain tag
- **AND** evaluation coverage SHALL aggregate it under that domain
