# MRT PHARMA — EVI-MA-07A.1

## LIVE VIEWPORT DARKENING — ROOT-CAUSE DIAGNOSTIC REPORT

- **Task:** EVI-MA-07A.1 — prove the live root cause of the "viewport stays dark after placement cancel" failure BEFORE changing anything.
- **Branch:** `main` · **HEAD:** `1de2c5b0d01e3a69e0c5a744b1d58ae1f3526bd3` · **origin/main:** identical (0 ahead / 0 behind).
- **Working tree:** preserved (146 uncommitted paths — prior EVI + Build 1B.9 + EVI-MA-07A deliverables intact). Nothing reset/reverted.
- **`manual_acceptance = PENDING`** — not self-accepted.
- **Scope discipline:** I did NOT change CSS, did NOT rewrite placement state, did NOT modify Bentley display settings, and did NOT begin Build 1C/2. This deliverable is the **instrumented diagnostic + a proven static narrowing**; the final one-line fix is gated on the live capture below.

---

## 1. RECONCILE

Recorded before any change: branch `main`, HEAD `1de2c5b0d01e3a69e0c5a744b1d58ae1f3526bd3`, origin/main identical, 0/0 divergence, 146 uncommitted paths (preserved). Frontend baseline entering this task: 84 test files / 1294 tests, `tsc -b` PASS, build PASS, `/viewer` = 200.

---

## 2. WHY THE PREVIOUS THEORY WAS WRONG

EVI-MA-07A assumed the transparent `.viewer-panel-backdrop` (driven by `openPanel`) was the sole cause. The live evidence disproves that:
- The `.viewer-panel-backdrop` is **transparent** (`background: transparent`) — it cannot visually *darken* anything.
- It is a child of `.viewer-stage` only — it **cannot** cover the right-side `.viewer-inspector` (a separate CSS-grid cell), yet the inspector is reported dark too.

So a single transparent overlay inside the stage cannot explain "3D + 2D + inspector all darken together." A new, evidence-first diagnosis was required.

---

## 3. WHAT I PROVED STATICALLY (search of the whole `frontend/src`)

These findings narrow the cause and are what the live capture will confirm:

1. **No placement/darkening CSS class exists.** No CSS rule applies `filter`, `brightness`, `opacity < 1`, or a dark `background` to `.viewer-page`, `.viewer-stage`, `.viewer-inspector`, or any container conditioned on placement/interaction. (`opacity` in the CSS only appears on `:disabled` buttons and small labels.)
2. **No global full-window darkening rule** in `styles/global.css`, `styles/tokens.css`, `index`/`App`/`main` CSS, or any route CSS.
3. **No imperative darkening.** Nothing sets `document.body`/`documentElement` styles, and no code creates a full-screen overlay element. The only imperatively-created DOM nodes are small `pointer-events:none` decorator labels (`RoomPlanDecorator`, `ClinicalProgramDecorator`).
4. **The placement path changes NO Bentley display state.** `MrtAssetPlacementTool` (onPostInstall / onDataButtonDown / onResetButtonUp / onCleanup / exitTool) and `spatialAssetOverlay.beginPlacementForLibraryEntry` / `cancelPlacement` do **not** touch `viewFlags`, `displayStyle`, `featureOverrideProvider`, emphasis, hilite, flash, transparency, render mode, never-drawn, or canvas CSS. The overlay header explicitly states it does not modify ViewFlags/camera/transparency.
5. **`.viewer-stage` background is near-black** (`#0b0e14`). When the Bentley canvas content is not painting, the stage shows this dark background. The **2D floor plan** panel (`.bim2d-plan`) is translucent with `backdrop-filter: blur(4px)`, so it visually darkens together with whatever is behind it — consistent with a scene/canvas darkening rather than a DOM overlay covering it.

**Implication:** the cause is very unlikely to be a CSS class or a placement-code mutation. It is most consistent with either (a) a Bentley scene/canvas display state, or (b) a DOM layer that only the live `elementsFromPoint` stack can name. Both are exactly what the built diagnostic captures. I deliberately did **not** patch on this inference — the spec requires live proof.

---

## 4. THE INSTRUMENTED DIAGNOSTIC (built, wired, tested)

A DEVELOPER-only, **READ-ONLY** diagnostic was added. It captures the spec's §2–§11 evidence in one snapshot per invocation, with no mutation and no secrets.

**New module** `frontend/src/components/spatial/placementDarkeningDiagnostic.ts`:
- `capturePlacementDarkeningSnapshot(...)` records, from the LIVE DOM:
  - **§2 placement state** (read, not inferred): `placementModeActive`, intent present/summary, interaction state, `openPanel`, pending asset, candidate, placement-tool-active, active Bentley tool id, selectedAppObject.
  - **§3 viewport element**: real `.viewer-stage` host + `canvas`, bounding rect, center point.
  - **§4 `document.elementsFromPoint(centerX, centerY)`** — the full top→bottom stack, each with tagName/id/className/rect/z-index/position/pointer-events/background/background-color/opacity/filter/backdrop-filter/visibility/display, plus canvas relation (IS/CONTAINS/ABOVE canvas) and whether it covers the viewport.
  - **§5 all full-viewport elements** anywhere in the document (any name; not limited to backdrop/overlay/modal) with the same styles.
  - **§8/§9 common-ancestor chains** of the 3D viewport, the 2D floor plan, and the inspection panel (to catch a shared opacity/filter/background above all three).
  - **§7 Bentley view state** (injected via `readBentleyViewStateForDiagnostic`): render mode, `viewFlags.transparency`/`lighting`, feature-override provider count, always/never-drawn counts, selection active, display-style name, background color, **canvas CSS opacity + filter**.
  - **§10 pointer receiver**: `document.elementFromPoint(center)` — which element actually receives the pointer.
- `classifyDarkening(...)` maps the captured evidence to the spec's classification set: `ORPHANED_DOM_OVERLAY` / `COMMON_ANCESTOR_OPACITY` / `COMMON_ANCESTOR_FILTER` / `POINTER_INTERCEPTION_LAYER` / `PLACEMENT_STATE_NOT_IDLE` / `BENTLEY_DISPLAY_STATE_NOT_RESTORED` / `NO_DARKENING_EVIDENCE` (and supports `MULTIPLE_INDEPENDENT_DEFECTS` via multiple returned causes).
- `formatDarkeningSnapshot(...)` renders a bounded, secret-free report for the Developer Inspector.

**Live readers (read-only, no mutation):**
- `spatialAssetOverlay.readPlacementStateForDiagnostic()` — store + live active Bentley tool.
- `LiveItwinViewer.readBentleyViewStateForDiagnostic()` — viewFlags/emphasis/selection/display-style/background + Bentley canvas CSS opacity & filter.

**Wired into the DEV drawer** (`BentleyViewer.tsx`, Developer mode only), three buttons that write the snapshot to the Developer Inspector:
- `DIAGNOSE — NORMAL`
- `DIAGNOSE — PLACEMENT ACTIVE`
- `DIAGNOSE — AFTER CANCEL (DARK)`

The diagnostic is temporary/Developer-only per §6/§11 and can be removed once the defect is fixed.

---

## 5. HOW TO CAPTURE THE PROOF (live, one authenticated session)

The decisive `elementsFromPoint` / Bentley-view capture requires the authenticated live viewer (the only place the Bentley canvas exists). It cannot run headlessly. Steps:

1. Open `http://localhost:3000/viewer`, sign in, enable **Developer mode** (top-right).
2. Open the Developer tools drawer; click **DIAGNOSE — NORMAL**. Copy the Inspector output (state A).
3. Select Discovery MI → **PLACE IN MODEL**; click **DIAGNOSE — PLACEMENT ACTIVE** (state B).
4. Cancel placement; while the viewport is still dark, click **DIAGNOSE — AFTER CANCEL (DARK)** (state C).
5. Compare A vs B vs C. The `[ROOT-CAUSE CLASSIFICATION]` line names the proven cause; the `[ELEMENTS-FROM-POINT]`, `[FULL-VIEWPORT ELEMENTS]`, `[COMMON ANCESTOR DIMMERS]`, and `[BENTLEY VIEW STATE]` sections give the exact evidence (element name / z-index / opacity / filter, or the changed view flag).

**§6 decisive DOM-overlay toggle:** if the AFTER_CANCEL stack shows a dimming element `ABOVE_CANVAS` covering the viewport, toggle its `display:none` in DevTools; if brightness/pointer return, that element is proven the cause. If NO foreign layer is above the canvas (§7), the `[BENTLEY VIEW STATE]` section vs NORMAL identifies the stale view flag / canvas CSS.

---

## 6. ROOT-CAUSE CLASSIFICATION — STATUS

**PENDING LIVE CAPTURE.** Based on the static proof (§3), the field is narrowed to one of:
- `BENTLEY_DISPLAY_STATE_NOT_RESTORED` (most consistent: 2D plan darkens with the scene via its `backdrop-filter`; no CSS/DOM darkener found), or
- `ORPHANED_DOM_OVERLAY` / `COMMON_ANCESTOR_*` (only if the live `elementsFromPoint`/ancestor capture reveals a layer or shared dimmer not visible in source — which the instrument will name exactly).

I have deliberately NOT asserted a single cause without the live evidence, per the spec's "STOP GUESSING / FIRST PROVE" directive.

---

## 7. TESTS / BUILD / VIEWER

- **New tests:** `frontend/src/tests/placementDarkeningDiagnostic.test.ts` — **12 passing**. They prove the instrument reports truthfully: `isDarkeningContributor` flags opacity<1 / filter / backdrop-filter / translucent rgba; `classifyDarkening` correctly returns each cause (ORPHANED_DOM_OVERLAY, COMMON_ANCESTOR_OPACITY, PLACEMENT_STATE_NOT_IDLE, BENTLEY_DISPLAY_STATE_NOT_RESTORED, NO_DARKENING_EVIDENCE); jsdom capture finds the host/center/canvas relation.
- **Typecheck:** `npx tsc -b` → PASS.
- **Full frontend suite:** **85 files / 1306 tests, all passing** (baseline 84/1294; +1 file, +12 tests; zero regressions).
- **Production build:** `npm run build` → PASS (warnings pre-existing, unrelated).
- **Viewer:** `/viewer` = **200** on `:3000`; dev server left running.

---

## 8. WHAT HAPPENS AFTER PROOF (§13, not yet done)

Once the live capture names the exact owner of the stale state, apply the **minimum** correction to that owner only (e.g. restore the one changed Bentley view flag, or remove/teardown the one named DOM element) — no new placement state machine, no new backdrop, no broad Bentley reset. Then add a regression (§14) reproducing PLACE → cancel → placement IDLE → no darkening element/state remains → pointer reaches viewport, and re-run the full suite/build/viewer.

---

## 9. MANUAL ACCEPTANCE (§15)

`http://localhost:3000/viewer` is left running. Not self-accepted. The manual sequence (normal → PLACE → Esc → normal brightness immediately → orbit/pan immediately, ×3; then PLACE → cancel via non-Escape → normal) is the acceptance gate AFTER the proven fix.

**`manual_acceptance = PENDING`.**

---

## 10. STOP

Diagnostic instrument built, wired, and tested; static narrowing complete; live-capture instructions provided. Stopping here per §16. Did NOT begin Build 1C or Build 2. Awaiting the live capture (or your go-ahead to apply the minimum fix once the capture names the owner).

*End of EVI-MA-07A.1 diagnostic report.*
