## ADDED Requirements

### Requirement: Skill non-call root cause classification
The diagnostic report SHALL classify why an expected Skill was not called.

#### Scenario: Selector excluded Skill
- **WHEN** a request expected `get_labor_payables`
- **AND** the selected tool set did not include `get_labor_payables`
- **THEN** diagnostics SHALL report root cause `selector_excluded`
- **AND** include the selected tool names and matching selector layer

#### Scenario: Skill disabled
- **WHEN** a request expected `web_search`
- **AND** `web_search` was disabled by configuration
- **THEN** diagnostics SHALL report root cause `skill_disabled`
- **AND** include the disabled reason

#### Scenario: Permission rejected
- **WHEN** LLM selected an admin Skill
- **AND** Tool Executor rejected it for a non-admin user
- **THEN** diagnostics SHALL report root cause `permission_rejected`
- **AND** include the required permission level

#### Scenario: Schema validation failed
- **WHEN** LLM selected a Skill but Tool Executor rejected its arguments
- **THEN** diagnostics SHALL report root cause `schema_validation_failed`
- **AND** include the validation error summary

### Requirement: Coverage matrix drilldown
Diagnostics SHALL link runtime failures to the coverage matrix entry for the affected capability.

#### Scenario: Missing Skill capability
- **WHEN** a user asks for a system function classified as `needs_skill`
- **THEN** diagnostics SHALL report that no Skill currently covers the capability
- **AND** identify the matrix entry and priority
