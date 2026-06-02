## ADDED Requirements

### Requirement: Parallel context preloading during LLM invocation
While the LLM is processing the user request, the system SHALL concurrently load context data that will likely be needed by tools (recent costs, current weather, active crop cycles).

#### Scenario: Preload during cost record query
- **WHEN** the user says "上个月花了多少钱"
- **AND** the LLM begins processing
- **THEN** the system SHALL concurrently load the last 30 days of cost records
- **AND** when the tool executes, the data SHALL already be available
- **AND** the tool execution latency SHALL be reduced by at least 50ms

#### Scenario: Preload data not used
- **WHEN** context data is preloaded but the LLM does not invoke a tool that needs it
- **THEN** the preloaded data SHALL be discarded
- **AND** the main response flow SHALL not be blocked or delayed

### Requirement: Preload does not block main flow
The parallel preloading SHALL be fire-and-forget. If preloading fails or times out, the main LLM response flow SHALL continue unaffected.

#### Scenario: Preload timeout
- **WHEN** preloading takes longer than 2 seconds
- **THEN** the preload task SHALL be cancelled
- **AND** the main LLM response SHALL continue
- **AND** the tool SHALL load its own data when executed
