# MRT PHARMA — EVI-MA-07A

## PLACEMENT-MODE ESCAPE / BACKDROP RECOVERY — CORRECTION REPORT

- **Correction:** EVI-MA-07A (placement-state lifecycle only)
- **Branch:** `main`
- **HEAD:** `1de2c5b0d01e3a69e0c5a744b1d58ae1f3526bd3`
- **origin/main:** identical (0 ahead / 0 behind)
- **Working tree:** preserved — prior EVI work and Build 1B.9 deliverables intact (no reset, no revert).
- **`manual_acceptance = PENDING`** — not self-accepted. Awaiting live manual verification.
- **Scope guard:** placement-state lifecycle only. Did NOT begin Build 1C, Build 2, physics/economics, routing, or animation.

---

## 1. RECONCILE

Recorded before any change:
- Branch `main`, HEAD `1de2c5b0d01e3a69e0c5a744b1d58ae1f3526bd3`, origin/main identical.
- 141 uncommitted paths present (prior EVI + Build 1B.9 audit deliverables). All preserved.
- Frontend baseline: 82 test files / 1274 tests passing, `tsc -b` PASS, `npm run build` PASS, `/viewer` = 200 on `:3000`.

No prior work was reset or reverted.

---

## 2. THE ACTUAL STATE MACHINE (traced, not guessed)

I traced every state involved in PLACE IN MODEL through the real code (via a focused codebase investigation), not from CSS:

- **Single source of truth for "placement is active":** `SpatialAssetStore.intent` (`frontend/src/domain/assets/spatialAssetStore.ts`). Derived snapshot fields `placementModeActive` / `placementIntent`; interaction state `'PLACING'`. `beginPlacement()` sets `intent`; `cancelPlacement()` clears **only** `intent`; `completePlacementAt()` consumes it.
- **Placement enter/cancel path:** `spatialAssetOverlay.beginPlacementForLibraryEntry()` / exported async `cancelPlacement()` — starts/stops the Bentley `MrtAssetPlacementTool` and toggles store intent. It touches **no** React panel state and installs **no** DOM overlay.
- **Bentley tool** (`MrtAssetPlacementTool.ts`): `onResetButtonUp` (right-click) and `onCleanup` (Esc/tool cancel) clear store intent only.

**The full-screen dimming/blocking element — the root cause.** There is exactly ONE full-viewport layer that can trap the viewport: `.viewer-panel-backdrop` (`frontend/src/routes/BentleyViewer.tsx`, `BentleyViewer.css`):
- `position:absolute; inset:0; z-index:1200; background: transparent; pointer-events:auto;`
- It is mounted **solely** on `openPanel` being truthy (an open floating tool panel), and its `onPointerDown` dispatches `OUTSIDE_CLICK` to close the panel.

**There is no placement-specific backdrop at all.** `placementModeActive` (store intent) and `openPanel` (React panel visibility) were **fully decoupled**:
- Entering placement never set `openPanel`.
- Cancelling placement (any path — UI Cancel, right-click, Esc-through-tool) cleared placement state but **never cleared `openPanel`**.
- The app's only Escape handler that could dismiss the backdrop was itself **gated on `openPanel`** and unaware of placement.

**The orphan trap:** if a floating tool panel was open when the user entered/exited placement, cancelling placement correctly showed "Placement cancelled" but left the transparent `.viewer-panel-backdrop` mounted (because `openPanel` was still set). With `pointer-events:auto` across the whole stage, the Bentley canvas beneath became unreachable — the viewport appeared blocked/frozen, and the placement Escape path (Bentley tool `onCleanup`) had zero effect on `openPanel`, so Escape did not recover it. That is precisely the reported live failure.

---

## 3. ONE AUTHORITATIVE PLACEMENT STATE (§3)

`placementModeActive` (derived from `SpatialAssetStore.intent`) is already the single authority; I did **not** introduce a competing boolean. Normal viewer state = placement IDLE. The shell now mirrors this one flag into React via an event-driven subscription (`subscribeSpatialAssets`, no polling) so the app shell can react to it.

Mapped to the requested `PlacementSession` concept: `status = IDLE` ⇔ `intent === undefined`; any non-IDLE phase ⇔ `intent !== undefined`. The full-screen treatment may exist only while the session is non-IDLE — enforced by §7 below.

---

## 4. CANCEL IS ATOMIC (§4, §6)

All cancellation paths route through the ONE `cancelPlacement()` (`spatialAssetOverlay.cancelPlacement()` → `spatialAssetStore.cancelPlacement()` + `exitMrtAssetPlacementTool()`), which clears the placement intent and exits the Bentley tool. No separate partial-cleanup function exists. After cancel, the session is truly IDLE. "Placement cancelled" now means IDLE **and** no orphaned block layer (§7).

---

## 5. ESCAPE — APP-STABLE, MANDATORY (§5)

Added an **app-stable** Escape handler in `BentleyViewer.tsx`, installed at `window` level in the **capture phase**, always mounted post-auth (NOT gated on `openPanel`, NOT dependent on Bentley's active Tool). Its behavior is decided by the pure helper `decideEscapeRecovery` (`frontend/src/components/spatial/placementEscapeRecovery.ts`):

- If placement is active → call the ONE `cancelPlacement()`.
- If a floating panel/backdrop is open → dispatch `ESCAPE` to close it.
- Both in a **single** Escape press (atomic recovery) → normal viewer restored immediately, no refresh.
- Escape is **not** hijacked while typing in `input` / `textarea` / `select` / contentEditable.

This replaces the old `openPanel`-gated Escape effect (which could not rescue an orphaned backdrop relative to placement).

---

## 6. BACKDROP NEVER ORPHANED + BACKDROP UX (§7, §8)

Two enforcement points, both derived directly from the authoritative state:

1. **`backdropMayMount({ hasOpenFloatingPanel, placementModeActive })`** now gates the `.viewer-panel-backdrop`. It returns true **only** for an open panel with NO active placement. The backdrop can therefore never coexist with an armed placement session, and it disappears automatically the instant placement state returns to IDLE — no explicit second cleanup.
2. **`shouldCloseFloatingPanelOnPlacementArmed(...)`**: the moment placement is armed, any open floating panel is closed (`setOpenPanel(null)`), removing the only source of a full-viewport backdrop during placement.

**UX (§8):** during spatial placement the BIM is **not** dimmed — there is no placement backdrop, and the panel backdrop is suppressed while placing, so the user sees the building clearly. Placement guidance remains the subtle `.mrt-placement-status` banner ("Placing: … / Click a location / Right-click or Esc to cancel"). The (panel-only) backdrop remains transparent and, when present, never blocks placement because it cannot be present during placement.

---

## 7. SELECTION / EXISTING ASSETS UNAFFECTED (§11)

`cancelPlacement()` clears only the temporary placement intent (and exits the tool). It does not delete/move existing equipment or clear unrelated persisted state — verified by test I (placed-asset count unchanged across arm→cancel). This preserves the established editor policy.

---

## 8. CHANGES MADE (minimal placement-state lifecycle only)

New:
- `frontend/src/components/spatial/placementEscapeRecovery.ts` — pure, Bentley-free decision helpers: `decideEscapeRecovery`, `backdropMayMount`, `shouldCloseFloatingPanelOnPlacementArmed`.
- `frontend/src/tests/placementEscapeRecovery.test.ts` — 12 pure decision tests.
- `frontend/src/tests/placementEscapeRecoveryDom.test.tsx` — 8 DOM-level tests (real `keydown` Escape).

Modified:
- `frontend/src/routes/BentleyViewer.tsx` — (a) subscribe to `placementModeActive`; (b) close open panel when placement arms; (c) app-stable capture-phase Escape recovery (replacing the old openPanel-only Escape effect); (d) gate `.viewer-panel-backdrop` with `backdropMayMount`.

No changes to picking mathematics, geometry, physics, economics, routing, or animation.

---

## 9. DOM TESTS (§12 A–I)

`placementEscapeRecoveryDom.test.tsx` drives **real** DOM `keydown` Escape events against a harness that wires the same three helpers the shell uses, against a mocked overlay (so vitest never imports the @itwin stack — project pattern). Proven:
- **A** PLACE IN MODEL → placement ARMED → placement UI visible.
- **B** Escape → IDLE → backdrop gone.
- **C** `cancelPlacement()` called (spy) — all temporary placement state cleared.
- **D** "Placement cancelled" leaves no dim/block layer.
- **E** Escape works with no Bentley tool involved (window-level, tool-independent).
- **F** Escape while focus is over the Asset Library still cancels.
- **G** Escape while focus is over the viewport (no text field) still cancels.
- **H** Re-enter placement after cancel works 3× with no orphaned state/backdrop.
- **I** Existing placed assets unchanged by cancel.

`placementEscapeRecovery.test.ts` additionally proves the backdrop never coexists with placement, atomic recovery, non-Escape/text-field guards, and pointer/tool independence.

---

## 10. TEST / BUILD / VIEWER RESULTS

- **Typecheck:** `npx tsc -b` → PASS.
- **New tests:** `placementEscapeRecovery.test.ts` (12) + `placementEscapeRecoveryDom.test.tsx` (8) = **20 passing**.
- **Full frontend suite:** **84 files / 1294 tests, all passing** (baseline was 82/1274; +2 files, +20 tests — my additions; zero regressions).
- **Production build:** `npm run build` → PASS (`✓ built`). Warnings are pre-existing (chunk size + ineffective-dynamic-import notices), unrelated to this change.
- **Viewer:** `/viewer` = **200** on `:3000`; dev server left running (`term_1789324313590_4582g2z3rx4`).

---

## 11. MANUAL ACCEPTANCE (§13)

`http://localhost:3000/viewer` is left running for the manual sequence:
1. Select Discovery MI. 2. Click PLACE IN MODEL. 3. Viewer stays clearly visible (no heavy dim). 4. Press Escape. 5. Placement UI disappears immediately. 6. Viewer returns to normal brightness. 7. Orbit/pan works immediately. 8. Start placement again. 9. Cancel again. 10. No refresh required. 11. Repeat 3× — no orphaned listener/state.

**Honest note:** the recovery logic, the backdrop-derivation, and the app-stable Escape are proven at the pure-decision and DOM-event level (real `keydown` on `window`, real backdrop mount/unmount assertions). Confirmation in the live browser against the actual Bentley canvas is the manual step above.

**`manual_acceptance = PENDING`.**

---

## 12. STOP

Tests and build are green. Stopping here per instruction. Did NOT begin Build 1C, Build 2, the physics/economics audit, routing, or animation. Awaiting manual acceptance.

*End of EVI-MA-07A report.*
