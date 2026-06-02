## ADDED Requirements

### Requirement: Session isolation for background execution
The simulation test execution engine SHALL create an independent database session for the background task, separate from the FastAPI request context session.

#### Scenario: Background task uses fresh session
- **WHEN** a simulation run is started via POST /simulation/run
- **THEN** the background task `_execute_run` SHALL create a new `SessionLocal()` session
- **AND** construct a new `SimulationRunner` with the fresh session
- **AND** the request-level session SHALL NOT be used for `before`/`after` snapshots

### Requirement: Per-case data isolation
The system SHALL support cleaning specified tables before each test case execution, removing only records belonging to the test farm.

#### Scenario: Clean tables before execution
- **WHEN** a test case has `precondition.clean_tables = ["cost_records"]`
- **THEN** before taking the `before` snapshot, the system SHALL delete all `cost_records` where `farm_id` matches the test farm
- **AND** the `before` snapshot SHALL contain zero records for those tables

#### Scenario: No clean tables without explicit precondition
- **WHEN** a test case has no `precondition.clean_tables`
- **THEN** the system SHALL NOT delete any existing records
- **AND** the test runs against the current database state

### Requirement: Batch execution with rate limiting
The system SHALL execute test cases sequentially with a delay between each case to avoid triggering API rate limits.

#### Scenario: Sequential execution with delay
- **WHEN** running a batch of 3 test cases
- **THEN** case 1 SHALL execute first
- **AND** after case 1 completes, the system SHALL wait 6 seconds before starting case 2
- **AND** the total execution time SHALL be at least 12 seconds (2 delays between 3 cases)
