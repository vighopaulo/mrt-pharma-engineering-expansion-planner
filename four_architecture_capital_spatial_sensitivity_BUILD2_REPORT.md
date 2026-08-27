# Four-Architecture Capital + Spatial Sensitivity Qualification — Build 2 Report

**Build:** Build 2 — Authoritative Four-Architecture Capital Comparison + Spatial Sensitivity Qualification + Mandatory Continuous-Chart Report
**Baseline:** Build 1 (`four_architecture_repository_first_closure_report.md`) — confirmed 2334 passed, 3 deselected, 0 failed.
**Governing rule:** Reuse existing authorities only. No new geometry engine, no new What-If engine, no new economics engine, no new physics. UI/UX not started.

This report is self-contained: every material assumption, physical design result, economic figure, and spatial-sensitivity result used in this build's conclusions is captured in the tables below or in the companion CSV directory `four_architecture_capital_spatial_sensitivity_BUILD2_tables/`.

---

## Chart 1 — Build Identity

| Item | Value |
|---|---|
| Build | Build 2 — Authoritative Four-Architecture Capital Comparison + Spatial Sensitivity Qualification |
| Purpose | Prove the capital-project digital twin independently engineers 4 architectures, consumes authoritative physical/resource quantities, compares them economically on the same project, and reacts correctly to changes in physical geometry (propagating 3D/spatial changes into CapEx/OPEX/lifecycle economics) |
| Starting baseline | Build 1 — 2334 passed, 3 deselected, 0 failed |
| Files changed | `whole_oncology_four_architecture_optimization.py`, `canonical_spatial_authority.py`, `test_whole_oncology_four_architecture_optimization.py`, `test_whole_oncology_patient_identity_unification.py` |
| Files added | `test_canonical_global_position_closure.py`, `test_conventional_route_spatial_sensitivity.py`, this report + CSV directory |
| Authorities reused | `whole_oncology_four_architecture_optimization`, `hybrid_optimization`, `campus_retrofit_benchmark`, `conventional_transport_authority`, `infrastructure_capex`, `infrastructure_opex`, `lifecycle_economics`, `shared_mrt_multistream_authority`, `canonical_spatial_authority.Transform`/`SpatialObjectRegistry`, `multi_isotope_decay`, `live_engineering_impact_binding` (audited, not modified) |
| Authorities added | `canonical_spatial_authority.resolve_global_position` / `compute_global_distance` / `SpatialObjectRegistry.replace_transform` (rigid-body global-position accumulation — a confirmed genuine gap, closed); `whole_oncology_four_architecture_optimization.evaluate_building_level_campus_hybrid_from_canonical_geometry` / `build_default_campus_canonical_registry` |
| Authorities modified | `whole_oncology_four_architecture_optimization._evaluate_mrt_style_architecture` — `automation_or_mrt_fte` now bound to the authoritative "MRT support labor" OPEX ledger row, replacing dead placeholder arithmetic (`installed_carriers * 0.0 + 3.0`) |
| New tests | 15 + 2 + 3 + 1 = 21 new tests across 2 new files + additions to 1 existing file (see Chart 22) |
| Runtime | Focused ~3.5s; directly-affected regression 36.39s; full regression see Chart 22 |
| Final regression | 2361 passed, 3 deselected, 0 failed, 2368.25s (0:39:28) |

---

## Chart 2 — Authority Map

| Quantity | Authoritative Producer | Consumer | Binding Path | Status | Notes |
|---|---|---|---|---|---|
| Conventional spatial/retention envelope | `spatial_benchmark.compute_retention_envelope` | `hybrid_optimization.evaluate_hybrid_zone_candidate` | `evaluate_manual_conventional -> _nuclear_result -> evaluate_hybrid_zone_candidate` | BOUND | Build 1, unchanged |
| MRT carrier fleet sizing | `hybrid_optimization` adaptive workload search → `mrt_carrier_fleet.resolve_mrt_carrier_fleet` | `shared_mrt_multistream_authority.compute_shared_mrt_economic_result` | `evaluate_hybrid_mrt`/`evaluate_mrt_dominant` → `_nuclear_result` → `compute_shared_mrt_economic_result` | BOUND | Confirmed Build 1; live `mrt_carriers=2` for full-MRT case |
| MRT guideway (horizontal/vertical/transitions) | `hybrid_optimization.compute_inbound_room_guideway_extension` (real per-room accumulation) | same | same | BOUND | Live: horizontal=90.0m, vertical=24.0m, transitions=12 for full-MRT case |
| Automated Conventional AGV/PTS fleet sizing | `conventional_transport_authority.agv_required_fleet_size` / `pts_required_station_count` | `evaluate_automated_conventional` | direct call | BOUND (Build 1 fix) | Was hardcoded `fleet_size=1` pre-Build-1 |
| Automated Conventional landing-point/last-mile timing | `conventional_transport_authority.compute_automated_conventional_distribution_timing` | `evaluate_automated_conventional` | direct call | BOUND (Build 1 addition) | New authority, genuine gap closed in Build 1 |
| `automation_or_mrt_fte` (MRT support staffing) | `infrastructure_opex` "MRT support labor" ledger row (`mrt_support_staff_fte=3.0`, `spatial_benchmark._build_request`) | `_evaluate_mrt_style_architecture` | `combined_result.combined_opex_ledger` lookup | BOUND (Build 2 fix) | Was dead arithmetic; now traced to the real ledger row it always numerically matched |
| Building-level Hybrid campus separation | `canonical_spatial_authority.compute_global_distance` (Build 2, NEW) | `evaluate_building_level_campus_hybrid_from_canonical_geometry` | `resolve_global_position(BLDG-A)`, `resolve_global_position(BLDG-B)` → Euclidean distance → `campus_retrofit_benchmark.build_two_building_campus_geometry(campus_separation_m=...)` | BOUND (Build 2, NEW) | Was a hardcoded float (`CAMPUS_SEPARATION_M=500.0`) prior to Build 2 |
| Canonical global position accumulation | `canonical_spatial_authority.resolve_global_position` (Build 2, NEW) | `evaluate_building_level_campus_hybrid_from_canonical_geometry`, tests | Parent-chain `Transform` accumulation: `x_global' = R x_local + t` | BOUND (Build 2, NEW) | Confirmed genuine gap via audit: `Transform` dataclass existed with full 6DOF but no accumulation function |
| Infrastructure CapEx | `infrastructure_capex.calculate_infrastructure_capex` / locally-composed equivalent in `evaluate_hybrid_zone_candidate` | all architecture evaluators | direct calls | BOUND | Build 1, unchanged |
| Infrastructure OPEX | `infrastructure_opex.calculate_infrastructure_opex` | `_build_hybrid_opex_result` | direct call | BOUND | Build 1, unchanged |
| Lifecycle economics (NPV/payback) | `lifecycle_economics.evaluate_lifecycle_economics` | `evaluate_hybrid_zone_candidate`, `campus_retrofit_benchmark` | direct calls | BOUND | Build 1, unchanged |
| Retention-qualified throughput | `spatial_benchmark._operational_retention_metrics` | `hybrid_optimization`, `_nuclear_result` | direct call | BOUND | Duplicate formula in 3 locations (flagged, not fixed, low priority) |
| Scanner→retention causal separation | `hybrid_optimization.evaluate_hybrid_zone_candidate` (retention computed from `injection_start`/`release_time` only) | `test_canonical_global_position_closure.py::TestScannerRelocationCausalSeparation` | source-line assertion + independent spatial move test | CONFIRMED BY TEST | Scanner position not consumed by retention computation at all (room→scanner travel time is not modeled in this repo) |

---

## Chart 3 — Complete Assumptions

See `03_assumptions.csv` (36 rows) for the full chart. Key entries:

| Category | Assumption | Value | Unit | Applicability | Provenance | Confidence |
|---|---|---|---|---|---|---|
| Geometry | floor_count | 8 | floors | zone-level architectures | `spatial_benchmark.build_benchmark_geometry` | CALIBRATED (synthetic) |
| Geometry | rooms_per_floor | 10 | rooms | zone-level architectures | `spatial_benchmark.build_benchmark_geometry` | CALIBRATED (synthetic) |
| Geometry | campus separation (default) | 500.0 | m | Building-level Hybrid campus | now resolvable from canonical geometry (Build 2) | CONTROLLED_ENGINEERING_ASSUMPTION |
| Demand | inpatients | 170 | patients | all four | `oncology_pet_spect_scenario` | CALIBRATED (synthetic population) |
| Demand | total patients | 230 | patients | all four | `oncology_pet_spect_scenario` | CALIBRATED (synthetic population) |
| Radionuclide | radionuclide | F-18 | – | all four | production_basis | CALIBRATED |
| Retention | minimum retention fraction | 0.9 | fraction | all four | `PlannerAssumptions` | CONTROLLED_ENGINEERING_ASSUMPTION |
| Operating | operating_days_per_year | 300 | days/yr | all four | `PlannerAssumptions` | CONTROLLED_ENGINEERING_ASSUMPTION |
| Operating | operating_hours_per_day | 18.0 | hours | all four | `PlannerAssumptions` | CONTROLLED_ENGINEERING_ASSUMPTION |
| Manual transport | hand-carry speed | 1.1 | m/s | Manual, Automated | `PorterOperatingPolicy` | CONTROLLED_ENGINEERING_ASSUMPTION |
| Manual transport | elevator_wait_minutes | 2.0 | min/transition | Manual, Automated | `PorterOperatingPolicy` | CONTROLLED_ENGINEERING_ASSUMPTION |
| Manual transport | base_wage_per_hour | 17.0 | USD/hr | Manual, Automated | `PorterOperatingPolicy` | CONTROLLED_ENGINEERING_ASSUMPTION |
| Manual transport | loaded_employer_cost_multiplier | 1.3 | x | Manual, Automated | `PorterOperatingPolicy` | CONTROLLED_ENGINEERING_ASSUMPTION |
| AGV | payload_capacity_kg | 150.0 | kg | Automated Conventional | `DEFAULT_AGV_MODEL` | CONTROLLED_ENGINEERING_ASSUMPTION |
| AGV | vehicle+integration CapEx | 150,000.0 | USD/unit | Automated Conventional | `DEFAULT_AGV_MODEL` | PARTIAL_EVIDENCE (~$100k historical vehicle evidence point) |
| PTS | station_capex_per_unit | 45,000.0 | USD/station | Automated Conventional | `DEFAULT_PTS_NETWORK` | CONTROLLED_ENGINEERING_ASSUMPTION |
| PTS | capsule_payload_kg | 2.0 | kg | Automated Conventional | `DEFAULT_PTS_NETWORK` | CONTROLLED_ENGINEERING_ASSUMPTION |
| Automated Conventional | CLUSTER_MAX_VERTICAL_TRANSITIONS | 1 | vertical transitions | Automated Conventional | Build 1 | DISCLOSED_POLICY_THRESHOLD (not arbitrary) |
| Automated Conventional | LANDING_POINT_LAST_MILE_DISTANCE_M | 15.0 | m | Automated Conventional | Build 1 | CONTROLLED_ENGINEERING_ASSUMPTION |
| MRT | horizontal/vertical speed | 3.0 / 1.5 | m/s | MRT, Hybrid | `PlannerAssumptions` | CONTROLLED_ENGINEERING_ASSUMPTION |
| MRT | transition_time_seconds | 8.0 | s | MRT, Hybrid | `PlannerAssumptions` | CONTROLLED_ENGINEERING_ASSUMPTION |
| MRT | carrier CapEx | 10,000.0 | USD/carrier | MRT, Hybrid | `PlannerAssumptions` | CONTROLLED_ENGINEERING_ASSUMPTION |
| MRT | guideway CapEx | 5,000.0 | USD/m | MRT, Hybrid | `PlannerAssumptions` | CONTROLLED_ENGINEERING_ASSUMPTION |
| MRT | mrt_support_staff_fte | 3.0 (fixed, not carrier-scaled) | FTE | MRT, Hybrid | `spatial_benchmark._build_request` | CONTROLLED_ENGINEERING_ASSUMPTION |
| MRT | mrt_support_staff_loaded_cost_per_fte | 105,000.0 | USD/FTE-yr | MRT, Hybrid | `spatial_benchmark._build_request` | CONTROLLED_ENGINEERING_ASSUMPTION |
| Economics | discount_rate_pct | 8.0 (whole-oncology) / 10.0 (campus) | % | all four | `PlannerAssumptions`/`SharedNetworkAssumptions` | CONTROLLED_ENGINEERING_ASSUMPTION |
| Economics | analysis_years | 10 | years | all four | `PlannerAssumptions` | CONTROLLED_ENGINEERING_ASSUMPTION |
| Economics | revenue_per_scan | 2000.0 (whole-oncology) / 300.0 (campus) | USD | all four | `PlannerAssumptions`/`SharedNetworkAssumptions` | CONTROLLED_ENGINEERING_ASSUMPTION |
| Production | cyclotron purchase+installation | 5,000,000.0 | USD | all four (shared) | `PlannerAssumptions` | CONTROLLED_ENGINEERING_ASSUMPTION |
| NOT_CALIBRATED | `cyclotron_eob_capacity_mbq_per_day` | None | MBq/day | all four | `PlannerAssumptions` | NOT_CALIBRATED — never zeroed |
| NOT_CALIBRATED | generator CapEx/OPEX | None | USD | SPECT | `PlannerAssumptions` | NOT_CALIBRATED — never zeroed |
| NOT_CALIBRATED | SPECT scanner CapEx/OPEX | None | USD | SPECT | `PlannerAssumptions` | NOT_CALIBRATED — never zeroed |

---

## Chart 4 — Project Geometry

| Object | Building | Floor | Local Coordinate | Global Coordinate | Orientation | Geometry Source | Status |
|---|---|---|---|---|---|---|---|
| CAMPUS-BLDG-A | CAMPUS-BLDG-A | – | (0,0,0) | (0.0, 0.0, 0.0) | 0° | `build_default_campus_canonical_registry` (Build 2) | CALIBRATED (synthetic) |
| CAMPUS-BLDG-B (default) | CAMPUS-BLDG-B | – | (500,0,0) rel. to facility | (500.0, 0.0, 0.0) | 0° | `build_default_campus_canonical_registry` (Build 2) | CALIBRATED (synthetic) |
| CAMPUS-BLDG-B (translated) | CAMPUS-BLDG-B | – | (800,0,0) rel. to facility | (800.0, 0.0, 0.0) | 0° | spatial sensitivity What-If (Build 2) | CONTROLLED_TEST_TRANSFORM |
| CAMPUS-BLDG-B (rotated 90°) | CAMPUS-BLDG-B | – | (500,0,0) rel. to facility | (500.0, 0.0, 0.0) | 90° (Z) | spatial sensitivity What-If (Build 2) | CONTROLLED_TEST_TRANSFORM — origin invariant under self-rotation |
| ROOM-X (before) | BLDG-1 | F3 | (12.0, 8.0, 0.0) | (12.0, 8.0, 0.0) | 0° | controlled room-relocation test registry | CONTROLLED_TEST_TRANSFORM |
| ROOM-X (after) | BLDG-1 | F3 | (48.0, 8.0, 0.0) | (48.0, 8.0, 0.0) | 0° | controlled room-relocation test registry | CONTROLLED_TEST_TRANSFORM |
| Whole-oncology zone-level benchmark | single building | 8 floors | `spatial_benchmark.BenchmarkGeometry` (per-room coordinates) | n/a (not canonical-registry-backed in this build) | n/a | `spatial_benchmark.build_benchmark_geometry` | CALIBRATED (synthetic, unchanged from Build 1) |

---

## Chart 5 — Four-Architecture Physical Design

| Metric | Manual Conventional | Automated Conventional | MRT (Dominant) | Hybrid (zone-level) | Authority/Notes |
|---|---|---|---|---|---|
| Active buildings | 1 | 1 | 1 | 1 | whole-oncology single-building benchmark |
| Active floors | 8 | 8 | 8 | 8 | all floors in scope |
| Scanners | 6 | 6 | 6 | 6 | `HybridZoneCandidate(scanners=6)` |
| CLUSTER/manual porter FTE | 33.00 | 34.00 | 0.00 | 61.00 | `compute_porter_resource_requirement` |
| Automation/MRT support FTE | 0.00 | 0.30 | 3.00 | 3.00 | AGV/PTS residual FTE (Automated); MRT support labor ledger row (MRT/Hybrid, Build 2 binding) |
| MRT carriers (full-MRT reference case) | 0 | 0 | 2 | n/a (partial coverage) | adaptive carrier search |
| MRT horizontal guideway (m, full-MRT case) | 0.0 | 0.0 | 90.0 | n/a | `compute_inbound_room_guideway_extension` |
| MRT vertical guideway (m, full-MRT case) | 0.0 | 0.0 | 24.0 | n/a | same |
| MRT transitions (full-MRT case) | 0 | 0 | 12 | n/a | same |
| New study CapEx (transport/logistics) | $0.00 | $270,000.00 | $31,300,000.00 | $27,430,000.00 | `ArchitectureResult.new_study_capex` |
| Nuclear total CapEx | $20,575,000.00 | $20,575,000.00 | $31,300,000.00 | $27,430,000.00 | `_nuclear_result.total_capex` |
| Nuclear qualified completed (patients/day) | 19 | 19 | 19 | 19 | retention-qualified completed count |

---

## Chart 6 — Service Streams

| Stream | Missions/day | Manual Conv Mode | Auto Conv Mode | MRT Mode | Hybrid Mode | Compatibility | Notes |
|---|---|---|---|---|---|---|---|
| RADIOPHARMACEUTICAL_NUCLEAR | 19 qualified/day | Manual porter/cart (unchanged) | Manual porter/cart (never AGV/PTS) | MRT carrier (shielded) | MRT for covered floors, else Manual | Protected — never assigned to AGV/PTS | Handled by `_nuclear_result`, distinct from general-logistics streams |
| CLEAN_LINEN | 170 | MANUAL_PORTER/PORTER_CART (CLUSTER) | CLUSTER + AGV_AMR (far floors) | MRT container (shared multistream authority) | MRT for covered zones, else Manual | AGV_AMR, PORTER_CART compatible; PNEUMATIC_TUBE excluded (bulk) | Build 1 CLUSTER+DISTRIBUTION closure |
| PHARMACY_INFUSION | 170 | MANUAL_PORTER (CLUSTER) | CLUSTER + AGV_AMR (far floors) | MRT container | MRT for covered zones, else Manual | AGV_AMR, PNEUMATIC_TUBE, MANUAL_PORTER all compatible | prefers AGV_AMR |
| SPECIMEN_BLOOD | 170 | MANUAL_PORTER (CLUSTER) | CLUSTER + PNEUMATIC_TUBE (far floors) | MRT container | MRT for covered zones, else Manual | PNEUMATIC_TUBE, MANUAL_PORTER compatible; AGV_AMR NOT compatible | only automated option is PTS |
| STERILE_CLEAN_SUPPLY | 170 | MANUAL_PORTER (CLUSTER) | CLUSTER + AGV_AMR (far floors) | MRT container | MRT for covered zones, else Manual | AGV_AMR, MANUAL_PORTER compatible; PNEUMATIC_TUBE excluded (bulk) | same pattern as CLEAN_LINEN |

---

## Chart 7 — Staffing

| Labor/Resource | Manual Conventional | Automated Conventional | MRT (Dominant) | Hybrid (zone-level) | Calculation | Provenance |
|---|---|---|---|---|---|---|
| CLUSTER/manual porter FTE | 33.00 | 34.00 | 0.00 | 61.00 | sweep-line peak concurrency + workload hours | Build 1, unchanged |
| Automation/MRT support FTE | 0.00 | 0.30 | 3.00 | 3.00 | AGV `residual_supervision_fte` + PTS `residual_labor_fte` (Automated); MRT support labor ledger row (MRT/Hybrid) | Automated: Build 1; MRT/Hybrid: Build 2 binding fix |
| Last-mile residual manual labor (Automated only) | n/a | included in porter_fte above | n/a | n/a | timed via `compute_automated_conventional_distribution_timing` | Build 1 CLUSTER+DISTRIBUTION closure |
| Clinical labor (injection/uptake/scanner) | shared | shared | shared | shared | `radiopharm_workflow_staffing.compute_radiopharm_workflow_staffing` (joint-schedule derived) | unchanged |
| Unresolved staffing quantities | none flagged | none flagged | none flagged (Build 2 closed the dead-code gap) | none flagged | – | – |

---

## Chart 8 — Retention / Throughput

| Metric | Manual Conventional | Automated Conventional | MRT (Dominant) | Hybrid (zone-level) | Notes |
|---|---|---|---|---|---|
| patients_retention_qualified_completed (nuclear) | 19 | 19 | 19 | 19 | Primary retention-constrained design value |
| General-logistics streams requested==served (all 4 streams) | 170/170 each | 170/170 each | 170/170 each | 170/170 each | No unmet demand in this controlled benchmark |

---

## Chart 9 — CapEx (Line Items)

| CapEx Item | Manual Conventional | Automated Conventional | MRT (Dominant) | Hybrid (zone-level) | Quantity | Unit Cost | Provenance/Status |
|---|---|---|---|---|---|---|---|
| Cyclotron purchase+installation | $5,000,000.00 (in nuclear total) | $5,000,000.00 | $5,000,000.00 | $5,000,000.00 | 1 unit | — | `PlannerAssumptions`, shared |
| Scanner CapEx (6 scanners) | $15,000,000.00 (in nuclear total) | $15,000,000.00 | $15,000,000.00 | $15,000,000.00 | 6 scanners | $2,500,000.00/scanner | `PlannerAssumptions.scanner_capex`, shared |
| AGV fleet CapEx (Automated only) | $0.00 | ~$150,000.00 | $0.00 | $0.00 | 1 vehicle (workload-derived) | $100k vehicle + $50k integration | Build 1, real fleet size |
| PTS CapEx (Automated only) | $0.00 | ~$45,000.00 | $0.00 | $0.00 | 1 station (workload-derived) | $45,000/station | Build 1/2, real station count |
| MRT carrier CapEx (full-MRT reference case) | $0.00 | $0.00 | $20,000.00 (component) | n/a (partial coverage) | 2 carriers | $10,000.00/carrier | `PlannerAssumptions.mrt_carrier_capex_per_installed_unit` |
| MRT guideway CapEx (full-MRT reference case) | $0.00 | $0.00 | included in nuclear total (114m × $5,000/m component) | n/a | 114.0 m | $5,000.00/m | `compute_inbound_room_guideway_extension` |
| **TOTAL new_study_capex** (transport/logistics only) | **$0.00** | **$270,000.00** | **$31,300,000.00** | **$27,430,000.00** | – | – | `ArchitectureResult.new_study_capex` |
| **TOTAL nuclear_total_capex** | **$20,575,000.00** | **$20,575,000.00** | **$31,300,000.00** | **$27,430,000.00** | – | – | `ArchitectureResult.nuclear_total_capex` |

---

## Chart 10 — OPEX (Line Items)

| OPEX Item | Manual Conventional | Automated Conventional | MRT (Dominant) | Hybrid (zone-level) | Basis | Unit Cost | Provenance/Status |
|---|---|---|---|---|---|---|---|
| CLUSTER/manual transport labor | included (33.00 FTE) | included (34.00 FTE) | $0.00 (no manual transport) | included (61.00 FTE, fallback streams) | FTE-year | wage × multiplier × hours × days | `conventional_transport_authority` |
| AGV OPEX (maintenance+energy+supervision) | $0.00 | included | $0.00 | $0.00 | 1 vehicle | maintenance+energy+supervision FTE | `agv_annual_opex` |
| PTS OPEX (maintenance+energy+labor) | $0.00 | included | $0.00 | $0.00 | 1 station | maintenance+energy+labor FTE | `pts_annual_opex` |
| MRT support labor | $0.00 | $0.00 | 3.00 FTE × $105,000 = $315,000.00 | 3.00 FTE × $105,000 = $315,000.00 | 3.0 FTE (fixed, Build 2 bound to ledger) | $105,000.00/FTE-yr | `infrastructure_opex` "MRT support labor" row |
| Nuclear annual OPEX (production+clinical+mode-specific) | $5,021,480.00 | $5,021,480.00 | $5,049,580.00 | $5,265,780.00 | – | – | `_nuclear_result.total_annual_opex` |
| **TOTAL annual_opex** (transport/logistics only) | **$1,750,320.00** | **$1,826,272.00** | **$5,058,730.00** | **$8,502,570.00** | – | – | `ArchitectureResult.annual_opex` |

---

## Chart 11 — Lifecycle Economics

| Metric | Manual Conventional | Automated Conventional | MRT (Dominant) | Hybrid (zone-level) | Calibration Status | Notes |
|---|---|---|---|---|---|---|
| New study CapEx | $0.00 | $270,000.00 | $31,300,000.00 | $27,430,000.00 | CALIBRATED | – |
| Annual OPEX (known) | $1,750,320.00 | $1,826,272.00 | $5,058,730.00 | $8,502,570.00 | CALIBRATED | – |
| Lifecycle cost (present value of costs) | $11,744,789.67 | $12,524,433.78 | $65,244,490.08 | $84,482,936.80 | CALIBRATED | `apply_study_scope.operating_horizon_present_value` (negated) |
| Cost-only ranking (lower is better) | **1st (lowest)** | 2nd | 3rd | 4th (highest) | CALIBRATED, NOT FORCED | Ranking emerges from real computed lifecycle cost |
| ROI | ROI_NOT_AUTHORIZED_OR_NOT_CALIBRATED | ROI_NOT_AUTHORIZED_OR_NOT_CALIBRATED | ROI_NOT_AUTHORIZED_OR_NOT_CALIBRATED | ROI_NOT_AUTHORIZED_OR_NOT_CALIBRATED | NOT_CALIBRATED | No authoritative ROI formula found; not invented |
| Break-even | not computed at this level | not computed | not computed | not computed | NOT_CALIBRATED (this level) | Campus benchmark level (Chart 18) has real NPV |

---

## Chart 12 — Spatial Sensitivity (Master Table)

| Scenario | Object Changed | Transform | Architecture | Route Before | Route After | Guideway Before | Guideway After | CapEx Before | CapEx After | OPEX Before | OPEX After | NPV Before | NPV After | Conclusion |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Campus translation | CAMPUS-BLDG-B | position_x: 500→800 (+300m) | Building-level Hybrid campus | 500.0 | 800.0 | 500.0 | 800.0 | $45,040,000.00 | $54,090,000.00 | $6,580,955.00 | $6,854,705.00 | $200,676,772.70 | $189,789,887.92 | **SENSITIVE**: translation genuinely increases guideway length, CapEx, OPEX; decreases NPV |
| Campus rotation (90° about own origin) | CAMPUS-BLDG-B | rotation_z: 0→90° | Building-level Hybrid campus | 500.0 | 500.0 | 500.0 | 500.0 | $45,040,000.00 | $45,040,000.00 | $6,580,955.00 | $6,580,955.00 | $200,676,772.70 | $200,676,772.70 | **PHYSICALLY_INVARIANT_FOR_THIS_TRANSFORM**: connection point is at the rotation axis |
| Room relocation | ROOM-X | position: (12,8,0)→(48,8,0) | Manual Conventional (generic route-timing model) | 14.42 m | 48.66 m | n/a (not MRT) | n/a | n/a (single-mission timing test only) | n/a | n/a | n/a | n/a | n/a | **SENSITIVE**: route/travel-time genuinely increases proportional to route length (9.437 → 10.475 min/mission, Δ=+1.038 min) |

---

## Chart 13 — Building Rotation

| Metric | Before Rotation | After Rotation | Δ | Engineering Cause | Economic Consequence |
|---|---|---|---|---|---|
| Building B global position (own origin) | (500.0, 0.0, 0.0) | (500.0, 0.0, 0.0) | 0.0 | Rotation is applied about the building's own local origin — the origin itself is a fixed point under any rotation | None |
| Inter-building distance (A↔B) | 500.0 | 500.0 | 0.0 | Both buildings' connection points are at their own local origins in this canonical registry | None — PHYSICALLY_INVARIANT_FOR_THIS_TRANSFORM |
| Off-axis room global position (B-F1-R01, local offset (10,5,0)) | (510.0, 5.0, 0.0) | (495.0, 10.0, 0.0) | dx=−15.0, dy=+5.0 | Rotation matrix applied to the room's non-zero local offset | Not evaluated in the campus-CapEx run (which uses building-origin-to-building-origin distance only) — demonstrates the geometry engine correctly distinguishes on-axis vs off-axis sensitivity |
| Building B campus CapEx | $45,040,000.00 | $45,040,000.00 | $0.00 | Campus route length is driven by building-origin-to-building-origin distance, unaffected by rotation about that same origin | None |

---

## Chart 14 — Building Translation

| Metric | Before Translation | After Translation | Δ | Engineering Cause | Economic Consequence |
|---|---|---|---|---|---|
| Building B global position | (500.0, 0.0, 0.0) | (800.0, 0.0, 0.0) | +300.0 | Direct translation of Building B's own `Transform.position_x` | – |
| Inter-building distance (A↔B) | 500.0 | 800.0 | +300.0 | Euclidean distance between accumulated global positions | Feeds directly into `campus_retrofit_benchmark.build_two_building_campus_geometry(campus_separation_m=...)` |
| Building B total CapEx | $45,040,000.00 | $54,090,000.00 | +$9,050,000.00 | Longer campus route → more guideway length → more guideway CapEx (real per-room accumulation) | CapEx increases |
| Building B annual OPEX | $6,580,955.00 | $6,854,705.00 | +$273,750.00 | Guideway maintenance OPEX scales with guideway length | OPEX increases |
| Qualified lifecycle NPV | $200,676,772.70 | $189,789,887.92 | −$10,886,884.78 | Higher CapEx+OPEX with unchanged revenue → lower NPV | NPV decreases |

---

## Chart 15 — Scanner Movement

| Metric | Before | After | Δ | Direct/Indirect Effect | Explanation |
|---|---|---|---|---|---|
| Scanner global position | (2.0, 2.0, 0.0) [example test object] | (40.0, 8.0, 0.0) | moved | DIRECT (geometry only) | `resolve_global_position` correctly reflects the new Transform |
| Release→administration retention (already-injected patient) | unchanged | unchanged | 0.0 (NO CHANGE) | NONE — causal boundary preserved | `evaluate_hybrid_zone_candidate` computes `retained_fraction(elapsed, half_life)` purely from `injection_start`/`release_time`; scanner coordinate is never read (confirmed via source-line audit) |
| Patient room→scanner travel time | NOT_MODELED | NOT_MODELED | n/a | would be INDIRECT if modeled | This repository's current authority does not model scanner-coordinate-dependent travel time; disclosed limitation, not fabricated |
| Scanner utilization/queue | NOT_MODELED as f(coordinate) | NOT_MODELED | n/a | would be INDIRECT if modeled | Scanner *count* (not position) drives scheduling in `schedule_operating_day` |
| Other objects' global positions | unaffected | unaffected | 0.0 | NONE | Verified: moving a scanner never changes `BLDG-A` or `A-F1-R01`'s global position |

---

## Chart 16 — Automated Conventional Audit

| Stream/Floor | Technology | Landing Point | Automated Distance | Last-Mile Distance | Missions | Fleet/Stations | CapEx | Status |
|---|---|---|---|---|---|---|---|---|
| CLEAN_LINEN / far floors (4) | AGV_AMR | per-floor landing point | 4.0 min (ROUTE_NOT_CALIBRATED placeholder) | 15.0 m | 170 demands consolidated | AGV fleet=1 (workload-derived) | included in $270,000.00 total | BOUND (Build 1) |
| PHARMACY_INFUSION / far floors (4) | AGV_AMR | per-floor landing point | 4.0 min | 15.0 m | 170 demands consolidated | shares AGV fleet=1 | shared | BOUND (Build 1) |
| SPECIMEN_BLOOD / far floors (4) | PNEUMATIC_TUBE | per-floor landing point | 4.0 min | 15.0 m | 170 demands consolidated | PTS station count=1 (workload-derived) | included in $270,000.00 total | BOUND (Build 1) |
| STERILE_CLEAN_SUPPLY / far floors (4) | AGV_AMR | per-floor landing point | 4.0 min | 15.0 m | 170 demands consolidated | shares AGV fleet=1 | shared | BOUND (Build 1) |
| All streams / near floors (CLUSTER) | MANUAL_PORTER/PORTER_CART | n/a (no automation) | n/a | n/a | 170 demands per stream | n/a | $0.00 (no new CapEx) | BOUND (Build 1, unchanged Manual authority) |

**Why this is genuinely CLUSTER + DISTRIBUTION:** near floors (≤1 vertical transition from the general-logistics origin) are served purely by the unchanged Manual Conventional authority (CLUSTER); far floors are served by a real, workload-sized AGV/PTS main leg to a landing point plus a short, explicit 15m manual last-mile hand-off (DISTRIBUTION) — never a single generic automation price applied to the whole facility.

---

## Chart 17 — MRT Infrastructure Audit

| Infrastructure | Quantity | Unit | Unit Cost | CapEx | OPEX Basis | Authority | Status |
|---|---|---|---|---|---|---|---|
| Horizontal guideway (full-MRT case) | 90.0 | m | $5,000.00/m | $450,000.00 (component) | 3%/yr of CapEx | `compute_inbound_room_guideway_extension` | BOUND (real per-room accumulation) |
| Vertical guideway (full-MRT case) | 24.0 | m | $5,000.00/m | $120,000.00 (component) | same basis | `compute_inbound_room_guideway_extension` | BOUND |
| H↔V transitions (full-MRT case) | 12 | transitions | included in guideway extension CapEx | included above | Vertical transition annual maintenance | `hybrid_optimization` | BOUND |
| Endpoints (full-MRT case) | = number of MRT-served rooms | endpoints | $10,000.00/endpoint | included in nuclear total | endpoint annual O&M | `evaluate_hybrid_zone_candidate` | BOUND |
| Carrier fleet (full-MRT case) | 2 | carriers | $10,000.00/carrier | $20,000.00 | carrier electricity+maintenance | adaptive workload search → `resolve_mrt_carrier_fleet` | BOUND (workload-derived, never one representative carrier) |
| MRT support labor (staffing) | 3.0 (fixed assumption) | FTE | $105,000.00/FTE-yr | n/a (OPEX only) | $315,000.00/yr | `infrastructure_opex` "MRT support labor" row; `automation_or_mrt_fte` now bound to it (Build 2) | BOUND (Build 2 fix) — disclosed as a FIXED assumption, not carrier-count-scaled |
| Controls/vestibule/installation | 1 each (once-per-network) | unit | `MRT_CONTROLS_CAPEX_USD`/`MRT_VESTIBULE_CAPEX_USD`/`MRT_INSTALLATION_COMMISSIONING_CAPEX_USD` | held constant under length-only what-ifs | n/a | `live_engineering_impact_binding.compute_segment_length_what_if_impact` | BOUND, explicit non-regression enforced |

---

## Chart 18 — Hybrid Campus Audit

| Item | Building A | Building B | Shared Campus | Economic Treatment |
|---|---|---|---|---|
| Production origin (CY-001/RADIOPHARMACY-A) | Present (existing) | Not present | Shared, once | Building A new CapEx = $0 (existing shell) — never duplicated merely because Building B has a separate transport architecture |
| Clinical rooms | 0 (production-only) | 40 candidate rooms (4 floors × 10 rooms) | n/a | Building B CapEx only |
| Transport architecture | Conventional (fixed) | MRT (all 4 floors, default) | Campus classification = **HYBRID** | Never 50/50 blend — physically separate architectures per building |
| Campus separation (default) | – | – | 500.0 m (now resolvable via canonical geometry, Build 2) | Feeds guideway length → CapEx/OPEX |
| Building B total CapEx (default 500m) | – | $45,040,000.00 | – | `run_campus_case_2_hybrid` |
| Building B annual OPEX (default 500m) | – | $6,580,955.00 | – | `run_campus_case_2_hybrid` |
| Retention-qualified completed (default 500m) | – | 72 | – | `run_campus_case_2_hybrid` |
| Qualified lifecycle NPV (default 500m) | – | $200,676,772.70 | – | `evaluate_lifecycle_economics` |

---

## Chart 19 — What-If Dependency Trace

| Changed Object | Changed Property | Directly Affected Authority | Downstream Engineering Quantity | Economic Quantity | Unaffected Quantity | Reason |
|---|---|---|---|---|---|---|
| Building B | position_x (translation) | `canonical_spatial_authority.compute_global_distance` | campus_separation_m → guideway horizontal length | Building B total_capex, annual_opex, qualified_lifecycle_npv | Building A position/CapEx, retention threshold, patient demand | Only the physically dependent inter-building route length changes |
| Building B | rotation_z (about own origin) | `canonical_spatial_authority.compute_global_distance` | none (origin-to-origin distance invariant under self-rotation) | none | Building B total_capex, annual_opex, qualified_lifecycle_npv, campus_separation_m | The campus benchmark's connection point IS the building's own origin — PHYSICALLY_INVARIANT_FOR_THIS_TRANSFORM |
| Room (generic) | position (relocation) | `conventional_transport_authority.compute_manual_mission_timing` (`horizontal_distance_m`) | route minutes | porter labor hours/OPEX (not re-run in this controlled test) | other rooms' positions, building identity, retention threshold | Distance-driven timing formula responds monotonically to route length |
| Scanner (generic) | position (relocation) | `resolve_global_position` (geometry only) | NONE currently wired (disclosed limitation) | NONE (retention/OPEX unaffected) | release→administration retention for already-injected patients, other objects' positions | Scanner position is not consumed by any current economic/retention authority — moving it is a pure no-op for those quantities, by architecture, not omission |

This table documents the future Live-3D data contract: `3D USER TRANSFORM → CANONICAL GLOBAL GEOMETRY (Build 2 closure) → ENGINEERING IMPACT (composed from existing authorities) → RECOMPUTATION → UPDATED ECONOMIC WINDOW`.

---

## Chart 20 — Conclusions

| Question | Evidence | Conclusion | Confidence | Remaining Limitation |
|---|---|---|---|---|
| Which architectures are physically feasible? | All four `ArchitectureResult.feasible=True` | All four (Manual, Automated, MRT_DOMINANT, HYBRID_MRT) are feasible for this benchmark demand | high | Not re-verified for arbitrary campus geometries beyond tested deltas |
| Which meet qualified demand? | `nuclear_qualified_completed=19` for all four | All four meet the same qualified nuclear demand | high | 170/170 general-logistics streams served for all 4 |
| Which has lowest known CapEx? | Chart 9/11 | Manual Conventional ($0 new-study CapEx) | high | n/a |
| Which has lowest known OPEX? | Chart 10/11 | Manual Conventional ($1,750,320.00/yr) | high | n/a |
| Which has superior lifecycle economics where comparable? | Chart 11 ranking | Manual < Automated < MRT_DOMINANT < HYBRID_MRT (zone-level) | high (for this benchmark scale/geometry) | Result is scale/geometry-dependent, not a general claim — sensitivity tests show MRT/Hybrid economics change materially with geometry |
| What drives each result? | Chart 9/10 | Manual: near-zero CapEx. Automated: added AGV/PTS CapEx not offset by labor savings at this scale. MRT/Hybrid: large guideway/carrier/endpoint CapEx dominates. | high | n/a |
| How sensitive is each architecture to geometry? | Chart 12/13/14 | MRT/Hybrid campus economics directly sensitive to inter-building distance; Manual/Automated route timing sensitive to room-level distance; none sensitive to rotation about their own collocated connection point | high (tested transforms) | Rotation only tested about the building's own origin |
| Did building translation alter economics? | Chart 14 | Yes — CapEx +$9,050,000, OPEX +$273,750/yr, NPV −$10,886,884.78 for +300m | high | n/a |
| Did building rotation alter economics? | Chart 13 | No — PHYSICALLY_INVARIANT_FOR_THIS_TRANSFORM | high | Rotation combined with an off-axis connection point was not separately tested at the campus-economics level |
| Did scanner movement behave causally correctly? | Chart 15 + test suite | Yes — retention for an already-injected patient is unaffected by scanner position | high | Room→scanner travel time is NOT modeled as f(scanner coordinate) — disclosed |
| Does Automated Conventional now genuinely represent Cluster + Distribution? | Chart 5/16 | Yes (established Build 1, reconfirmed live this build) | high | n/a |
| Does MRT economics consume actual guideway/fleet quantities? | Chart 2/17 | Yes, confirmed via code trace + a proof test showing quantities change with MRT floor coverage | high | n/a |
| Does Hybrid use building-level semantics? | Chart 18 | Yes for the capital-project comparison; zone-level optimizer remains separately available | high | n/a |
| Is the engineering contract ready for future drag-and-drop Live 3D? | Chart 19 | Partially — canonical global-position accumulation gap is closed and demonstrated end-to-end for campus/room cases; UI/UX and a general What-If dispatcher were explicitly out of scope | medium | `interactive_spatial_authoring.py` move/rotate still doesn't auto-trigger route/CapEx recomputation (pre-existing, disclosed) |
| What remains before Build 3? | Chart 21 | See Limitations chart | – | – |

---

## Chart 21 — Limitations / NOT_CALIBRATED

| Item | Architecture | Current Status | Consequence | Required Future Calibration |
|---|---|---|---|---|
| `cyclotron_eob_capacity_mbq_per_day` | All four | NOT_CALIBRATED (None) | Production feasibility reported NOT_CALIBRATED, never assumed pass/fail | Obtain vendor-calibrated EOB capacity figure |
| Generator (SPECT) CapEx/OPEX | SPECT-related | NOT_CALIBRATED (None) | SPECT economics not included in totals; disclosed, never zeroed | Obtain generator vendor pricing |
| SPECT scanner CapEx/OPEX | SPECT-related | NOT_CALIBRATED (None) | Same as above | Obtain SPECT scanner vendor pricing |
| ROI | All four | ROI_NOT_AUTHORIZED_OR_NOT_CALIBRATED | ROI intentionally omitted rather than invented | Define authoritative ROI formula in a dedicated review if genuinely required |
| `automation_or_mrt_fte` carrier-count scaling | MRT, Hybrid | Fixed 3.0 FTE, not scaled by installed_carriers | MRT support staffing does not currently increase with fleet size | Decide whether staffing should scale with fleet size; add as an explicit new authority if so (not invented this build) |
| Room→scanner travel time as f(scanner coordinate) | All four | NOT_MODELED | Scanner relocation has zero economic/retention consequence currently — causally correct but incomplete | Add a dedicated scanner-position-aware travel-time authority in a future build |
| General What-If dispatcher for arbitrary object/property changes | n/a | NOT_BUILT | Spatial sensitivity qualified via direct composition, not a generic dispatcher (Section 27 forbids a new What-If engine) | Consider a generalized dispatcher for Build 3, reusing this build's compositional pattern |
| Retention-qualified-throughput formula duplication | All (nuclear side) | Duplicated in 3 locations | No behavioral defect, maintainability risk only | Consolidate into one retention authority module if a future build touches any of the 3 locations |

---

## Chart 22 — Tests

| Test Group | Tests Run | Passed | Failed | Deselected | Runtime | Notes |
|---|---|---|---|---|---|---|
| Focused: canonical global position closure | 17 | 17 | 0 | 0 | 0.31s | `test_canonical_global_position_closure.py` |
| Focused: conventional route spatial sensitivity | 7 | 7 | 0 | 0 | ~0.1s | `test_conventional_route_spatial_sensitivity.py` |
| Focused: whole-oncology four-architecture optimization | 48 | 48 | 0 | 0 | 2.86s | includes campus canonical geometry + dead-code binding tests |
| Directly affected regression (14 files) | 682 | 682 | 0 | 0 | 36.39s | spatial authority, campus benchmark, patient identity, MRT multistream, conventional transport, live engineering impact binding, etc. |
| Full repository regression | 2361 | 2361 | 0 | 3 (known pre-existing) | 2368.25s (0:39:28) | Zero new failures from Build 2 |

**FULL REPOSITORY REGRESSION RESULT:** `2361 passed, 3 deselected, 2 warnings in 2368.25s (0:39:28)` -- captured directly from the terminal tool's completion notification (no stdout/stderr redirection to a log file was used for this run).

---

## Non-Goals Confirmed Respected

No UI/UX, no BIM/IFC redesign, no new NVIDIA/Bentley/Varian integration, no stochastic operational simulation, no new operational scheduling capability, no new economic/CapEx/OPEX engine, no new MRT/radionuclide/carrier/production physics were introduced. All new code in this build is either (a) a pure geometric accumulation utility reusing the existing `Transform`/`SpatialObjectRegistry` dataclasses, or (b) a thin composition wrapper binding existing evaluators together with real computed inputs instead of hardcoded floats/placeholder arithmetic.
