# MRT Pharma — Build 1B Manual Acceptance Correction

## B1B-MA-02 — Upper-Storey Walkthrough Spawn Below / Intersecting Floor Slab

**Status:** IMPLEMENTED / AUTOMATED GREEN / MANUAL RETEST REQUIRED
**manual_acceptance:** PENDING
**build_1b_marked_complete:** false
**Baseline commit:** `1de2c5b0d01e3a69e0c5a744b1d58ae1f3526bd3` (branch `main`)

This correction continues from the current working tree only. Build 1A and Build 1B
are not restarted, reverted, redesigned, or reimplemented. No Build 2 scope. Nothing
is staged, committed, or pushed.

---

## 1. Defect

Reproduction: **2C17 PROSTH. LAB → Radiopharmacy (Second Floor) → Enter Walkthrough Here.**

The targeted "Enter Walkthrough Here" for an upper-storey clinical room started the
camera at (or below) the whole-model band datum — roughly the ground/first floor —
instead of at pedestrian eye height standing on the selected room's floor. The result
was the camera spawning **below / intersecting the second-floor slab**.

Ground/first-floor rooms did not show the defect, which is why it survived to manual
acceptance: for a ground-floor room the band datum ≈ the room floor.

---

## 2. Root cause (proven from source)

The targeted-spawn **pipeline is correct end to end into the controller**:

- `resolveClinicalRoomWalkthroughSpawn` derives the floor from the authoritative room
  footprint (`fp.volume?.zLow ?? fp.floorZ`), adds `WALKTHROUGH_EYE_HEIGHT_M`
  (`cameraNav`), and rejects wrong-storey rooms via `programStoreyRanges`.
- `resolveTargetedWalkthroughSpawn` returns `spawn.z = roomFloorZ + eyeHeight`.
- `enterWalkthrough` sets the initial camera position (`start`) to that override correctly.

The bug was **one line downstream**, in `walkthroughController.enterWalkthrough`:

- The per-session **`floorElevation`** (the Z the camera is pinned to) was taken from the
  **whole-model storey-band datum** (`chosen.zLow` from `loadStoreys` Z-banding), **not**
  from the supplied targeted spawn.
- `applyCamera` re-derives the eye Z **every frame** via
  `eyeZForFloor(floorElevation, WALKTHROUGH_EYE_HEIGHT_M)`.
- So the correct upper-storey `spawn.z` was **overwritten on the first frame** by the low
  band datum → the camera dropped below/through the slab.

---

## 3. Fix (minimum, reuses existing authorities)

**Location:** `frontend/src/components/spatial/walkthroughController.ts` (`enterWalkthrough`).

A pure, `@itwin`-free helper was extracted so the runtime and the tests share one
implementation:

```ts
// frontend/src/components/spatial/walkNav.ts
export function resolveWalkthroughFloorElevation(input: {
  spawnOverrideZ?: number
  eyeHeight: number
  storeyFloorZ: number
}): number {
  if (Number.isFinite(input.spawnOverrideZ) && Number.isFinite(input.eyeHeight)) {
    return (input.spawnOverrideZ as number) - input.eyeHeight
  }
  return input.storeyFloorZ
}
```

The controller now derives the floor elevation from this helper:

```ts
const floorZ = resolveWalkthroughFloorElevation({
  spawnOverrideZ: hasOverride ? spawnOverride!.z : undefined,
  eyeHeight: WALKTHROUGH_EYE_HEIGHT_M,
  storeyFloorZ,
})
```

When a targeted spawn is supplied, `floorElevation = spawnOverride.z − eyeHeight`, which
**reconstructs the selected room's own floor exactly** using the same canonical eye
height the resolver applied. `applyCamera`'s `eyeZForFloor(floorElevation, eye)` then
reproduces `spawn.z` on entry and keeps it pinned there through forward/strafe/turn — no
vertical drift, no snap to the first floor, no slab pass-through. When there is no
override (generic entry), it falls back to the storey-band datum (prior behavior).

### Authorities (all reused, none duplicated)
- **Room floor:** `fp.volume?.zLow ?? fp.floorZ`, reconstructed exactly via `spawn.z − eye`.
- **Eye height:** `cameraNav.WALKTHROUGH_EYE_HEIGHT_M` — a single shared constant used by
  both the resolver and the camera. No second eye-height authority was introduced.
- **Storey membership:** `programStoreyRanges` rejection in the resolver (unchanged).

### What was deliberately NOT done
- No disabling/weakening of the floor constraint (it stays active).
- No vertical-fly controls; pitch rotates the view only — still a floor-constrained pedestrian.
- No change to `targetedWalkthroughSpawn.ts` (it was already correct).
- No hardcoded global Z.

---

## 4. Spawn Z: before vs after

| | Initial `start` | Per-session `floorElevation` | Per-frame eye Z | Result |
|---|---|---|---|---|
| **Before** | `spawnOverride` (correct) | `chosen.zLow` (whole-model band) | `eyeZForFloor(band, eye)` | below the upper slab |
| **After** | `spawnOverride` (correct) | `spawnOverride.z − eye` (room floor) | `eyeZForFloor(roomFloor, eye) == spawnOverride.z` | eye height inside the room |

---

## 5. Tests added

New file: `frontend/src/tests/build1bB1bMa02WalkthroughSpawn.test.ts` — **9 tests**.

- **(a)** Upper-storey targeted `spawn.z ≈ roomFloorZ + eyeHeight`, and the old storey-band
  pin is *proven* to land below the second-floor slab.
- **(b)** Same-XY rooms on different storeys produce **distinct** camera Z separated by the
  storey gap — fails if both collapse to a single global Z.
- **(c)** Irregular/concave (L-shaped) upper-storey room: resolved interior XY is inside the
  footprint and Z sits on the correct storey.
- **(d)** Post-spawn floor constraint is invariant across simulated XY movement: eye Z stays
  `== spawn.z`, above the slab, with zero vertical drift.
- **(e)** Spawn point in-room **and** a representative equipment envelope in-room
  (containment sanity; spawn is room-derived, equipment is never the authority).
- **Seam tests (×4):** override path (`spawn.z − eye`), no-override fallback, non-finite
  fallback (bad override / bad eye), and the exact round-trip
  `eyeZForFloor(resolveFloor(spawnZ), eye) === spawnZ`.

The 16 general spawn sub-properties in `build1bSpatialCorrection.test.ts` are unchanged.

---

## 6. Regression preserved

- **B1B-MA-01** (2D18 TECH. OFFICE → PET/CT Scanner Room → GE HealthCare Discovery MI,
  parent-derived containment PASS, LOCKED, persistence): green, untouched.
- **Scanner acceptance / equipment gate / canonical identity:** unchanged.
- **All prior walkthrough suites** (walkNav, firstPerson, cameraNav, Build 1A walkthrough):
  green.

---

## 7. Verification

| Check | Result |
|---|---|
| Typecheck (`tsc -b`) | PASS |
| Test files (baseline → after) | 62 → 63 |
| Tests (baseline → after) | 1018 → 1027 (+9, 0 failures) |
| Production build | PASS |
| Worker head (`parse-imdl-worker.js`) | `(()=>{"use strict";f` |
| WASM magic (`draco_decoder.wasm`) | `0061 736d` |
| `@itwin/core-frontend` | 5.12.5 |
| `/viewer` HTTP | 200 |
| Dev server | restarted clean on port 3000 |

---

## 8. Scope review

- Changes confined to `frontend/`: `walkNav.ts`, `walkthroughController.ts`, and the new
  test file.
- **0** `.py` / closed-domain changes made by this fix. Two untracked `.py` files
  (`transport_connectivity_composition_authority.py`,
  `test_transport_connectivity_composition_authority.py`) pre-date this session and are
  unrelated.
- `frontend/.env` remains ` M` (pre-existing, unstaged) — not modified by this fix.
- Nothing staged, committed, or pushed.

---

## 9. Manual retest steps (for user acceptance)

1. Load the MRTway Medical Clinic Demo; confirm `/viewer` renders at
   `http://localhost:3000/viewer`.
2. Select the **2C17 PROSTH. LAB** clinical function and its **Radiopharmacy** room on the
   **Second Floor**.
3. Click **Enter Walkthrough Here**.
4. Confirm the camera starts at standing eye height **inside** the room, on top of the
   second-floor slab (not below / through it).
5. Walk forward/back/strafe and turn: the eye height stays constant on the second-floor
   plane — no drop to the first floor, no slab pass-through.
6. **Regression:** repeat B1B-MA-01 (2D18 TECH. OFFICE → PET/CT Scanner Room → Discovery MI)
   and a ground-floor **Enter Walkthrough Here** to confirm both still behave correctly.

---

## 10. Limitations

- The room floor is reconstructed as `spawn.z − eye`; this is exact **because** the resolver
  and the camera share the single `WALKTHROUGH_EYE_HEIGHT_M` constant. The round-trip test
  guards that invariant.
- Generic (non-targeted) walkthrough entry still uses the storey-band datum — correct for
  whole-model entry and out of scope here.
- Targeted storey membership is still decided upstream by `programStoreyRanges`; this fix
  only ensures the controller honors the room floor the resolver already validated.

**Build 1B is NOT marked complete. Ledger/authority index NOT advanced.
manual_acceptance = PENDING pending the manual retest above.**
