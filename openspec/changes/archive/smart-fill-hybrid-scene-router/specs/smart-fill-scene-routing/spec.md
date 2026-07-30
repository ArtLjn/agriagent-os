## ADDED Requirements

### Requirement: Scene Routing Strategy

The system SHALL route smart-fill requests through a two-stage strategy: regex rules first, LLM classification second. Regex rules SHALL cover high-frequency keyword patterns for all four supported scenes. When regex rules do not match, the system SHALL invoke an LLM classifier that returns one of the supported scene values or `unsupported`. The system SHALL NOT invoke the LLM classifier when regex rules already produce a confident match.

#### Scenario: Regex match routes directly without LLM call

- **WHEN** the client calls `/smart-fill/parse` without a `scene` parameter
- **AND** the input text matches a regex rule for `ledger.record` (e.g., "买化肥 200 元")
- **THEN** the system SHALL route to the `ledger.record` scenario parser
- **AND** the system SHALL NOT invoke the LLM classifier
- **AND** the system SHALL log `route_source=regex`

#### Scenario: Regex miss triggers LLM fallback

- **WHEN** the client calls `/smart-fill/parse` without a `scene` parameter
- **AND** the input text does not match any regex rule (e.g., "建个番茄的生长阶段档案")
- **THEN** the system SHALL invoke the LLM classifier
- **AND** the system SHALL route to the scene returned by the LLM
- **AND** the system SHALL log `route_source=llm`

#### Scenario: LLM classifier failure falls back to unsupported

- **WHEN** the LLM classifier is invoked
- **AND** the LLM call times out or returns an unparseable response
- **THEN** the system SHALL return scene=`unsupported`
- **AND** the response SHALL include a warning explaining that automatic scene detection failed
- **AND** the system SHALL log `route_source=llm_failed`

#### Scenario: LLM classifier returns unsupported

- **WHEN** the LLM classifier returns `scene=unsupported` with any confidence
- **THEN** the system SHALL accept that result
- **AND** the system SHALL NOT retry the classification
- **AND** the response SHALL include `missing_fields=["scene"]`

### Requirement: Client Scene Override

The `/smart-fill/parse` endpoint SHALL accept `scene` as an optional parameter. When the client provides a `scene` value, the system SHALL use it directly and SHALL NOT invoke the scene router. When the client omits `scene`, the system SHALL invoke the scene router to determine the scenario automatically.

#### Scenario: Client-provided scene bypasses router

- **WHEN** the client calls `/smart-fill/parse` with `scene="ledger.record"`
- **THEN** the system SHALL skip the scene router entirely
- **AND** the system SHALL route directly to the `ledger.record` scenario parser
- **AND** the system SHALL log `route_source=client_override`

#### Scenario: Missing scene triggers automatic routing

- **WHEN** the client calls `/smart-fill/parse` without a `scene` parameter
- **THEN** the system SHALL invoke the scene router
- **AND** the routed scene SHALL be used for subsequent parsing

### Requirement: Scene Catalog

The scene router SHALL recognize exactly four supported scenes plus an `unsupported` sentinel. Supported scenes are `ledger.record`, `crop.template`, `crop.cycle`, and `labor.worker`. Any input that cannot be confidently mapped to one of the four SHALL return `unsupported`.

#### Scenario: Four supported scenes are routable

- **WHEN** the input text matches patterns for any of `ledger.record`, `crop.template`, `crop.cycle`, or `labor.worker`
- **THEN** the scene router SHALL return the matching scene
- **AND** the system SHALL proceed with the corresponding parser

#### Scenario: Unmatched input returns unsupported

- **WHEN** the input text cannot be matched by regex rules or LLM classification
- **THEN** the scene router SHALL return `unsupported`
- **AND** the system SHALL NOT attempt to parse the input with any scenario parser

### Requirement: Regex Rule Coverage for Worker Natural Language

The regex rule set SHALL cover natural-language worker recruitment expressions beyond formal terms like "新增工人" or "招工". The rule set SHALL match patterns where a person arrives or is hired, even when the word "工人" does not appear in the text.

#### Scenario: Worker scene matches arrival expressions

- **WHEN** the input text is "我家来了一个人王树 100 工资"
- **THEN** the scene router SHALL identify this as `labor.worker`
- **AND** the system SHALL NOT route it to `ledger.record` despite the word "工资"

#### Scenario: Worker scene matches hire expressions

- **WHEN** the input text contains hiring patterns like "招了" or "雇了" or "请了" followed by a person reference
- **THEN** the scene router SHALL identify this as `labor.worker`

### Requirement: Idempotent Cache for LLM Fallback Results

The system SHALL cache LLM classifier results keyed by farm_id and normalized input text for 24 hours. Cache hits SHALL return the previously computed scene without invoking the LLM. Regex results SHALL NOT be cached because regex evaluation is deterministic and zero-cost.

#### Scenario: Repeated input reuses cached scene

- **WHEN** the same farm submits the same normalized input text within 24 hours
- **AND** the previous classification used the LLM fallback
- **THEN** the system SHALL return the cached scene
- **AND** the system SHALL NOT invoke the LLM classifier again
- **AND** the system SHALL log `route_source=llm_cache`

#### Scenario: Different input bypasses cache

- **WHEN** the input text differs from any previously cached entry (even slightly, after normalization)
- **THEN** the system SHALL invoke the regex rules and potentially the LLM classifier as if it were a new request

### Requirement: Scene Routing Observability

Every `/smart-fill/parse` call SHALL emit a structured log entry capturing the routing source, identified scene, latency, and LLM reason (when applicable). This data SHALL be queryable to support regex rule iteration and LLM accuracy monitoring.

#### Scenario: Structured log captures routing metadata

- **WHEN** any `/smart-fill/parse` call completes (success or failure)
- **THEN** the system SHALL emit a log entry with fields: `route_source`, `scene`, `duration_ms`, `farm_id`, and `llm_reason` (when route_source is `llm` or `llm_failed`)
- **AND** the log entry SHALL NOT include the raw input text (privacy)

#### Scenario: LLM classifier reason is recorded

- **WHEN** the LLM classifier is invoked and returns a scene
- **THEN** the system SHALL record the LLM's `reason` field in the log
- **AND** the reason SHALL be in Chinese and under 50 characters

### Requirement: Mobile-app Workbench Default Behavior

The mobile-app workbench SHALL NOT send a hardcoded `scene` parameter when invoking `/smart-fill/parse`. The workbench SHALL rely on backend automatic routing so that all four supported scenes are accessible from the single text input.

#### Scenario: Workbench request omits scene

- **WHEN** the user submits text from the workbench input box
- **THEN** the mobile-app client SHALL call `/smart-fill/parse` without a `scene` parameter
- **AND** the backend scene router SHALL determine the scenario

### Requirement: Admin-web Frontend Prediction as UX Hint

The admin-web client MAY maintain a lightweight regex prediction layer to provide immediate UI hints while the user types. The frontend prediction SHALL NOT override backend routing. When the frontend prediction returns `unsupported`, the client SHALL still submit the request to `/smart-fill/parse` without `scene` so the backend LLM fallback can attempt classification.

#### Scenario: Frontend prediction provides UI hint

- **WHEN** the user types "买化肥 200 元" in the admin-web smart-fill input
- **THEN** the frontend prediction layer MAY immediately display a `ledger.record` hint
- **AND** the client SHALL still submit the request with `scene="ledger.record"` to the backend

#### Scenario: Frontend prediction miss does not block submission

- **WHEN** the frontend prediction returns `unsupported` (e.g., "建个番茄档案")
- **THEN** the client SHALL submit the request to `/smart-fill/parse` without a `scene` parameter
- **AND** the backend LLM fallback SHALL attempt classification
- **AND** the client SHALL NOT show a "无法识别" warning before the backend response arrives

### Requirement: LLM Classifier Output Schema

The LLM classifier SHALL return a JSON object with three fields: `scene` (one of the four supported values or `unsupported`), `confidence` (float between 0 and 1), and `reason` (Chinese explanation under 50 characters). The system SHALL validate the response against this schema and treat invalid responses as classification failures.

#### Scenario: Valid LLM response is accepted

- **WHEN** the LLM returns `{"scene": "labor.worker", "confidence": 0.92, "reason": "提到来了一个人和工资金额"}`
- **THEN** the system SHALL route to `labor.worker`
- **AND** the system SHALL record the reason in logs

#### Scenario: Invalid LLM response triggers fallback

- **WHEN** the LLM returns a response missing the `scene` field or with an unknown scene value
- **THEN** the system SHALL treat this as a classification failure
- **AND** the system SHALL return `unsupported` to the client
- **AND** the system SHALL log `route_source=llm_failed`
