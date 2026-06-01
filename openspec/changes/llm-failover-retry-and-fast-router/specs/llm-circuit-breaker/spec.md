## MODIFIED Requirements

### Requirement: Error classification for quota exhaustion
`classify_error()` SHALL recognize `AllocationQuota.FreeTierOnly` error codes and classify them as `QUOTA_EXHAUSTED` level, which triggers immediate DEAD state in the circuit breaker.

#### Scenario: 403 with AllocationQuota.FreeTierOnly
- **WHEN** LLM call fails with 403 and error code `AllocationQuota.FreeTierOnly`
- **THEN** `classify_error()` returns `ErrorLevel.QUOTA_EXHAUSTED`

#### Scenario: 403 without quota exhaustion
- **WHEN** LLM call fails with 403 but without `AllocationQuota.FreeTierOnly` error code
- **THEN** `classify_error()` returns `ErrorLevel.PROVIDER` (existing behavior)

#### Scenario: Quota exhausted triggers immediate DEAD
- **WHEN** `record_failure()` receives a key with `QUOTA_EXHAUSTED` error level
- **THEN** the circuit entry is immediately set to DEAD state (no exponential backoff)

### Requirement: ErrorLevel enum extended
`ErrorLevel` enum SHALL include `QUOTA_EXHAUSTED` value in addition to existing `PROVIDER` and `MODEL` values.

#### Scenario: ErrorLevel has three values
- **WHEN** code references `ErrorLevel`
- **THEN** `QUOTA_EXHAUSTED` is available alongside `PROVIDER` and `MODEL`
