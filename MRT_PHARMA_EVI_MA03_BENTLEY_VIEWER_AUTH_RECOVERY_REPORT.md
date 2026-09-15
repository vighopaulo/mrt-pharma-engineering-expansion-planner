# MRT Pharma — EVI-MA-03 Bentley 3D Viewer Auth / Token Recovery

The `/viewer` React shell renders, but the Bentley 3D viewport showed `baseViewerInitializer.validTokenNeeded` and the 3D BIM was absent. This build restores viewer initialization by verifying a real access token before mounting the Viewer, and replaces the raw library string with an intelligible, secret-free failure UI — without regressing any equipment / picking / deletion / collision / clinical / walkthrough / 2D-plan work.

manual_acceptance = **PENDING** (do not self-accept).

---

## 1. Reconciled state

- Branch `main`; HEAD `1de2c5b`; origin/main `1de2c5b`; divergence 0/0.
- `frontend/.env` is TRACKED and modified in the working tree. It contains PKCE SPA **public** config only (no token/secret). All required keys are PRESENT: `VITE_BENTLEY_SPA_CLIENT_ID`, `VITE_BENTLEY_IMODEL_ID` (+ optional `VITE_BENTLEY_AUTHORITY`, `VITE_BENTLEY_SCOPE`, `VITE_BENTLEY_REDIRECT_URI`, `VITE_BENTLEY_POST_SIGNOUT_REDIRECT_URI`, `VITE_BENTLEY_ITWIN_ID`). No secret value was read, printed, logged, or committed. `.env` was NOT overwritten.
- Test baseline before this build: 68 files / 1094 tests.
- All Build 1B / EVI-MA-01 / EVI-MA-02 / EVI-MA-02A work preserved.

## 2. Last-known-good vs current-bad

- Good: full Bentley BIM visible, rooms/walls/floors, cyclotron geometry, Walkthrough.
- Bad: React shell + 2D plan render; main viewport shows `baseViewerInitializer.validTokenNeeded`; 3D BIM absent; 2D reports "Room geometry is not available to derive a safe spawn" (honest, because the BIM is unavailable).

## 3. Proven root cause

`baseViewerInitializer.validTokenNeeded` is an i18n string owned by `@itwin/web-viewer-react` (it does NOT appear anywhere in this repo's source). It is displayed when the `<Viewer>`'s `BaseViewerInitializer` finds no valid access token from the auth client at initialization.

Diff evidence: the ONLY working-tree change to the viewer/auth path is a harmless `onDeselect` wiring in `LiveItwinViewer.tsx` / `BentleyViewer.tsx` (forwarding empty-selection to dismiss the inspection card). Nothing in the EVI work changed authentication, the token provider, environment loading, iTwin/iModel configuration, initialization order, or the `/signin-callback` handler. Therefore this is **not** a code regression from EVI-MA-01/02/02A.

The failing seam is **token readiness at Viewer mount**: `LiveItwinViewer` gated `<Viewer>` on `signInSilent()` resolving. But `signInSilent()` can RESOLVE without a usable access token (stale/expired session, or the client reports authorized before a token is actually available). In that state the Viewer mounts and its initializer has no valid token → `validTokenNeeded`.

Cause classification (§5): **E/F/H — token not actually available at initialization (expired/stale silent session) combined with the Viewer initializing before a verified token exists.** NOT A (config missing), NOT B/C/D (env exposure/name/loading — all keys PRESENT and Vite-exposed), NOT G (iTwin/iModel ids present), NOT I (dev-server cwd — see §6).

## 4. Fix

**(a) Verify a real token before mounting `<Viewer>` (`LiveItwinViewer.tsx` + pure `viewerAuth.decideTokenReadiness`).** After `signInSilent()`, the effect now calls `authClient.getAccessToken()` and checks `isAuthorized` / `hasSignedIn` / `accessTokenExpiresAt` via the pure `decideTokenReadiness(...)`. If the result is `NEEDS_REAUTH` (empty/expired token, or not authorized), it performs `signInRedirect('/viewer')` to interactively re-authenticate — instead of mounting the Viewer into `validTokenNeeded`. The token value is never logged, stored, or returned (the decision returns only a `READY` / `NEEDS_REAUTH` enum). The established PKCE authority is used unchanged; no token is hardcoded.

**(b) Secret-free config diagnostic (`viewerConfig.resolveViewerConfigDiagnostic`).** Reports PRESENT/MISSING per required/optional env key by NAME only — never a value. `REQUIRED_VIEWER_ENV_KEYS` = `VITE_BENTLEY_SPA_CLIENT_ID`, `VITE_BENTLEY_IMODEL_ID`.

**(c) Intelligible failure UI (`BentleyViewer.tsx`).** The auth-error and config-missing CTAs now show "3D BIM viewer unavailable — Bentley/iTwin authentication is not ready." plus a Developer-only `<ViewerConfigDiagnosticPanel>` listing PRESENT/MISSING keys. The raw `validTokenNeeded` string is no longer the primary user-facing experience, and the failure is NOT hidden.

## 5. Files changed

- `frontend/src/lib/viewerAuth.ts` — `decideTokenReadiness` (pure) + `TokenReadiness`.
- `frontend/src/lib/viewerConfig.ts` — `resolveViewerConfigDiagnostic`, `REQUIRED_VIEWER_ENV_KEYS`, `OPTIONAL_VIEWER_ENV_KEYS`.
- `frontend/src/components/viewer/LiveItwinViewer.tsx` — token verification before `setReady`; re-auth redirect otherwise.
- `frontend/src/routes/BentleyViewer.tsx` — intelligible failure UI + `ViewerConfigDiagnosticPanel`.
- `frontend/src/routes/BentleyViewer.css` — diagnostic styling.
- `frontend/src/tests/eviMa03ViewerAuthRecovery.test.ts` (new).

## 6. Dev-server working directory

Vite loads env from `frontend/` (where `frontend/.env` lives). The canonical command is run from `frontend/`: `npm run dev -- --port 3000 --strictPort`. No env files were relocated.

## 7. Viewer initialization sequence (after fix)

load public config (`getViewerConfig`) → construct PKCE `BrowserAuthorizationClient` → `signInSilent()` → **verify `getAccessToken()` non-empty + authorized + not-expired** (else `signInRedirect`) → `setReady(true)` → mount `<Viewer authClient iTwinId iModelId>` → `ViewCreator3d` builds the spatial view → viewport created → MRTway decorators/tools attach → equipment overlays render. Equipment decorators are never a substitute for the base viewport.

## 8. 3D BIM restoration status

Config PRESENT; `/viewer` = 200; `/signin-callback` = 200. The token-readiness gate now routes an unauthenticated/expired session through interactive sign-in rather than into `validTokenNeeded`. **Whether the live 3D BIM paints depends on the user completing Bentley sign-in in the browser** (interactive redirect) — which is the intended PKCE behavior and cannot be exercised headlessly. This is why manual acceptance is required (§19/§14): the 2D plan / shell rendering does not prove 3D success.

## 9. Equipment / Walkthrough regression status

No equipment, picking, deletion, collision, clinical-planning, walkthrough, or 2D-plan code was modified. Persisted application state (assignments, planning volumes, EquipmentAssetInstances, locks, collision rules, 2D markers) is untouched — the fix changes only the auth/token gate and failure UI. Once the BIM loads, authoritative room geometry returns and targeted Walkthrough can derive a safe spawn again (the honest "room geometry not available" message was a symptom of the absent BIM, not suppressed).

## 10. Verification

- Test baseline: before 68 files / 1094 tests; after **69 files / 1105 tests PASS** (+11 EVI-MA-03).
- Typecheck `tsc -b`: PASS. Production build: PASS (pre-existing chunk-size + INEFFECTIVE_DYNAMIC_IMPORT advisories only).
- `/viewer` = **200**; `/signin-callback` = 200. WASM `public/scripts/draco_decoder.wasm` + Bentley worker `public/scripts/parse-imdl-worker.js` present.
- Bentley renderability firewall: 28 PASS. No backend Python changed. No tests weakened.
- Canonical dev server left RUNNING on **port 3000** for manual inspection.

## 11. Environment variable NAMES involved (never values)

`VITE_BENTLEY_SPA_CLIENT_ID` (required), `VITE_BENTLEY_IMODEL_ID` (required), `VITE_BENTLEY_AUTHORITY`, `VITE_BENTLEY_SCOPE`, `VITE_BENTLEY_REDIRECT_URI`, `VITE_BENTLEY_POST_SIGNOUT_REDIRECT_URI`, `VITE_BENTLEY_ITWIN_ID` (optional; public defaults exist). All PRESENT.

## 12. Manual acceptance (do NOT self-accept)

- Open http://localhost:3000/viewer. If not already signed in, complete the Bentley sign-in redirect.
- A. Full Bentley BIM geometry visible in the main viewport (rooms/walls/floors).
- B. Clinical Program loads. C. 2D plan loads. D. Existing equipment at persisted positions. E. Cyclotron recognizable geometry. F. PET/CT recognizable geometry if placed. G. Walkthrough can enter a room with authoritative geometry. H. Fit to Equipment works. I. Right-click equipment context menu works. J. Delete works. K. Collision rejection works.
- If A fails: STOP (do not claim equipment acceptance). If the viewer cannot authenticate, the CTA now shows an intelligible message + a PRESENT/MISSING config list (no secrets).

## 13. Stop condition

Automated verification passes; canonical dev server left running on port 3000. STOPPED for manual acceptance. Not starting PTS / RTHS / MRT animation / Build 2 routing.
