## 1. Backend Schema

- [x] 1.1 Add DailyAdvice v2 Pydantic models in `backend/app/schemas/agent.py` for overview, generation metadata, compact item, detail item, evidence, steps, related entries, actions, and hero badges.
- [x] 1.2 Keep backward-compatible `AdviceItem.title/detail/priority/icon` fields by mapping them from `compact`.
- [x] 1.3 Update API response typing for `GET /agent/daily` and `POST /agent/daily/refresh` without changing endpoint paths.

## 2. Candidate To Skeleton Mapping

- [x] 2.1 Extend daily advice model utilities to build deterministic item skeletons from `DailyAdviceCandidate`.
- [x] 2.2 Add category defaults for lucide icon, icon color, level, default steps, default actions, and fallback related entries.
- [x] 2.3 Add overview builder for score, subtitle, and weather/work_order/pending metrics.
- [x] 2.4 Add empty-state builder for “今日暂无高优先级事项” with usable compact and detail fields.

## 3. Validation And Reflection

- [x] 3.1 Add hard validator for DailyAdvice v2 payload: schema shape, non-empty items, candidate IDs, forbidden topics, min lengths, steps/evidence completeness, and priority escalation.
- [x] 3.2 Add daily advice Reflection check entry under `backend/app/agent/reflector/` that converts validator issues into `ReflectionResult`.
- [x] 3.3 Add repair instruction generation from validation/reflection issues for LLM retry prompts.
- [x] 3.4 Record daily advice Reflection results through existing trace collector with farm id, candidate fingerprint, retry index, and generation mode metadata.

## 4. Generation, Retry, Fallback, Cache

- [x] 4.1 Update `backend/prompts/daily_advice.j2` to request v2 JSON text completion only from provided candidate skeletons.
- [x] 4.2 Refactor `get_daily_advice` generation flow to build candidates, skeletons, call LLM, validate, reflect, retry up to 2 times, and fallback when needed.
- [x] 4.3 Ensure retry uses the same selected candidates and candidate fingerprint and does not recollect signals.
- [x] 4.4 Store full v2 JSON in `AgentRecord.content` and store schema version, generation mode, retry count, reflection decision, validation errors, and candidate fingerprint in `AgentRecord.meta`.
- [x] 4.5 Update cache-read logic to accept only matching schema version and candidate fingerprint, while safely ignoring old/polluted cache records.
- [x] 4.6 Ensure quota/error/empty LLM responses are not cached as raw advice and instead return fallback.

## 5. Mobile App Consumption

- [x] 5.1 Update `mobile-app/lib/data/api/api_models.dart` to parse DailyAdvice v2 while preserving old response compatibility.
- [x] 5.2 Update home controller/view models to render `items[].compact` for the AI 今日建议 list.
- [x] 5.3 Update advice detail navigation to pass the selected item from the existing response instead of requesting a single-item endpoint.
- [x] 5.4 Update `AdviceDetailScreen` to render `detail.title`, `detail.description`, `hero_badges`, `evidence`, `steps`, `related`, and `actions` from API data with empty-state handling.

## 6. Tests And Verification

- [x] 6.1 Add backend unit tests for validator failures: empty item, short content, forbidden topic, unknown candidate id, and priority escalation.
- [x] 6.2 Add backend tests for retry success, retry exhaustion fallback, empty candidates, and cache meta behavior.
- [x] 6.3 Add backend tests for deterministic fallback rendering from weather, operation, crop_stage, finance, setup, and record candidates.
- [x] 6.4 Add mobile model parsing tests for v2 and old response compatibility.
- [x] 6.5 Add mobile/home-detail tests proving homepage uses `compact` and detail page uses the already-loaded item `detail`.
- [x] 6.6 Run backend pytest/ruff and mobile Flutter tests for affected areas.
