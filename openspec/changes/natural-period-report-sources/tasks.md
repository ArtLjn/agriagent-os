## 1. Schema And Contracts

- [x] 1.1 Extend structured report schemas with period, summary, metrics, sections, recommendations, source_summary, and source_refs.
- [x] 1.2 Define stable section payload conventions for A2UI rendering, including section type, title, items/data, and source_ref_ids.
- [x] 1.3 Keep ReportResponse and history item compatibility by preserving content and allowing structured_data to be null for old records.

## 2. Report Data Collection

- [x] 2.1 Refactor report_data_service to build report facts for a supplied natural period instead of only returning cycles, costs, and logs.
- [x] 2.2 Add operation_work_orders collection for the report period, filtered by farm_id and date.
- [x] 2.3 Add labor_entries/workers aggregation for payable, paid, unpaid, worker count, and labor cost summary.
- [x] 2.4 Add source_refs generation for crop cycles, cycle stages, farm logs, work orders, cost records, labor entries, farm, user settings, and weather service.
- [x] 2.5 Add previous natural period aggregation for monthly comparison and optional weekly comparison.
- [x] 2.6 Treat weather as optional future-risk input and allow report generation to continue when weather is unavailable.

## 3. Weekly And Monthly Report Assembly

- [x] 3.1 Implement weekly section assembly for snapshot, operation review, work order status, crop stage updates, finance flow, weather risks, and next actions.
- [x] 3.2 Implement monthly section assembly for KPIs, period comparison, cost structure, cycle portfolio, operation distribution, labor summary, finance exceptions, and next month plan.
- [x] 3.3 Ensure all numeric metrics and section facts are computed deterministically before LLM invocation.
- [x] 3.4 Limit long detail lists to bounded top-N items and expose aggregate counts for omitted data.

## 4. LLM Copywriting Boundary

- [x] 4.1 Update structured report prompt so LLM only returns summary, highlights, and recommendations based on supplied facts.
- [x] 4.2 Parse LLM copywriting output safely and ignore any attempted fact, metric, section, or source_ref overrides.
- [x] 4.3 Add deterministic fallback summary and recommendations when LLM output is missing or invalid.
- [x] 4.4 Render a backward-compatible Markdown content summary from structured_data.

## 5. API And Persistence

- [x] 5.1 Update POST /agent/report response to return the new structured_data contract.
- [x] 5.2 Save structured report data in AgentRecord.meta with source refs and generated copywriting.
- [x] 5.3 Update report history mapping to return structured_data when present and null when absent.
- [x] 5.4 Preserve existing report_type and cycle_id behavior, including optional cycle filtering where supported.

## 6. Verification

- [x] 6.1 Add unit tests for natural week and natural month period calculation.
- [x] 6.2 Add service tests for weekly report sections and source_refs.
- [x] 6.3 Add service tests for monthly report sections, previous-period comparison, and missing baseline handling.
- [x] 6.4 Add tests proving LLM output cannot override deterministic facts or source refs.
- [x] 6.5 Add API/history tests for new structured_data and old-record fallback.
- [x] 6.6 Run backend lint and targeted pytest for report services and agent report endpoints.
