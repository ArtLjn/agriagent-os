## ADDED Requirements

### Requirement: Capability operation execution compatibility
Tool Executor SHALL support execution decisions that include capability, operation, and legacy alias metadata while preserving existing write confirmation behavior.

#### Scenario: Capability operation enters pending confirmation
- **WHEN** LLM selects `manage_cost` with operation `create_record`
- **THEN** Tool Executor treats the operation as `write_confirm`
- **AND** Tool Executor creates a pending action before any database write

#### Scenario: Legacy alias remains executable
- **WHEN** a model or pending action references legacy tool `settle_debt`
- **THEN** Tool Executor resolves the alias to the current capability operation
- **AND** execution uses the existing compatible Skill handler until the capability handler is migrated

### Requirement: Operation risk enforcement
Tool Executor SHALL enforce risk at operation level, not only at capability or tool name level.

#### Scenario: Read operation executes without pending action
- **WHEN** LLM selects `manage_cost` with operation `query_summary`
- **THEN** Tool Executor treats the call as read-only
- **AND** Tool Executor does not create a pending action

#### Scenario: High-risk operation requires explicit confirmation
- **WHEN** LLM selects `manage_crop_cycle.delete_cycle`
- **THEN** Tool Executor treats the operation as high risk
- **AND** the confirmation message includes affected target and risk notes before execution

### Requirement: Alias-aware pending action replay
Pending action execution SHALL resolve stored legacy Skill names through the alias registry before executing or reporting failure.

#### Scenario: Historical pending action replays
- **WHEN** a stored pending action contains `delete_cost_record`
- **THEN** pending action execution resolves the alias to `manage_cost.delete_record`
- **AND** the trace records both the legacy Skill name and resolved capability operation

#### Scenario: Unknown legacy alias fails closed
- **WHEN** a stored pending action references a deprecated Skill with no alias mapping
- **THEN** pending action execution fails closed with a user-safe error
- **AND** trace records the missing alias mapping
