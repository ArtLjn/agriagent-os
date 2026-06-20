## 1. Backend Location Source

- [x] 1.1 Audit existing location reads in weather API, WeatherSkill, farm context summary, daily advice, profile and settings APIs.
- [x] 1.2 Define a shared backend helper/service that resolves weather location in priority order: explicit request, current farm, user_settings fallback, system default.
- [x] 1.3 Add or select the authenticated endpoint used by the mobile app to update the current user's default farm operating region.
- [x] 1.4 Ensure farm operating region updates are scoped to the current user and reject cross-farm updates with structured error code.
- [x] 1.5 Invalidate farm context, weather and Agent summary caches after farm operating region updates.

## 2. Data Compatibility And Migration

- [x] 2.1 Decide whether this change adds farm latitude/longitude fields now or keeps coordinates in compatibility fallback for this iteration.
- [ ] 2.2 Add database migration if farm latitude/longitude fields are introduced.
- [x] 2.3 Add migration or backfill routine to copy existing user_settings default city/coordinates into the user's default farm when farm location is empty.
- [x] 2.4 Preserve user_settings default_city/default_lat/default_lon compatibility for old clients and fallback weather reads.
- [x] 2.5 Add tests for old data where farm location is empty but user_settings has location.

## 3. Weather And Agent Integration

- [x] 3.1 Update farm_context_service weather summary to use the shared farm-first location resolver.
- [x] 3.2 Update WeatherSkill so unspecified weather queries use current farm location first.
- [x] 3.3 Keep explicit city weather queries as one-off overrides that do not modify farm operating region.
- [x] 3.4 Update weather API behavior or authenticated callers so default weather follows current farm operating region.
- [x] 3.5 Add tests for farm location priority, user_settings fallback and system default fallback.

## 4. Mobile First Region Setup

- [x] 4.1 Update app startup/profile loading to determine first setup from server farm location being empty.
- [x] 4.2 Request location permission only when the current account's default farm operating region is empty or the user explicitly asks to relocate.
- [x] 4.3 Initialize farm operating region from GPS nearest-city match after user grants permission.
- [x] 4.4 Do not automatically update farm operating region when the user's device moves to another city.
- [x] 4.5 Support manual region selection and optional explicit re-location from settings.

## 5. Mobile Profile And Settings UI

- [x] 5.1 Replace separate "所在城市" and "默认天气" entries with one "经营地区" or "农场地区" entry.
- [x] 5.2 Show weather as following operating region, without an independently editable default weather city.
- [x] 5.3 Show an empty-state prompt when farm operating region is missing.
- [x] 5.4 Ensure profile header and settings rows use the same farm operating region value.
- [x] 5.5 Update mobile repository/API models to stop treating user_settings default_city as the primary display source for new clients.

## 6. Tests And Verification

- [x] 6.1 Add backend API tests for reading current user profile with farm location and updating own farm location.
- [x] 6.2 Add backend tests for WeatherSkill explicit city override and farm-first default weather.
- [x] 6.3 Add backend tests for context cache invalidation after operating region updates.
- [x] 6.4 Add mobile controller/repository tests for first setup, existing farm location, denied permission and manual update flows.
- [x] 6.5 Run backend lint and tests required by project rules.
- [x] 6.6 Run mobile tests or targeted Flutter tests for profile/settings behavior.
