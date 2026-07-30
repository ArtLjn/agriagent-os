## ADDED Requirements

### Requirement: Capability registry source of truth
The system SHALL maintain a Skill capability registry that defines each business capability, domain, operations, examples, anti-examples, tags, version, owner, status, context dependencies, cache invalidation groups, and legacy aliases.

#### Scenario: Registry exposes capability metadata
- **WHEN** the Skill catalog is built
- **THEN** each enabled capability includes `name`, `domain`, `capability`, `description`, `examples`, `anti_examples`, `tags`, `version`, `owner`, `status`, `operations`, and `context_dependencies`
- **AND** the catalog does not infer business capability from directory name alone

#### Scenario: Registry validates operation risk
- **WHEN** a capability declares an operation
- **THEN** the operation includes a machine-readable risk level
- **AND** write, delete, settlement, and external-network operations declare confirmation or enablement behavior

### Requirement: Legacy Skill alias mapping
The system SHALL map every deprecated CRUD/API-level tool name to a capability and operation before the old tool name can be hidden or removed.

#### Scenario: Legacy write Skill resolves to capability operation
- **WHEN** a pending action references `create_cost_record`
- **THEN** the alias registry resolves it to `manage_cost.create_record`
- **AND** execution remains compatible with the existing write confirmation flow

#### Scenario: Missing alias fails validation
- **WHEN** an enabled legacy Skill is marked deprecated
- **THEN** Registry validation fails unless the legacy Skill has an alias target with capability and operation

### Requirement: Skill governance report
The system SHALL produce a governance report that detects incomplete metadata, duplicate examples, missing anti-examples, missing aliases, invalid domains, missing owners, and operations without risk declarations.

#### Scenario: Governance check catches incomplete capability
- **WHEN** a capability lacks `owner`, `anti_examples`, or operation risk
- **THEN** the governance check reports the capability and fails the Skill registry validation

#### Scenario: Disabled Skill declares reason
- **WHEN** a capability or legacy Skill is disabled
- **THEN** the registry includes a machine-readable disabled reason
- **AND** the disabled capability is excluded from Router candidates
