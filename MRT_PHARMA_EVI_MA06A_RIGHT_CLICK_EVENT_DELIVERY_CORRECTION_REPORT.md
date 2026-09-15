# EVI-MA-06A — Right-Click Event-Delivery Correction (manual-acceptance failure fix)

**Status:** implementation complete · `manual_acceptance = PENDING` (do not self-accept)
**Trigger:** manual acceptance of EVI-MA-06 FAILED — physical right-click on visible application-owned geometry did not open the context menu. The unified picker was NOT complete; pure-picker tests proved nothing about live event delivery.

---

## 1. Reconcile

Branch `main`, HEAD `1de2c5b`, origin/main `1de2c5b`, 0/0. Uncommitted EVI work preserved (no reset/revert/ZIP). EVI-MA-06 unified picker/domain kept; only the event-delivery layer is corrected.

## 2. Instrumented live chain: DOM event → viewport → ray → AppObjectPickTarget → menu store → React

I instrumented every stage with structured DEV diagnostics (`ContextMenuBridgeDiagnostic`, stages `EVENT_RECEIVED → GESTURE_ACTIVE_SKIP | NO_RAY | NO_TARGET | MENU_OPENED`, plus a bounded ring accessible via `getAppContextMenuDiagnostics()`), rather than changing any picking mathematics.

## 3. First failed stage (proven): EVENT_RECEIVED never fired

The DOM `contextmenu` event never reached a listener. Root cause: the right-click bridge lived **inside `MrtDirectManipulationTool`** — installed in `onPostInstall`/`onDataButtonDown`, removed in `onCleanup`. Bentley's `ToolAdmin` routinely activates the **view-navigation tool** after camera orbit/pan, on viewport focus changes, and whenever the primitive tool was never armed. Each such switch runs the primitive tool's `onCleanup`, which called `removeEquipmentContextMenuBridge()` and detached the only `contextmenu` listener. So after essentially any camera interaction — or before any left-click armed the tool — there was **no listener at all**, and right-click was a no-op. This exactly matches the reported "worked, failed, worked again, depended on viewport/tool lifecycle" behaviour. The picking mathematics downstream were never reached, so they were never the problem.

## 4. Fix: a TOOL-INDEPENDENT viewport-lifetime bridge

New module `appObjectContextMenuBridge.ts` binds a single capture-phase `contextmenu` listener to the **viewport host element**, for the **lifetime of the viewport**, independent of which Bentley tool is active. It is installed/torn down by the overlay's `setActiveProductViewport(vp)` — the same hook the viewer already uses to register/deregister its live `ScreenViewport` on view open/dispose — so it survives every tool switch and camera move and is re-installed idempotently on viewport remount.

The bridge only owns DOM event → `clientToRay` → `resolveAppObjectAtRay` → open the correct menu store (equipment vs vestibule) + select. The picker math, resolution, and menu store are unchanged and injected, keeping the bridge thin and DOM-testable.

The former tool-owned bridge is disabled (`installEquipmentContextMenuBridge` is now a no-op) so there is exactly ONE capture-phase listener — no double-handling / `stopPropagation` race. `onResetButtonUp` remains as a tool-native secondary path when the primitive tool happens to be active.

## 5. Scanner / cyclotron / vestibule tested separately

The DOM-level test dispatches a REAL `contextmenu` MouseEvent against an actual jsdom viewport host and asserts the menu-open store call carries the exact instance id for each family: scanner (`EQUIPMENT_INSTANCE`), cyclotron (`EQUIPMENT_INSTANCE`), and vestibule (`CLINICAL_LOGISTICS_VESTIBULE`). It also proves: the listener persists across repeated events (simulated tool switches), a dispose removes it, empty/native-BIM right-click closes app menus and does NOT suppress the browser menu, a gesture-active event is skipped, and the structured diagnostic records the first reached stage (including `NO_RAY`).

## 6. Diagnostics disposition

The per-event `console.info('[rc-bridge] ...')` trace is DEV-gated (`import.meta.env.DEV`). The structured `ContextMenuBridgeDiagnostic` ring (`getAppContextMenuDiagnostics()`) is retained as the useful structured diagnostic for future triage; it is bounded (≤50) and PII-free. No verbose per-frame logging remains.

## 7. Files

**New:** `appObjectContextMenuBridge.ts`, `eviMa06RightClickBridgeDom.test.ts` (8 DOM-level tests).
**Modified:** `spatialAssetOverlay.ts` (viewport-lifetime bridge install/teardown in `setActiveProductViewport` + diagnostics ring), `MrtDirectManipulationTool.ts` (tool-owned bridge install neutralized to a no-op).

## 8. Verification

| Check | Result |
|---|---|
| `npx tsc -b` | PASS |
| DOM right-click bridge suite | 8 passed |
| Full frontend suite | **80 files / 1254 tests — all pass** (was 79 / 1246; +1 file, +8 tests) |
| `npm run build` | PASS (pre-existing warnings only) |
| `/viewer` on :3000 | 200 |

Dev server left running on **port 3000**.

> Honesty note: this is now proven at the DOM-event level (a real `contextmenu` event opens the menu store with the correct id) and by the tool-independent lifetime binding, which directly addresses the diagnosed failure. Final confirmation that the menu is visible in the LIVE Bentley browser for scanner, cyclotron, and vestibule remains the manual-acceptance step.

## 9. Manual acceptance — `manual_acceptance = PENDING`

In the live viewer: orbit/pan the camera (to force Bentley tool switches), then right-click a scanner, a cyclotron, and the vestibule — each must open its correctly-titled menu at the cursor without requiring a prior left-click or an active tool. Right-click native BIM must show no app menu.

**Do not self-accept.** Do not begin Build 1C or Build 2.
