## ADDED Requirements

### Requirement: LLM call failover within request
When an LLM call in `_llm_node` fails with a recoverable error (403, 429, connection error), the system SHALL automatically retry with a different provider within the same request, up to `failover_max_retries` times, before returning an error to the user.

#### Scenario: Single provider failure triggers retry
- **WHEN** LLM call fails with 403 error on ollama/gemma4:31b
- **THEN** system records failure, obtains new LLM instance from next available provider, and retries the call

#### Scenario: All providers exhausted returns error
- **WHEN** all retry attempts fail (e.g. 3 attempts)
- **THEN** system returns error message to user and logs all attempted providers

#### Scenario: Success on retry transparent to user
- **WHEN** first provider fails but second succeeds
- **THEN** user receives normal response with no indication of internal retry

#### Scenario: Non-recoverable error does not retry
- **WHEN** LLM call fails with an error that indicates a bug (e.g. invalid tool schema, 400 bad request)
- **THEN** system does not retry and immediately returns error to user

### Requirement: Configurable max retry count
The system SHALL read `failover_max_retries` from `AIConfig` to control maximum retry attempts within a single request. Default value SHALL be 3.

#### Scenario: Custom retry count from config
- **WHEN** `config.yaml` sets `ai.failover_max_retries: 2`
- **THEN** system retries at most 2 times before giving up

#### Scenario: Default retry count
- **WHEN** `config.yaml` does not set `failover_max_retries`
- **THEN** system uses default value of 3

### Requirement: Retry latency logging
Each retry attempt SHALL log the provider name, model, attempt number, and error type for observability.

#### Scenario: Retry logged with context
- **WHEN** retry occurs
- **THEN** log entry includes `attempt`, `provider`, `model`, `error_type`, `latency_ms`
