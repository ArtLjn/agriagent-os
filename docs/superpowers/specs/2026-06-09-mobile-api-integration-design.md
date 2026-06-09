# Mobile API Integration Design

## Goal

Connect the Flutter mobile app to the existing FastAPI backend on
`http://localhost:8099` while preserving the current mobile visual style and
respecting the backend as the source of truth for business data.

This design covers four areas:

- Authentication session foundation.
- Yaya non-streaming chat and conversation history.
- Home, billing, and profile read-only data binding.
- Record flow parsing and save flow adapted to backend scenes.

## Source Of Truth

- Backend API: existing routes in `backend/app/api` and `backend/app/modules/auth`.
- Mobile API client and repositories: `mobile-app/lib/data/api` and
  `mobile-app/lib/data/repositories`.
- Mobile visual baseline: current Flutter screens in `mobile-app/lib/features`
  and UI references under `docs/ui`.
- Backend base URL for local verification: `http://localhost:8099`, passed with
  `--dart-define=API_BASE_URL=http://localhost:8099`.

## Interface Adaptation Rules

When backend data and the current screen differ:

- Field-level or display-level differences are adapted directly in UI mappers.
- Local screen structure differences are adjusted with the current app design
  and mobile UI principles, while preserving visual style.
- Business definition, core flow, permission, charging, create/delete, or
  settlement conflicts stop implementation for that sub-flow until confirmed.
- The app must not fabricate core data that does not exist in the backend
  response just to reproduce a static design.

## Architecture

### Session Layer

Add a mobile session layer around `AuthRepository` and `ApiClient`.

Responsibilities:

- Persist the access token after login or register.
- Restore the access token on app startup before entering authenticated pages.
- Clear the token on logout.
- Route unauthenticated users to auth flow.
- Convert request failures into consistent UI states.

The backend has no logout endpoint, so logout is a local token clear.

### Data State Layer

Introduce small page-scoped async state models instead of a large global store.

Each page that binds real data should expose:

- loading state.
- data state.
- empty state.
- error state with retry.
- submitting state where a user action sends data.

Repositories stay responsible for endpoint calls. Screen models or controllers
adapt repository output to UI view models.

### Read-Only Page Binding

Profile page:

- `GET /auth/me` for nickname, phone, role, status, avatar.
- `GET /settings` for default city and weather location.
- `GET /api/app/version` for version display.

Home page:

- `GET /agent/daily` for daily advice.
- `GET /weather/forecast` for weather card.
- `GET /planting/work-orders` for recent work items.
- `GET /planting/labor/unsettled-summary` for labor reminder.

Billing page:

- `GET /costs` for recent transaction list.
- `GET /costs/summary/{year}` for yearly summary.
- `GET /debts` for receivable or debt reminders.

These are read-only bindings first. Deletion, settlement, and category
management remain separate flows because they modify business state.

### Yaya Chat

First version uses non-streaming chat:

- `POST /agent/chat` sends a message and appends the assistant reply.
- `GET /agent/conversations` fills the history drawer.
- `GET /agent/conversations/{session_id}/messages` loads selected history.

The UI should keep the current Yaya visual style. During sending, disable the
input action and show an in-thread pending state. If the API returns
`pending_action`, render a compact confirmation prompt only when its meaning can
be safely displayed from backend fields.

`POST /agent/chat/stream` is deferred until the non-streaming flow is stable.

### Record Flow

The record flow uses backend parsing first:

1. User enters a natural language record.
2. Mobile calls `POST /smart-fill/parse`.
3. Confirm screen renders backend `scene`, `draft`, `missing_fields`, and
   `warnings`.
4. User can edit missing or uncertain fields.
5. Save target is selected by backend scene and available draft fields.

Initial save mapping:

- Cost record scenes save to `POST /costs`.
- Debt scenes save to `POST /debts` when debt-specific fields are present.
- Farm log scenes save to `POST /logs`.
- Work order scenes save to `POST /planting/work-orders`.
- Wage scenes save to `POST /planting/labor/wages`.

If the scene is unknown, required fields are missing, or the draft cannot be
mapped without inventing core data, the app stays in confirm/edit state and
asks the user to complete the missing fields. It does not silently choose a
business target.

Delete and settlement operations are out of this implementation unless a
separate confirmation design is approved.

## Error Handling

All API-bound screens should handle:

- backend unreachable at `localhost:8099`.
- 401 or expired token.
- validation errors.
- empty lists.
- long text and large numeric values.
- repeated submit taps.

User-facing errors should be concise and should not display raw API paths.

## Testing And Verification

Implementation is complete only after:

- Backend connectivity is checked against `http://localhost:8099/health`.
- Mobile tests pass with `flutter test`.
- API path visibility test still confirms no endpoint paths are visible in UI.
- Auth tests cover token persistence, restore, and logout.
- Repository or controller tests cover profile, home, billing, Yaya, and record
  flow mapping.
- Manual smoke run uses
  `flutter run --dart-define=API_BASE_URL=http://localhost:8099`.

## Scope Boundaries

In scope:

- Session persistence and auth routing.
- Read-only profile, home, billing data binding.
- Non-streaming Yaya chat and history.
- Smart-fill record parsing and conservative save mapping.
- Loading, empty, error, and submitting states.

Out of scope for this design:

- SSE streaming chat.
- Billing deletion.
- Debt settlement.
- Crop cycle deletion.
- Category deletion.
- Full crop template management.
- Admin or simulation APIs in mobile app.

## Implementation Order

1. Session persistence and backend connectivity verification.
2. Profile page real data binding.
3. Yaya non-streaming chat and history.
4. Home and billing read-only data binding.
5. Record flow parse, confirm, edit, and conservative save mapping.
6. Full mobile test and local backend smoke verification.
