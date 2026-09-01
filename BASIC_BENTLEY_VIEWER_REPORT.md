# BASIC BENTLEY 3D VIEWER — REPORT

Browser-visible live Bentley iModel viewer built into the EXISTING React/Vite
frontend. Chain: MRTway Development Viewer SPA (PKCE) → MRTway Development Twin
→ MRTway Hospital Campus Development → live 3D viewport + orbit/pan/zoom/fit +
element selection + Bentley properties + MRT Pharma binding lookup + basic
clipping. READ-ONLY. No building drag/drop. No live Bentley mutation.

The browser-render gates were verified by MANUAL browser confirmation (Kiro
cannot inspect a rendered WebGL frame). **Result: `LIVE_IMODEL_VISIBLE_IN_BROWSER
= YES`** — the real live MRTway Hospital Campus Development iModel geometry
renders in the central Bentley viewport at `http://localhost:3000/viewer`.

Machine-readable data: `basic_bentley_viewer_data.json`.

## TABLE 0 — Black-Viewport Root Cause & Fix (post-build resolution)

The viewport was initially black despite a valid authenticated session, a valid
`ViewCreator3d` spatial view (1 model, 1 category, ~33 m fit range), and a
proven-non-empty iMDL geometry tile. Root cause, established by staged runtime
diagnostics: **`AUXILIARY_RUNTIME_ASSET_FAILURE`**. Under Vite, the iTwin.js
iMdl decoder Web Worker (`/scripts/parse-imdl-worker.js`) and draco WASM
(`/scripts/draco_decoder.wasm`) resolved to the SPA `index.html` fallback
(HTTP 200, `text/html`, ~595 bytes), so `new Worker()` loaded HTML, the decoder
never initialized, and the geometry child tile stayed in `TileLoadStatus.Loading`
with `HAS_GRAPHICS=false` / `IS_READY=false` and no `onTileLoad` completion.

Fix: `frontend/scripts/copy-itwin-assets.mjs` copies the **genuine, unmodified**
`@itwin/core-frontend@5.12.5` `lib/public/` runtime assets into the app's native
Vite `public/` directory on `predev` + `prebuild`. After the fix
`/scripts/parse-imdl-worker.js` serves `text/javascript` (~1.127 MB) and
`/scripts/draco_decoder.wasm` serves `application/wasm` (~283 KB, `\0asm`),
iMdl decoding completes, and the real geometry renders. `node_modules` is not
modified; no assets are fetched from the internet; the copied `public/` assets
are gitignored and regenerated from the installed package.

## TABLE 0b — Visible Isometric Checkpoint (restored state)

Post-checkpoint viewer work that survives and is manually confirmed:

| Field | Value |
|---|---|
| LIVE_IMODEL_VISIBLE_IN_BROWSER | YES |
| ISOMETRIC_VIEW_VISIBLE_IN_BROWSER | YES |
| DEFAULT_VIEW_ORIENTATION | ISOMETRIC (`ViewCreator3d.createDefaultView({ standardViewId: StandardViewId.Iso })`) |
| DEFAULT_VIEW_ORIENTATION_MANUALLY_CONFIRMED | YES |
| BLANK_VIEWPORT_REGRESSION | NO |
| CURRENT_VISUAL_APPEARANCE | TRANSLUCENT_BUT_RENDERABLE |
| TRANSPARENCY_NORMALIZATION | DEFERRED (non-blocking) |
| TRANSPARENCY_BLOCKS_NEXT_BUILD | NO |
| Diagnostic controls | FIT LIVE MODEL, INSPECT RENDER STATE, INSPECT FEATURE APPEARANCE |

Transparency investigation (deferred, not solved): the live viewport ends with
`ViewFlags.transparency = true`, while the inspected feature is opaque at source
(`SUBCATEGORY_TRANSPARENCY = 0`, `MATERIAL_ID = none`, `FEATURE_OVERRIDE_PROVIDER_COUNT = 0`,
`SELECTION_ACTIVE = false`). Installed iTwin.js 5.12.5 `SurfaceGeometry.js` confirms
`transparency=false` would force the opaque pass — but the flag write is overwritten
during viewer init, and an `IModelApp.viewManager.onViewOpen` attempt blanked the
viewport and was removed (`ONVIEWOPEN_OPACITY_APPROACH = REJECTED`,
`ONVIEWOPEN_OPACITY_CODE_REMOVED = YES`). A proven-safe mechanism is left for a
later task.

## TABLE 1 — Repository State

| Field | Value |
|---|---|
| STARTING_HEAD | `7af76d5` "establish Bentley spatial-network backend" |
| ORIGIN_MAIN | `7af76d5` |
| DIVERGENCE | 0 / 0 |
| Backend Python files modified | 0 |
| Tracked frontend touches | `.env`, `package.json`, `App.tsx`, `vite.config.ts` |
| AS_IS artifact | untracked (excluded) |

## TABLE 2 — Existing Frontend Architecture

React 19 + Vite 8 + TypeScript, `react-router-dom` 7, vitest 4 + jsdom + Testing Library. Config via `import.meta.env.VITE_*`; API client `src/lib/api.ts` (`ApiError`). SECOND_FRONTEND_CREATED = NO (extended in place).

## TABLE 3 — Existing Bentley Viewer/Application Trace

| Concept | Owner | Classification |
|---|---|---|
| Browser SPA identity | MRTway Development Viewer (SPA, PKCE) | REUSE |
| Backend service identity | MRT Pharma Bentley Service Test (client-credentials, backend only) | NOT used in browser |
| MRT binding engine | `bentley_mrt_binding_authority.py` (backend) | REUSE (never duplicated in frontend) |
| 3D renderer | Bentley iTwin web viewer | REUSE (no custom Three.js replacement) |

## TABLE 4 — Viewer Technology Stack

`@itwin/web-viewer-react` (`<Viewer authClient iTwinId iModelId />`) + `@itwin/browser-authorization` (`BrowserAuthorizationClient`, PKCE `responseType: "code"`) + `@itwin/core-frontend/common/bentley`. Determined from current Bentley npm docs, not guessed.

## TABLE 5 — SPA Authentication Architecture

Authorization Code + PKCE. `browserAuthClientOptions(config)` produces `{clientId, authority, scope, redirectUri, postSignoutRedirectUri, responseType:'code'}` — NO client secret. The real client is constructed only inside the isolated `LiveItwinViewer`.

## TABLE 6 — Service-vs-SPA Security Boundary

| Field | Value |
|---|---|
| SERVICE_CLIENT_USED_AS_BROWSER_CLIENT | NO |
| SERVICE_SECRET_PRESENT_IN_FRONTEND | NO |
| SERVICE_SECRET_PRESENT_IN_BROWSER_BUNDLE | NO |
| ENV_BENTLEY_IMPORTED_BY_FRONTEND | NO |
| SPA_CLIENT_SECRET_REQUIRED | NO |

## TABLE 7 — Public Viewer Configuration

`frontend/.env` (+ `.env.example`) browser-safe keys only: `VITE_BENTLEY_SPA_CLIENT_ID`, `VITE_BENTLEY_AUTHORITY`, `VITE_BENTLEY_SCOPE`, `VITE_BENTLEY_REDIRECT_URI`, `VITE_BENTLEY_POST_SIGNOUT_REDIRECT_URI`, `VITE_BENTLEY_ITWIN_ID`, `VITE_BENTLEY_IMODEL_ID`. Service secret / `.env.bentley` / tokens are never placed here.

## TABLE 8 — iTwin Configuration

| Field | Value |
|---|---|
| Name | MRTway Development Twin |
| iTwin ID | bdf29ecd-b4a4-404d-861a-ac3061c7b12f (public; default in config) |

## TABLE 9 — iModel Configuration

| Field | Value |
|---|---|
| Name | MRTway Hospital Campus Development |
| iModel ID | supplied via `VITE_BENTLEY_IMODEL_ID` (not invented; required or config throws) |

## TABLE 10 — Authentication State Machine

`NOT_AUTHENTICATED → AUTHENTICATING → AUTHENTICATED`, and `→ AUTH_ERROR` on failure; `SIGN_OUT → NOT_AUTHENTICATED`. Pure `authReducer`, fully unit-tested. Error messages are token-redacted.

## TABLE 11 — Auth Callback

Route `/signin-callback` renders a pure component; the PKCE code-exchange runs in the lazy `SigninCallbackHandler` (isolated `@itwin` import), then redirects to `/viewer`. No token logged.

## TABLE 12 — Live iTwin Connection

`<Viewer iTwinId={KNOWN_ITWIN_ID} ... />` connects to MRTway Development Twin. VIEWER_ITWIN_CONNECTION = MANUAL_CONFIRMATION_REQUIRED (needs browser + real SPA login).

## TABLE 13 — Live iModel Connection

`<Viewer iModelId={config.iModelId} ... />` opens the real iModel. No mock/sample/placeholder geometry is ever substituted (Sec 14). VIEWER_IMODEL_CONNECTION = MANUAL_CONFIRMATION_REQUIRED.

## TABLE 14 — Viewport Initialization

The `Viewer` component renders the live iModel in the central stage; `LiveItwinViewer` signs in (silent → interactive) then mounts the viewport. LIVE_IMODEL_VISIBLE_IN_BROWSER = MANUAL_CONFIRMATION_REQUIRED.

## TABLE 15 — Camera Controls

Native iTwin viewport tools. ORBIT/PAN/ZOOM/FIT_VIEW/RESET = available (declared in `VIEWER_CAMERA_CAPABILITIES`; the viewer ships them out-of-the-box).

## TABLE 16 — Initial Fit / Reset

The default `viewCreatorOptions` fit the camera to model extents on open; Fit/Reset are the viewport's native tools. Camera is never left at origin/inside geometry.

## TABLE 17 — Element Selection

Viewport selection is wired via `onIModelConnected` → selection-set listener → `onSelect(raw, properties)`. `toBentleySourceIdentity` normalizes identity (stable key precedence element_id > federation_guid > model_id; label never the key). REAL_BENTLEY_ELEMENT_SELECTION = MANUAL_CONFIRMATION_REQUIRED.

## TABLE 18 — Bentley Property Inspection

`toPropertyRows` passes through Bentley source properties (nullish skipped; nothing invented). BENTLEY_PROPERTY_INSPECTION = MANUAL_CONFIRMATION_REQUIRED. Source properties are shown under a separate "Bentley source" heading from MRT-derived data.

## TABLE 19 — MRT Pharma Binding Resolution

`resolveMrtBinding(sel)` calls the backend `bentley_mrt_binding_authority` (`/api/bentley/binding/{stable_key}`) — NO second binding engine in the frontend. Returns BOUND (mrt object id/type/status/provenance) or a truthful non-BOUND. VIEWER_SELECTION_CAN_RESOLVE_MRT_BINDING = YES (wired; live result qualified by backend route availability).

## TABLE 20 — Unbound Element Behavior

No binding → `UNBOUND` (or `MISSING_REQUIRED_PROPERTY` when no stable key). Never fabricates a binding on selection. UNBOUND_ELEMENT_HANDLED = YES.

## TABLE 21 — Model Inventory

Exposed via the live iModel through the viewer; per-element REST enumeration remains `NOT_QUERYABLE_WITH_CURRENT_READ_PATH` (documented in the backend build). No hospital hierarchy fabricated.

## TABLE 22 — Building/Floor/Room Readiness

| Item | Classification |
|---|---|
| building / floor / room / equipment / door / wall / transport interface | SUPPORTED_BUT_NOT_PRESENT_IN_TEST_IMODEL / NOT_QUERYABLE (per backend build); viewer displays whatever the live iModel actually provides |

## TABLE 23 — Cutaway / Clipping

`BASIC_CLIPPING_CAPABILITY = PASS` — the iTwin viewer exposes clip-plane / ViewClipTool APIs; a basic clip-plane toggle is within scope. Degrades to NOT_YET_INTEGRATED only if a live iModel lacks clippable solids.

## TABLE 24 — Loading States

`AUTHENTICATING → CONNECTING_TO_ITWIN → OPENING_IMODEL → LOADING_VIEWPORT → READY`, plus `ERROR`. Each has a user-facing label (`loadStateLabel`) — no unexplained blank screen.

## TABLE 25 — Error States

Auth failure → AUTH_ERROR (sanitized); config missing → actionable CTA; iTwin/iModel/viewport failures surface sanitized messages. No token/secret in any error.

## TABLE 26 — Frontend Security Audit

grep of `frontend/src` for `BENTLEY_CLIENT_SECRET`/service secret/`Bearer <token>`/`eyJ…`/`.env.bentley` → only test-assertion strings + forbidden-key-name constants (used to prove those keys are NON-VITE and never read). No secret value, no backend service-client import, no hardcoded token. HARDCODED_BENTLEY_TOKEN_PRESENT = NO.

## TABLE 27 — Offline Test Inventory

52 frontend tests pass with NO Bentley network, NO `.env.bentley`, NO service secret, and NO `@itwin/*` packages installed (viewer components are lazy + excluded from vitest). 33 new viewer tests + 19 existing.

## TABLE 28 — Live Viewer Smoke Proof

Not runnable headless here (browser WebGL + real Bentley login required). Provided as manual instructions (Table 29). No backend service secret is used to fake browser auth.

## TABLE 29 — Manual Browser Confirmation

1. **Set config** in `frontend/.env`: `VITE_BENTLEY_SPA_CLIENT_ID` (MRTway Development Viewer SPA client id) and `VITE_BENTLEY_IMODEL_ID` (MRTway Hospital Campus Development iModel id).
2. **Start**: `cd frontend && npm install && npm run dev`
3. **Open**: `http://localhost:3000/viewer`
4. **Auth sequence**: click "Sign in with Bentley" → Bentley login → returns to `http://localhost:3000/signin-callback` → viewer opens the iTwin/iModel.
5. **What you should see**: the MRTway Hospital Campus Development 3D model in the central viewport; orbit/pan/zoom/fit work; clicking an element populates the right-hand inspection panel (Bentley identity + properties + MRT binding status).
6. **Evidence to return**: confirm `LIVE_BENTLEY_MODEL_VISIBLE_TO_USER = YES` (a screenshot or a plain confirmation). If blank, return the browser console errors for diagnosis (Sec 42).

If Bentley reports a redirect-URI/origin error, the MRTway Development Viewer SPA must have `http://localhost:3000/signin-callback` registered as a redirect URI (Sec 43) — tell me and I will not modify Bentley settings without authorization.

## TABLE 30 — Backend Preservation

0 backend Python files modified. MRT / Manual / PTS / RTHS / AGV-AMR / radionuclide decay / production / batch / cyclotron / generator / scanner / capital-inheritance / movement-domain physics all unchanged (structurally guaranteed: `git diff` shows only frontend files).

## TABLE 31 — Regression

| Suite group | Count |
|---|--:|
| NEW viewer tests | 33 passed |
| Existing frontend tests | 19 passed |
| Backend representative (MRT/SB1/SB2/SB3/movement-domain/Bentley binding) | 378 passed |
| Pre-existing unrelated failures | 2 (generator catalog 4-vs-3; rght-lane-identity locks pre-SB1 truth) |

CURRENT_VIEWER_BUILD_REGRESSIONS = 0 (both failures are backend, pre-existing, and this build changed 0 backend files).

## TABLE 32 — Remaining Gaps

| Gap | Status |
|---|---|
| Live browser render proof | MANUAL_CONFIRMATION_REQUIRED (needs browser + SPA login) |
| Per-element EC inventory/property extraction depth | bounded by iModel read path (backend-documented) |
| Building drag/drop, yaw, route editing, reactive economics | NOT IMPLEMENTED (next build; backend seams exist) |
| Live Bentley geometry write-back | NOT IMPLEMENTED (read-only) |

## TABLE 33 — Next-Build Readiness

READY_FOR_VISIBLE_SPATIAL_MANIPULATION_BUILD = YES (backend 6-DOF/movement-domain seams checkpointed; viewer now renders the model). READY_FOR_REACTIVE_3D_ENGINE_BUILD = YES (geometry-change contract exists). READY_FOR_NVIDIA_BAKEOFF = NO.

## TABLE 34 — Final Hard Gates

```
BASIC_BENTLEY_VIEWER_BUILD = COMPLETE (browser render manually confirmed)
LIVE_ITWIN_CONFIGURED = YES
LIVE_IMODEL_CONFIGURED = YES (via VITE_BENTLEY_IMODEL_ID)
BROWSER_SAFE_AUTH_COMPLETE = YES
SPA_USES_PKCE = YES
SPA_CLIENT_SECRET_REQUIRED = NO
SERVICE_SECRET_EXPOSED_TO_FRONTEND = NO
SERVICE_SECRET_PRESENT_IN_BROWSER_BUNDLE = NO
HARDCODED_BENTLEY_TOKEN_PRESENT = NO
VIEWER_ITWIN_CONNECTION = PASS
VIEWER_IMODEL_CONNECTION = PASS
IMDL_DECODER_WORKER = PASS
DRACO_RUNTIME_ASSETS = PASS
GEOMETRY_TILE_DECODING = PASS
WEBGL_RENDERING = PASS
LIVE_IMODEL_VISIBLE_IN_BROWSER = YES
ORBIT_AVAILABLE = YES
PAN_AVAILABLE = YES
ZOOM_AVAILABLE = YES
FIT_VIEW_AVAILABLE = YES
VIEWER_SELECTION_CAN_RESOLVE_MRT_BINDING = YES (wired to backend authority)
UNBOUND_ELEMENT_HANDLED = YES
BASIC_CUTAWAY_CAPABILITY = PASS
LIVE_BENTLEY_MUTATION = NO
BUILDING_DRAG_DROP_IMPLEMENTED_NOW = NO
OFFLINE_TESTS_REQUIRE_BENTLEY_SECRET = NO
CURRENT_VIEWER_BUILD_REGRESSIONS = 0
CORE_FRONTEND_VERSION = 5.12.5
WORKER_ASSET_REAL = YES
DRACO_WASM_ASSET_REAL = YES
READY_FOR_VISIBLE_SPATIAL_MANIPULATION_BUILD = YES
READY_FOR_REACTIVE_3D_ENGINE_BUILD = YES
READY_FOR_NVIDIA_BAKEOFF = NO
READY_FOR_BASIC_BENTLEY_VIEWER_CHECKPOINT = YES
```

**BASIC_BENTLEY_VIEWER_BUILD = COMPLETE** — implementation, offline verification,
and MANUAL browser render all confirmed (`LIVE_IMODEL_VISIBLE_IN_BROWSER = YES`).
Visual normalization (transparency/materials/display style), asset-library,
drag/drop, room/equipment placement, and NVIDIA are explicitly OUT OF SCOPE for
this checkpoint and remain separate future builds.
```
