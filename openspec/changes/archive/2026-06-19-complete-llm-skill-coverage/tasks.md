## 1. Coverage Audit Foundation

- [x] 1.1 Add a registered Skill coverage audit test that loads the runtime Skill registry and reports enabled Skill names, permission levels, metadata completeness, selector coverage, chain policy coverage, and evaluation coverage.
- [x] 1.2 Add a selector parity test that fails when an enabled registered Skill has no selector trigger, intent classifier target, or explicit fallback policy.
- [x] 1.3 Add a chain policy parity test that fails when an enabled registered Skill has no `TOOL_CHAIN_MAP` entry or equivalent registry-derived chain policy.
- [x] 1.4 Add a write permission audit that fails when any write Skill is missing explicit `permission_level=write_confirm` metadata.
- [x] 1.5 Add disabled Skill audit support so intentionally disabled Skills require a machine-readable disabled reason.

## 2. Existing Skill Runtime Coverage

- [x] 2.1 Extend `tool_selector` triggers for `create_operation_work_order`, `get_operation_work_orders`, `get_labor_payables`, `settle_labor_payment`, and `update_operation_work_order`.
- [x] 2.2 Add selector regression tests for work order creation, work order query, work order correction, labor payable query, and labor payment settlement.
- [x] 2.3 Update `TOOL_CHAIN_MAP` or equivalent chain policy for all 19 registered Skills.
- [x] 2.4 Add chain expansion tests for labor and work order query Skills that require farm or planting context.
- [x] 2.5 Ensure `web_search` disabled state is represented as configuration or registry metadata rather than selector-only hardcoding.

## 3. Skill Metadata Completion

- [ ] 3.1 Add metadata fields for business domain, enabled state, disabled reason, and production readiness.
- [x] 3.2 Complete metadata for all existing read Skills, including context dependencies and evaluation tags.
- [x] 3.3 Complete metadata for all existing write Skills, including confirmation schema and cache invalidation groups.
- [x] 3.4 Complete metadata for `external_network` Skills, including enablement and failure policy.
- [x] 3.5 Update `/admin/skills` output tests to include coverage and enablement metadata.
- [ ] 3.6 Update Skill documentation validation so new Skills require complete metadata and runtime strategy.

## 4. Tool Executor Governance

- [x] 4.1 Add Tool Executor disabled-Skill rejection before parameter validation or external access.
- [ ] 4.2 Add Tool Executor external-network permission checks using configuration and metadata.
- [x] 4.3 Preserve explicit metadata precedence over legacy write Skill fallback.
- [x] 4.4 Add trace output for disabled Skill rejection with status `disabled` and disabled reason.
- [x] 4.5 Add tests for disabled `web_search`, enabled external-network execution, admin rejection, and metadata precedence.
- [x] 4.6 Enforce trusted `SkillContext.farm_id` tenant isolation for existing runtime Skills and cache keys; reject missing context before DB access and filter `cycle_id` lookups by farm.

## 5. Coverage Matrix

- [x] 5.1 Implement a coverage matrix model for domain, operation, source endpoint/service, status, Skill name, permission level, risk level, rationale, priority, and test status.
- [x] 5.2 Add a scanner or curated inventory for current FastAPI routes and key service operations.
- [x] 5.3 Classify existing API/service functions into `covered_by_skill`, `needs_skill`, `admin_skill`, `forbidden_for_llm`, and `no_skill_required`.
- [x] 5.4 Add a generated report or checked-in document summarizing high-priority `needs_skill` gaps.
- [x] 5.5 Add tests that ensure high-priority ordinary-user functions are not left unclassified.

## 6. Missing Ordinary User Skills

- [x] 6.1 Add or update Skill coverage for cost category list/create/delete with appropriate write confirmation for mutations.
- [x] 6.2 Add or update Skill coverage for crop template list/update/delete where safe for ordinary users.
- [x] 6.3 Add or update Skill coverage for farm log update/delete with confirmation and cache invalidation.
- [x] 6.4 Add or update Skill coverage for planting units where useful through natural language.
- [x] 6.4a Add or update Skill coverage for workers CRUD where useful through natural language.
- [x] 6.5 Add or update Skill coverage for wage save/update flows with confirmation and labor context.
- [x] 6.6 Add regression tests for every new ordinary-user Skill.

## 7. Admin And Sensitive Capability Policy

- [ ] 7.1 Classify admin users, quotas, trace, config, prompt reload, and cache clear capabilities in the coverage matrix.
- [ ] 7.2 Add read-only Admin Skills for safe diagnostics where approved, using `permission_level=admin`.
- [ ] 7.3 Add confirmation schema and high-risk metadata for any Admin mutation Skill that is approved.
- [ ] 7.4 Mark sensitive capabilities that must not be exposed to LLM as `forbidden_for_llm`.
- [ ] 7.5 Add non-admin rejection tests for every Admin Skill.

## 8. Evaluation And Diagnostics

- [ ] 8.1 Extend Skill regression reports to separate selection coverage from execution coverage.
- [ ] 8.2 Add coverage aggregation by Skill, business domain, permission level, confirmation path, context dependency, and exposure status.
- [ ] 8.3 Add diagnostic root-cause classification for selector exclusion, Skill disabled, permission rejection, schema validation failure, and missing capability.
- [ ] 8.4 Link failed evaluation cases to trace or simulated trace evidence.
- [ ] 8.5 Add tests for diagnostics of missing `get_labor_payables`, disabled `web_search`, rejected admin Skill, and schema validation failure.

## 9. Verification

- [x] 9.1 Run `openspec validate complete-llm-skill-coverage --strict`.
- [x] 9.2 Run backend targeted tests for skills, agent runtime, selector, evaluation, diagnostics, and admin config.
- [x] 9.3 Run `ruff check . && ruff format .` from the backend directory.
- [x] 9.4 Run `bash scripts/check-skill-docs.sh` and `bash scripts/harness-check.sh`.
- [x] 9.5 Review the coverage matrix and ensure no enabled registered Skill has selector, chain, metadata, or regression coverage gaps.
