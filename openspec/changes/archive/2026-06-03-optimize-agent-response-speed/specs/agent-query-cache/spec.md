## ADDED Requirements

### Requirement: High-frequency query results cached locally
Query results for frequently asked questions SHALL be cached with a TTL of 5-10 minutes. The cache key SHALL include the query type and farm_id.

#### Scenario: Weather query cached
- **WHEN** the user asks "今天天气怎么样"
- **AND** the weather data is not in cache
- **THEN** the system SHALL fetch weather from the external API
- **AND** store the result in cache with a 10-minute TTL

#### Scenario: Cached weather reused
- **WHEN** the user asks "今天天气怎么样" again within 10 minutes
- **THEN** the system SHALL return the cached result
- **AND** SHALL NOT call the external weather API
- **AND** the response latency SHALL be under 200ms

### Requirement: Cache invalidation on data change
When data changes (e.g., a new cost record is created), the related cache entries SHALL be invalidated.

#### Scenario: Cost cache invalidated on new record
- **WHEN** a new cost record is created
- **THEN** the cache entries for cost summaries and analytics SHALL be invalidated
- **AND** the next query SHALL fetch fresh data
