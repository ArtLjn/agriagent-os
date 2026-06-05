## ADDED Requirements

### Requirement: Skill coverage matrix
The system SHALL maintain an auditable coverage matrix that maps system capabilities to LLM-callable Skill coverage.

#### Scenario: API capability classified
- **WHEN** the coverage audit scans an API route or service operation
- **THEN** the matrix SHALL classify it as `covered_by_skill`, `needs_skill`, `admin_skill`, `forbidden_for_llm`, or `no_skill_required`
- **AND** the matrix SHALL include the domain, operation, source endpoint or service, rationale, priority, and test status

#### Scenario: Existing Skill mapped
- **WHEN** a registered Skill exists for a system capability
- **THEN** the matrix SHALL identify the Skill name, permission level, risk level, business domain, and evaluation coverage

### Requirement: Registered Skill coverage audit
The system SHALL fail coverage audit when an enabled registered Skill is missing from required runtime governance surfaces.

#### Scenario: Skill missing from selector
- **WHEN** a Skill is registered and enabled
- **AND** it is not reachable through selector triggers, intent classification, or an explicit fallback policy
- **THEN** the coverage audit SHALL report `selector_missing` for that Skill

#### Scenario: Skill missing from tool chain map
- **WHEN** a Skill is registered and enabled
- **AND** it has no entry in the tool chain map or equivalent registry-derived chain policy
- **THEN** the coverage audit SHALL report `chain_policy_missing` for that Skill

#### Scenario: Write Skill missing confirmation metadata
- **WHEN** a registered Skill performs a write operation
- **AND** its metadata does not declare `permission_level=write_confirm`
- **THEN** the coverage audit SHALL fail with `write_permission_missing`

### Requirement: System function exposure policy
Every system function considered for LLM access SHALL have an explicit exposure policy before implementation.

#### Scenario: Sensitive function excluded
- **WHEN** a function is classified as sensitive and not suitable for LLM access
- **THEN** the matrix SHALL mark it `forbidden_for_llm`
- **AND** no Skill SHALL expose it

#### Scenario: Admin function exposed
- **WHEN** a system management function is exposed through a Skill
- **THEN** that Skill SHALL declare `permission_level=admin`
- **AND** Tool Executor SHALL reject non-admin users before execution

### Requirement: No generic API proxy Skill
The system MUST NOT expose a generic API proxy Skill that allows arbitrary route or service method execution.

#### Scenario: New Skill review
- **WHEN** a new Skill is added
- **THEN** it SHALL have a specific business purpose, explicit parameter schema, permission level, risk level, documentation, and regression coverage
- **AND** it SHALL NOT accept arbitrary endpoint names, method names, or unrestricted JSON payloads for execution
