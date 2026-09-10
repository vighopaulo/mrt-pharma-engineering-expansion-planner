# MRT Pharma — September 9 Authority Consolidation / Repository Reconciliation Report

**Checkpoint:** repository `main`, HEAD
`bdd2103d7e4e189625a6c725bc81e166754df730`
(*"MRT Pharma: checkpoint BIM spatial and clinical-program foundation"*),
`origin/main` identical, divergence `0 0`. Working tree clean except the
intentionally-unstaged `frontend/.env`.

**Nature:** DOCUMENTATION / AUTHORITY RECONCILIATION ONLY. No product-engine or
product-UI behavior changed. Every classification was verified against the
physical repository (frontend `.ts/.tsx` + backend `.py` source and tests), not
from report `.md` files or session memory.

**Authorized edits this task:** `MRT_PHARMA_AUTHORITY_INDEX.md` (September 9
addendum), `MRT_PHARMA_OPEN_GAPS.md` (September 9 section), and this report pair.

---

## 1. Domain status matrix

Status vocabulary per `MRT_PHARMA_AUTHORITY_INDEX.md` §R.1.

| # | Domain | Status | Canonical owner (source) |
|---|---|---|---|
| A | Bentley / BIM / Spatial (live viewer) | `IMPLEMENTED_AND_INTEGRATED` | `LiveItwinViewer.tsx`, `projectBim.ts`, `authoritativeRoomGeometryProbe.ts` |
| B | Clinical Program | `IMPLEMENTED_AND_INTEGRATED` (full PET dept NO) | `clinicalProgram.ts`, `clinicalProgramOverlay.ts`, `ClinicalProgramControl.tsx` |
| C | Equipment | `IMPLEMENTED_DOMAIN_AUTHORITY` (not bound to clinical volume/live room) | `scanner_catalog.py`, `cyclotron_catalog.py`, `generator_catalog.py`, asset system |
| D | Spatial Routing | `IMPLEMENTED_DOMAIN_AUTHORITY` (live-geometry seam open) | `canonical_spatial_authority.py`, `human_circulation_authority.py` |
| E | Transport Technologies | `IMPLEMENTED_DOMAIN_AUTHORITY` | `transport_technology_authority.py`, five-mode authorities |
| F | MRT Infrastructure | `IMPLEMENTED_DOMAIN_AUTHORITY` | `mrt_auxiliary_systems_authority.py`, `mrt_carrier_fleet.py` |
| G | Patient / Clinical Demand | `IMPLEMENTED_DOMAIN_AUTHORITY` (live ARIA PLANNED) | `patient_radionuclide_demand.py`, `inbound_patient_program.py` |
| H | Cyclotron / Radiopharm. Production | `IMPLEMENTED_DOMAIN_AUTHORITY` / `PARTIAL` calibration | `cyclotron_production_estimation_authority.py` |
| I | Operations / Scheduling | `IMPLEMENTED_DOMAIN_AUTHORITY` (long→day seam PARTIAL) | `long_horizon_operational_planning.py`, `operational_day_orchestrator.py` |
| J | Simulation (engine) | `IMPLEMENTED_DOMAIN_AUTHORITY` | `existing_facility_baseline_simulation.py`, `live_operational_state.py` |
| K | Dynamic Trajectories | `IMPLEMENTED_DOMAIN_AUTHORITY` (RP-PTS sampler PARTIAL) | `production_trajectory_authority.py`, `operational_day_trajectory_scene.py` |
| L | Optimization / Capital Project | `IMPLEMENTED_DOMAIN_AUTHORITY` (free composition PLANNED) | `whole_oncology_four_architecture_optimization.py`, `equal_budget.py` |
| M | Economics | `IMPLEMENTED_DOMAIN_AUTHORITY` / `PARTIAL` calibration | `equipment_opex_authority.py`, `lifecycle_economics.py`, `infrastructure_*.py` |
| N | What-If / Lockdown / Lineage | `IMPLEMENTED_DOMAIN_AUTHORITY` (live UI PLANNED) | `lockdown_what_if_lineage_authority.py` |
| O | OpenUSD | `IMPLEMENTED_ADAPTER_OR_EXPORT` | `openusd_spatial_adapter.py` (zero `omni` imports) |
| P | NVIDIA / Omniverse runtime | `PLANNED` | — (no Kit/Nucleus/RTX/Isaac) |
| Q | Reporting / Export | `IMPLEMENTED_DOMAIN_AUTHORITY` (unified product report PLANNED) | `architecture_report.py`, `comparable_project_report.py`, engineering reports |
| R | UI/UX / Product Integration | `PARTIAL` — LIVE_BENTLEY_AND_CLINICAL_WORKFLOW_INTEGRATED=YES; END_TO_END_PRODUCT_WORKFLOW_INTEGRATED=NO | `BentleyViewer.tsx`, `spatialAssetOverlay.ts` |

**True 3D spatial authority chain (physical clinical planning):** authoritative
IfcSpace geometry → `ClinicalPlanningVolume` (oriented prism, contained) → range/
bbox as `DIAGNOSTIC_ONLY` fallback → labels as annotations → screen space never
authoritative.

## 2. Closed / partial / open gap summary

- **PARTIALLY_CLOSED / reworded:** OG-BEN-1 (live viewer + Project BIM + IfcSpace
  read now integrated; automated connection + backend ingestion open),
  OG-FIN-1 (reworded: viewer geometry read ≠ engineering-model file parser).
- **New gaps:** OG-FE-1 (Build 2B live composition, MANUAL_ACCEPTANCE_PENDING),
  OG-FE-2 (full PET dept, PLANNED), OG-FE-3 (equipment↔clinical-volume binding,
  PLANNED), OG-ROUTE-INT (live geometry→routing integration, PLANNED),
  OG-WIF-UI (What-If/Lockdown product UI, PLANNED).
- **Still open (unchanged):** OG-CAP-1/2, OG-OPS-1, OG-ARIA-1, OG-CYC-1,
  OG-SYNTH-1, OG-RAD-1, OG-GEN-1 (economics), OG-TRN-1/2, OG-USD-1, OG-SIM-1,
  OG-P3D-1/2, OG-SCN-1/2, OG-OPEX-1.

## 3. Duplicate-authority risk register (flag only; no refactor this task)

| Concept | Candidate authorities | Current canonical | Recommendation |
|---|---|---|---|
| Room geometry (frontend) | `roomSpatialAuthority` (classify) · `authoritativeRoomFootprint` (derive) · `RoomPlanDecorator` (range plan) | authoritative IfcSpace footprint (exact > range) | Consolidate the three "room geometry" touchpoints later. |
| Clinical volume | frontend `ClinicalPlanningVolume` · backend `interactive_spatial_authoring.py` | distinct products/coordinate authorities | Watch if frontend volume ever feeds the backend engineering model. |
| Route / network | `canonical_spatial_authority` · `canonical_geometry_shadow_routing_authority` · `human_circulation_authority` | `canonical_spatial_authority.resolve_route` | Real gap is live-geometry→route integration (OG-ROUTE-INT), not a second engine. |
| Simulation state | `digital_twin_simulation_state` · `dynamic_scene_state_authority` · `operational_day_trajectory_scene` | distinct roles (state/bridge/scene) | Keep distinct; document boundaries. |
| Scenario identity | `CanonicalLockdownRecord` · `CanonicalWhatIfRecord` | `lockdown_what_if_lineage_authority.py` | Single owner; gap is product UI (OG-WIF-UI). |

## 4. Superseded / fallback inventory (kept, not deleted)

- Range-derived clinical room rectangles / `BIM_RANGE_APPROXIMATION` anchors →
  `SUPERSEDED_OR_FALLBACK` (superseded by authoritative IfcSpace geometry where
  extractable; still the honest fallback where exact geometry is unavailable).
- Legacy 2D overlay-only clinical representation → `SUPERSEDED_OR_FALLBACK`
  (superseded by the true-3D `ClinicalProgramDecorator` / `ClinicalPlanningVolume`).
- `RoomPlanDecorator` derived room-plan → view-only planning context, not physical
  authority.
- Uptake 01 reconstruction → `TEMPORARY_RECOVERY` (explicit, duplicate-guarded,
  never auto-runs).
- Backend `decay_engine.py` / `production_engine.py` → thin re-export shims
  (already noted in the Aug 29 index).

## 5. Revised finish-line workstreams (source-reconciled)

A. Authority consolidation (THIS TASK — complete). B. Complete Clinical Program +
Equipment Composition. C. Bentley geometry → canonical spatial/transport
integration. D. Candidate Facility Composition Optimizer. E. Unified Operations
Execution. F. Interactive Simulation / Animation Runtime. G. NVIDIA Omniverse
Runtime. H. Candidate Economics + Calibration Closure. I. What-If / Lockdown
product integration. J. UI/UX + Reporting + End-to-End Demo.

## 6. Dependency / priority classification

- **Dependency order:** A → (B ∥ C) → D/E/I → F/G → J; H (calibration) runs in
  parallel and gates only commercial completeness, never the first demo.
- **DEMO_CRITICAL:** B, demo slice of C, OG-FE-1, OG-FE-3 (demo slice), J (UI).
- **POST_DEMO_IMPORTANT:** D (OG-CAP-2), E (OG-OPS-1), F (OG-SIM-1), I (OG-WIF-UI),
  OG-FE-2.
- **COMMERCIAL_CALIBRATION:** OG-CYC-1, OG-SCN-1/2, OG-OPEX-1, OG-GEN-1 economics,
  OG-P3D-1/2, OG-TRN-2.
- **OPTIONAL_FUTURE (first demo):** G (OG-USD-1), OG-TRN-1, OG-ARIA-1, OG-FIN-1.

## 7. Verification (regression check — product source unchanged)

- `TYPECHECK` = **PASS** (`tsc -b`).
- `OFFLINE_TEST_COUNT` = **619** (35 files), `OFFLINE_TEST_REGRESSIONS` = **0**
  (a concurrent build+test run once reported flaky failures; a clean isolated run
  is 35/35 files, 619/619 tests).
- `PRODUCTION_BUILD` = **PASS** (`tsc -b && vite build`; only the known harmless
  `INEFFECTIVE_DYNAMIC_IMPORT` + chunk-size advisories).
- `CORE_FRONTEND_VERSION` = **5.12.5**.
- `PRODUCT_SOURCE_FILE_CHANGE_COUNT` = **0** (only the two authority docs + this
  report pair changed).

## 8. Source-of-truth statement

`MRT_PHARMA_AUTHORITY_INDEX.md` (September 9 addendum) and `MRT_PHARMA_OPEN_GAPS.md`
(September 9 section) are the CURRENT repository authority/gap source of truth as of
HEAD `bdd2103`. Historical build reports remain provenance and are not retroactively
rewritten. No master roadmap was rewritten; no open-gaps register was erased.

**CHECKPOINT = HOLD_FOR_AUTHORITY_RECONCILIATION_REVIEW** — not staged, not
committed, not pushed. Awaiting user review.
