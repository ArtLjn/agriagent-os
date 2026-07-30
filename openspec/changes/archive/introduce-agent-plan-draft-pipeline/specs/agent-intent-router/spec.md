## ADDED Requirements

### Requirement: Router output feeds PlanDraft evidence
The router SHALL expose selected tools, intent frames, semantic evidence, missing fields, and policy decisions as PlanDraft input evidence rather than being treated as the final execution plan.

#### Scenario: Router evidence converted into draft
- **WHEN** the router identifies "李海这个月干了15天压瓜" as implicit farm labor work
- **THEN** the PlanDraft SHALL include router evidence for worker, operation type, quantity, and write risk
- **AND** execution SHALL still wait for PlanDraft validation

#### Scenario: Router no-tools business-like input becomes planning issue
- **WHEN** the router returns no selected tools for business-like input
- **THEN** the PlanDraft SHALL record the no-tool route state
- **AND** the system SHALL validate whether clarification or fallback response is safe

### Requirement: Router remains compatible during migration
The system SHALL keep existing RouterDecision fields available during migration while adding PlanDraft adapter output.

#### Scenario: Existing router tests still read selected tools
- **WHEN** existing router regression tests inspect `selected_tools`
- **THEN** the router SHALL continue returning compatible selected tool names
- **AND** PlanDraft-specific evidence SHALL be additive
