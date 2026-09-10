# MRT Pharma — Project BIM Selection + Persistent Active iModel

Baseline `HEAD = origin/main = b2abe6bf28056d002d140b52fb54e94c9cd417eb`, `0 / 0`, nothing staged. Implementation complete + verified. No Bentley writes; no re-ingestion. `CHECKPOINT = HOLD_FOR_MANUAL_ACCEPTANCE`.

## What this fixes

Previously `/viewer` reopened the synthetic engineering fixture, and the clinic only appeared via `?imodel=…`. Now the clinic is a **first-class, persistent, selectable project BIM** — ordinary `/viewer` opens the persisted active BIM (the clinic by default), and switching is a normal-mode control. Ingestion (upload/convert) and opening (select an existing iModel) are separated: an already-ingested BIM is never re-ingested to open it.

## Core design (pure, Bentley-free)

`frontend/src/lib/projectBim.ts`:
- `RegisteredBim` / `PersistedActiveBim` identities + roles (`PRODUCT_DEMO_BIM`, `ENGINEERING_REGRESSION_FIXTURE`).
- `buildProjectBimRegistry({ iTwinId, fixtureIModelId })` — registers the clinic (`36381ef4-…`, product default) and the fixture. The fixture id is injected from existing config (never duplicated/guessed).
- `resolveActiveProjectBim(...)` — deterministic precedence `URL_OVERRIDE > PERSISTED_SELECTION > PRODUCT_DEFAULT > LEGACY_FALLBACK`. A persisted id is honored only if it matches a registered model (invalid persisted id is ignored, never blindly opened).
- Persistence: `localStorage` key `mrtpharma.activeProjectBim.v1`. `isSafePersistedPayload` rejects any token/Authorization/refresh/secret/pkce field and any unexpected key — only `iModelId/iTwinId/displayName/role/lastOpenedAt`.

Wired into `viewerConfig.getViewerConfig()`: the opened iModel id/iTwin id now come from the resolver. `?imodel=` remains a developer override and does NOT auto-persist.

## Normal-mode UI

`ProjectBimSelector` (top-center, not dev-gated): shows `PROJECT BIM / <active name> / <role> · Ready` and an expandable list to switch. Switching persists the safe selection and reloads `/viewer` (no `?imodel=`) so the resolver opens it. Raw UUIDs are not shown; the fixture is labeled "Engineering Regression Fixture". The raw ingestion + audit panels remain Developer-mode only.

## Report fields

```
ACTIVE_PROJECT_BIM_MODEL = IMPLEMENTED          REGISTERED_BIM_COUNT = 2
NORMAL_PRODUCT_DEFAULT_BIM = MRTway Medical Clinic Demo    DEMO_BIM_FIRST_CLASS_PROJECT_MODEL = YES
ACTIVE_BIM_SELECTION_PERSISTED = YES            ACTIVE_BIM_RESTORED_AFTER_LOGIN = YES
REUPLOAD_REQUIRED_AFTER_LOGIN = NO              SPECIAL_URL_REQUIRED_AFTER_LOGIN = NO
IMODEL_RESOLUTION_PRECEDENCE = URL_OVERRIDE > PERSISTED_ACTIVE_BIM > PRODUCT_DEFAULT > LEGACY_FALLBACK
URL_OVERRIDE_AUTOMATICALLY_PERSISTS = NO
BIM_SELECTOR_VISIBLE_IN_NORMAL_MODE = YES       ENGINEERING_FIXTURE_ROLE_VISIBLE = YES
ALREADY_INGESTED_BIM_OFFERS_OPEN = YES          RAW_INGESTION_CONTROLS_VISIBLE_IN_NORMAL_MODE = NO
BENTLEY_WRITE_API_CALL_COUNT = 0                MODEL_SWITCH_WRITES_IMODEL = NO
DEMO_IMODEL_MODIFIED = NO                       ENGINEERING_FIXTURE_MODIFIED = NO
SPATIAL_SEMANTICS_CHANGED = NO   EQUIPMENT_PIPELINE_CHANGED = NO   INTERACTION_CODE_CHANGED = NO
BIM_VISUAL_PRESENTATION_CHANGED = NO   AUTH_FLOW_CHANGED = NO   SECRET_EXPOSED = NO

ACTIVE_BIM_RESOLVER_TESTABLE_OFFLINE = YES
URL_OVERRIDE_PRECEDENCE_TEST = PASS   PERSISTED_CLINIC_RESTORE_TEST = PASS   PRODUCT_DEFAULT_CLINIC_TEST = PASS
LEGACY_FALLBACK_TEST = PASS   INVALID_PERSISTED_MODEL_TEST = PASS   BIM_PERSISTENCE_SECRET_TEST = PASS
ACTIVE_BIM_SWITCH_TEST = PASS   INGESTED_BIM_ACTION_POLICY_TEST = PASS

TYPECHECK = PASS   OFFLINE_TEST_COUNT = 364   NEW_TEST_COUNT = 12   OFFLINE_TEST_REGRESSIONS = 0
PRODUCTION_BUILD = PASS   CORE_FRONTEND_VERSION = 5.12.5   WORKER_ASSET_REAL = YES   DRACO_WASM_ASSET_REAL = YES   /viewer = 200
CHECKPOINT = HOLD_FOR_MANUAL_ACCEPTANCE
```

## Manual acceptance (STOP)

1. Open `/viewer` (no `?imodel=`). The top-center **PROJECT BIM** control should show `MRTway Medical Clinic Demo · Product / Demo BIM · Ready`, and the clinic should open (product default when nothing persisted yet).
2. Expand it, click **OPEN** on `MRTway Hospital Campus Development` → the block fixture opens (labeled Engineering Regression Fixture).
3. Switch back to `MRTway Medical Clinic Demo` → clinic opens.
4. Leave `/viewer`, re-authenticate, return to plain `/viewer` (no `?imodel=`, no upload) → the last-selected BIM is restored.

`RETURN_TO_VIEWER_OPENS_PERSISTED_CLINIC = MANUAL_CONFIRMATION_REQUIRED`; `MANUAL_BIM_SWITCH = MANUAL_CONFIRMATION_REQUIRED`; `MANUAL_RETURN_REQUIRES_IFC_UPLOAD = NO`.

Files added: `projectBim.ts`, `ProjectBimSelector.tsx`, `projectBim.test.ts`. Modified: `viewerConfig.ts`, `BentleyViewer.tsx`, `BentleyViewer.css`, `bentleyViewer.test.tsx` (config assertion updated to the new product-default resolution). Nothing staged/committed/pushed.
