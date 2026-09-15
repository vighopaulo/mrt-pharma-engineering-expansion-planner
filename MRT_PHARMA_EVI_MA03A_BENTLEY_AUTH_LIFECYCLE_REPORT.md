# MRT Pharma — EVI-MA-03A Bentley 3D Auth Lifecycle Stabilization

The 3D viewport worked, then later reverted to `baseViewerInitializer.validTokenNeeded`. This build makes viewer authentication a single authoritative state machine: the `<Viewer>` mounts only on verified token readiness, an expiring/lost token demotes to an app-owned Reconnect UI (never the raw Bentley string), and application state (equipment, clinical program, 2D plan) survives auth recovery. Equipment CRUD / Hide-Show / persistence were NOT touched.

manual_acceptance = **PENDING** (do not self-accept). Secret-safety upheld: no token / refresh token / secret / verifier / `.env` value was read, logged, tested, or committed.

---

## 1. Reconciled state

Branch `main`; HEAD `1de2c5b`; origin/main `1de2c5b`; divergence 0/0. All EVI-MA-01…02E work preserved. Test baseline before this build: 73 files / 1141 tests.

## 2. Exact runtime failure seam

EVI-MA-03 verified a token before first mount, but two gaps let `validTokenNeeded` recur:

1. **No re-evaluation after mount (the recurrence cause).** `ready` was a one-shot boolean set once after silent sign-in; it never reset. When the token later **expired / the session went stale** ("worked five minutes ago"), the `<Viewer>` stayed mounted and `BaseViewerInitializer` re-checked the token on its own event and rendered the raw `validTokenNeeded` — with no path back.
2. **Redirect-on-silent-failure could dead-end.** The silent-failure branch called `signInRedirect`, which can be blocked in the embedded host (same class as the `window.confirm` issue), leaving a stuck/loading or a Viewer with no token.

Proven cause classification: **stale/expired token after TOKEN_READY with no demotion path** (plus a fragile auto-redirect). Not a client-instance mismatch by construction (the client is memoized and the SAME instance drives silent sign-in, `getAccessToken`, and the `<Viewer authClient>`), and not a callback race (the `/signin-callback` handler completes `handleSignInCallback` before returning to `/viewer`).

## 3. One authoritative auth state machine

New pure, secret-free machine in `viewerAuth.ts`:

```
ViewerAuthState = CONFIG_MISSING | INITIALIZING | AUTHENTICATING | TOKEN_READY | REAUTH_REQUIRED | ERROR
viewerMayMount(state) === (state === 'TOKEN_READY')
```

`viewerAuthReducer` transitions: `TOKEN_VERIFIED → TOKEN_READY`; `TOKEN_NOT_READY → REAUTH_REQUIRED`; `TOKEN_LOST` while `TOKEN_READY → REAUTH_REQUIRED`; `RECONNECT_REQUESTED → AUTHENTICATING`; `AUTH_ERROR → ERROR`. `TOKEN_READY` is reachable ONLY via `TOKEN_VERIFIED`.

## 4. Viewer mount condition (LiveItwinViewer)

- Replaced the `ready` boolean with `useReducer(viewerAuthReducer)`; the `<Viewer>` renders only when `viewerMayMount(authState)`.
- After `signInSilent()`, `getAccessToken()` is verified via `decideTokenReadiness` (authorized + non-empty token + not within a 30s expiry skew) on the SAME auth client. If not ready → `TOKEN_NOT_READY` (→ REAUTH_REQUIRED); it no longer auto-redirects into a possible dead end.
- **Expiry handling:** while `TOKEN_READY`, a 30s (non-aggressive) re-verification re-checks `getAccessToken()`/expiry; on loss it dispatches `TOKEN_LOST` → `REAUTH_REQUIRED`, unmounting the Viewer instead of leaving the raw `validTokenNeeded`.
- The auth state is surfaced to the route via `onAuthStateChange`; `reconnectNonce` re-runs silent+verify.

## 5. Same auth client instance

The `BrowserAuthorizationClient` is memoized on the primitive config values and is the single instance used for `signInSilent()`, `getAccessToken()`, the re-verification interval, and the `<Viewer authClient>` prop. No second client is created for the mount. (The interactive Reconnect uses a fresh client only to perform the PKCE redirect, which navigates away; on return, the memoized client rehydrates the session.)

## 6. Callback behavior (unchanged, verified)

`/signin-callback` → `SigninCallbackHandler` completes `handleSignInCallback()` before navigating to `/viewer`; on return, `/viewer`'s silent+verify establishes `TOKEN_READY` only after `getAccessToken()` succeeds. `/signin-callback` = 200.

## 7. App-owned failure UI + Reconnect (never the raw string)

`BentleyViewer` consumes `onAuthStateChange`. When `!viewerMayMount(viewerAuthState)` it renders an app-owned overlay: "Connecting…" for INITIALIZING/AUTHENTICATING, else "3D BIM authentication required" with a **Reconnect Bentley 3D** button (drives interactive PKCE via `reconnectBentleyAuth`) + the Developer PRESENT/MISSING config diagnostic. The raw `baseViewerInitializer.validTokenNeeded` is no longer the user-facing failure because the Viewer is not mounted when the token is not ready.

## 8. Application state preserved across auth recovery

Reconnect only increments a nonce + triggers the PKCE redirect. It does NOT reload the app, clear equipment, hidden/lock state, clinical assignments, planning volumes, 2D plan, or selection — all of that lives in the overlay module singleton + localStorage, independent of Bentley auth. When auth returns to TOKEN_READY, the decorators reconstruct from the same authoritative state.

## 9. Files changed

- `frontend/src/lib/viewerAuth.ts` — `ViewerAuthState`, `viewerAuthReducer`, `viewerMayMount`, `TOKEN_EXPIRY_SKEW_MS`; `decideTokenReadiness` gains skew.
- `frontend/src/components/viewer/LiveItwinViewer.tsx` — state-machine mount gate, token re-verification interval, `onAuthStateChange`/`reconnectNonce` props, `reconnectBentleyAuth`.
- `frontend/src/routes/BentleyViewer.tsx` — `viewerAuthState` + reconnect overlay + `handleReconnect`.
- `frontend/src/routes/BentleyViewer.css` — overlay styling.
- `frontend/src/tests/eviMa03aAuthLifecycle.test.ts` (new).

## 10. Tests

`eviMa03aAuthLifecycle.test.ts` (13 tests): mount only in TOKEN_READY; CONFIG_MISSING stays; silent-ok-but-no-token → REAUTH_REQUIRED; token verified → TOKEN_READY; TOKEN_LOST while ready → REAUTH_REQUIRED (no-op otherwise); reconnect restores TOKEN_READY; AUTH_ERROR → ERROR; expiry skew; cached-valid → READY / stale → NEEDS_REAUTH; token value never in output; states are non-secret enums. Full suite: **74 files / 1154 tests PASS** (was 73 / 1141; +13). EVI-MA-01…02E + EVI-MA-03 suites unchanged and green.

## 11. Verification

- Typecheck `tsc -b`: PASS. Production build: PASS (pre-existing advisories only).
- `/viewer` = **200**; `/signin-callback` = 200. WASM `public/scripts/draco_decoder.wasm` + Bentley worker `public/scripts/parse-imdl-worker.js` present.
- Canonical dev server RUNNING on **port 3000**. No backend Python changed. No tests weakened.

## 12. Manual acceptance (do NOT self-accept)

1. Open `/viewer`; if auth valid, full 3D BIM renders. 2. Normal refresh → BIM returns (cached auth) OR the Reconnect overlay appears — never only `validTokenNeeded`. 3. Hard refresh → same. 4. If Reconnect appears, click it → complete Bentley PKCE → BIM renders. 5. Confirm Clinical Program, 2D plan, and equipment state survived. 6. Select KIUBE → Hide/Show still works; Delete unchanged. 7. Refresh again → BIM remains recoverable.

## 13. Stop condition

Auth state is deterministic; Viewer mounts only on verified token readiness; the raw `validTokenNeeded` is prevented from being the normal failure UI; a Reconnect path exists; refresh/expiry behavior is tested; application state survives; all regressions pass; `/viewer` runs on port 3000 for manual acceptance. STOPPED. Not starting PTS / RTHS / MRT animation / Build 2.
