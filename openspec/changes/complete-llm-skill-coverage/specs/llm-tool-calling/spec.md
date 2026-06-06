## MODIFIED Requirements

### Requirement: Skill 权限分级
每个 Skill SHALL 声明权限等级，至少区分只读、需要确认的写操作、管理员操作和外部网络访问。Tool Executor MUST 根据 metadata.permission_level 决定是否允许执行、是否需要确认、是否需要管理员身份、是否需要外部网络许可；硬编码写操作名单只能作为 legacy fallback，不得覆盖显式 metadata。

#### Scenario: 写操作需要确认
- **WHEN** LLM 选择创建成本记录的 Skill
- **THEN** Tool Executor 根据权限等级进入 pending action 确认流程，而不是直接写入

#### Scenario: 管理员 Skill 需要管理员身份
- **WHEN** LLM 选择 metadata.permission_level 为 `admin` 的 Skill
- **THEN** Tool Executor verifies the current user has administrator permission before executing the Skill

#### Scenario: 外部网络 Skill 需要启用许可
- **WHEN** LLM 选择 metadata.permission_level 为 `external_network` 的 Skill
- **THEN** Tool Executor SHALL verify that external network Skills are enabled by configuration before execution
- **AND** if disabled, Tool Executor SHALL return a user-safe failure message and record a trace with status `disabled`

#### Scenario: 显式只读 metadata 覆盖 legacy 写名单
- **WHEN** a Skill name appears in a legacy write list
- **AND** its explicit metadata declares `permission_level=read`
- **THEN** Tool Executor SHALL treat it as read-only and execute without creating a pending action

## ADDED Requirements

### Requirement: Metadata completeness gate for write and admin Skills
The system SHALL require complete metadata for every write, admin, and external network Skill before it is considered enabled.

#### Scenario: Write Skill incomplete metadata
- **WHEN** a write Skill has `metadata_incomplete=true`
- **THEN** the coverage audit SHALL report the Skill as not production-ready
- **AND** the Skill SHALL require an implementation task to declare full confirmation schema and cache invalidation

### Requirement: Disabled Skill execution behavior
Disabled Skills SHALL be excluded from tool selection and rejected if directly requested by a model tool call.

#### Scenario: Disabled web search requested
- **WHEN** `web_search` is disabled by configuration
- **AND** LLM returns a `web_search` tool call
- **THEN** Tool Executor SHALL reject the call without external network access
- **AND** trace SHALL include the disabled reason
