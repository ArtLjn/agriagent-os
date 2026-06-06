## ADDED Requirements

### Requirement: Registered Skill regression coverage gate
The evaluation suite SHALL verify that every enabled registered Skill has at least one regression case for selection and one domain-appropriate case for execution or rejection.

#### Scenario: Enabled Skill without case
- **WHEN** a registered enabled Skill has no regression case
- **THEN** the evaluation report SHALL mark it `coverage_missing`
- **AND** CI SHALL fail for production-ready Skills

#### Scenario: Admin Skill rejection case
- **WHEN** a Skill declares `permission_level=admin`
- **THEN** the regression suite SHALL include a non-admin rejection case
- **AND** if admin execution is enabled, an admin success case

#### Scenario: External network disabled case
- **WHEN** a Skill declares `permission_level=external_network`
- **THEN** the regression suite SHALL include a disabled-provider case that performs no real network access

### Requirement: Coverage report by exposure status
The evaluation report SHALL aggregate Skill coverage by exposure status from the coverage matrix.

#### Scenario: Matrix status reported
- **WHEN** the evaluation report is generated
- **THEN** it SHALL include counts for `covered_by_skill`, `needs_skill`, `admin_skill`, `forbidden_for_llm`, and `no_skill_required`
- **AND** it SHALL list high-priority `needs_skill` entries

### Requirement: Selection and execution split
Skill regression SHALL report selection coverage separately from execution coverage.

#### Scenario: Skill selected but not executed
- **WHEN** selector includes `settle_labor_payment`
- **AND** Tool Executor rejects it because required parameters are missing
- **THEN** evaluation SHALL mark selection as covered
- **AND** execution as failed with a parameter or confirmation classification
