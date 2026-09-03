# MRT Pharma — Page-Refresh Auth Callback Recovery (FIX)

From baseline `b47107c2ea374398b3d143da68599e87d040aa46`. Implements the smallest
safe fix for the diagnosed hard-refresh failure on `/signin-callback`. No change
to PKCE, state validation, token storage, the auth-client factory/memoization,
viewer lifecycle, or any spatial/manipulation feature.

## Prior diagnosis (confirmed against current source)

```
PAGE_REFRESH_AUTH_BUG        = CONFIRMED   REFRESH_FAILURE_ROUTE = /signin-callback
PAGE_REFRESH_AUTH_FAILURE_CLASS = CALLBACK_ROUTE_BOOTSTRAP_ORDER_DEFECT + STALE_OR_CONSUMED_CALLBACK_REPLAY_ON_REFRESH
```
`PAGE_REFRESH_AUTH_ROOT_CAUSE`: `SigninCallbackHandler` called
`BrowserAuthorizationClient.handleSignInCallback()` unconditionally. The static
completer reads `localStorage["oidc.<state>"]` (state = URL `?state=` nonce) — a
ONE-TIME entry written by `signinRedirect` and consumed by the first successful
completion. On a hard refresh of the callback URL that entry is gone, so the
library throws "Could not load oidc settings from local storage" and the raw
error was shown to the user.

## Fix (narrow, callback-route only)

New pure decision seam `frontend/src/lib/authCallbackDecision.ts`:
- `oidcSettingsStorageKey(state) => "oidc." + state` (matches the installed
  `@itwin/browser-authorization@2.0.4` `loadSettingsFromStorage`).
- `decideCallbackAction({code,state,settingsEntryPresent})` →
  `PROCESS_CALLBACK | RECOVER_STALE | RECOVER_EMPTY`.
- `readCallbackActionFromEnv(location, storage)` reads URL params + the PRESENCE
  of the `oidc.<state>` entry (never the code/token/verifier/state value).

`frontend/src/components/viewer/SigninCallbackHandler.tsx` now:
- no `code`/`state` → `RECOVER_EMPTY` → `navigate('/viewer', {replace:true})`.
- `code`+`state` but `oidc.<state>` absent → `RECOVER_STALE` → `/viewer`
  (replace); the consumed callback is NOT replayed.
- `code`+`state` and settings entry present → `PROCESS_CALLBACK` →
  `handleSignInCallback()`; on success `navigate('/viewer', {replace:true})`; on
  a genuine failure the error is PRESERVED (not swallowed).
- StrictMode/re-entry guard (`startedRef`) so completion runs at most once.

Decision tree:
```
if !code || !state          -> RECOVER_EMPTY  -> /viewer (replace)
else if !oidc.<state> entry -> RECOVER_STALE  -> /viewer (replace)   (no replay)
else                        -> PROCESS_CALLBACK -> handleSignInCallback()
                                 success       -> /viewer (replace)
                                 genuine error -> show error (not swallowed)
```

```
CALLBACK_COMPONENT_FILE                 = frontend/src/components/viewer/SigninCallbackHandler.tsx
CALLBACK_DECISION_SEAM                  = frontend/src/lib/authCallbackDecision.ts
CALLBACK_STORAGE_KEY_DERIVATION         = "oidc." + <url state param>
CALLBACK_STORAGE_TYPE                   = LOCAL_STORAGE
STALE_CALLBACK_DETECTION_IMPLEMENTED    = YES
STALE_CALLBACK_RECOVERY_ROUTE           = /viewer     USES_REPLACE = YES
CONSUMED_CALLBACK_REPLAY                = NO
FRESH_CALLBACK_COMPLETION_PRESERVED     = YES   FRESH_CALLBACK_FINAL_ROUTE = /viewer   USES_REPLACE = YES
GENUINE_CALLBACK_FAILURE_PRESERVED      = YES
STRICTMODE_DUPLICATE_CALLBACK_COMPLETION = NO (startedRef guard)
AUTH_SECRET_LOGGING                     = NO (presence metadata only)
```

## Closed systems (unchanged)

```
PKCE_CHANGED = NO   STATE_VALIDATION_CHANGED = NO   TOKEN_STORAGE_POLICY_CHANGED = NO
AUTH_CLIENT_FACTORY_CHANGED = NO   AUTH_CLIENT_MEMOIZATION_CHANGED = NO
VIEWER_LIFECYCLE_CHANGED = NO   CAMERA_BEHAVIOR_CHANGED = NO
SPATIAL_SEMANTICS_CHANGED = NO   DIRECT_DRAG_CHANGED = NO   OBJECT_ATTACHED_ROTATION_CHANGED = NO   DELETE_CHANGED = NO
IMODEL_MODIFIED = NO
```

## Machine verification

```
TYPECHECK = PASS   OFFLINE_TEST_COUNT = 262   NEW_AUTH_TEST_COUNT = 8   OFFLINE_TEST_REGRESSIONS = 0
PRODUCTION_BUILD = PASS   CORE_FRONTEND_VERSION = 5.12.5
WORKER_ASSET_REAL = YES   DRACO_WASM_ASSET_REAL = YES   /viewer = 200
```
Offline tests: FRESH_CALLBACK_DETECTION, STALE_CALLBACK_DETECTION,
EMPTY_CALLBACK, env-read fresh/stale/empty, and secret-free storage access.

## Manual acceptance (pending — do not checkpoint)

```
VIEWER_HARD_REFRESH_RECOVERY         = MANUAL_CONFIRMATION_REQUIRED
STALE_CALLBACK_HARD_REFRESH_RECOVERY = MANUAL_CONFIRMATION_REQUIRED
REPEATED_VIEWER_REFRESH              = MANUAL_CONFIRMATION_REQUIRED
CHECKPOINT = HOLD_FOR_MANUAL_AUTH_ACCEPTANCE
```
1. Open `http://localhost:3000/viewer`, confirm BIM loads, press Refresh once →
   viewer returns normally, no raw callback error.
2. Refresh again → viewer returns normally.
3. If a stale `/signin-callback?code=…&state=…` is still reachable, refresh it →
   app recovers to `/viewer` (no "Could not load oidc settings…"). Do not send
   code/state/tokens. If not reproducible, record NOT_SEPARATELY_REPRODUCED.
