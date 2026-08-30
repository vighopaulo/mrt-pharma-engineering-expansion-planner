# TRANSPORT-MODE PARITY AUTHORITY — KIRO SUPER-BUILD 1

Manual + PTS + AGV/AMR (light-clinical + heavy-logistics), with MRT preserved
as reference. Establishes engineering/economic parity authorities so the NEXT
Super-Build's generalized multi-transport optimizer can compare all modes on
one schema. This build does NOT integrate that optimizer, does NOT change MRT
or the Part 3E experiments, and does NOT stage/commit/push.

Machine-readable data: `transport_mode_parity_data.json`.

## TABLE 1 — Super-Build Repository Basis

| Field | Value |
|---|---|
| Starting HEAD | `cb4d4f4` (corrected MRT experiment rerun checkpoint) |
| origin/main | `cb4d4f4` (divergence 0/0) |
| Scope | Transport-mode parity authorities only; NO optimizer, NO UI |
| Modes | MANUAL, PTS, DEDICATED_RP_PTS, AGV_AMR_LIGHT_CLINICAL, AGV_AMR_HEAVY_LOGISTICS, MRT(reference) |
| Checkpoint policy | IMPLEMENT → VERIFY → REPORT → STOP (no stage/commit/push) |

## TABLE 2 — Governance Upgrade

| Field | Value |
|---|---|
| Governance owner | `engineering_authority.py` (existing; extended, not duplicated) |
| Added | `SUPER_BUILD_GOVERNANCE_REGISTRY` = 23 `SuperBuildGovernanceRule` |
| `super_build_governance_present()` | True |
| Second hierarchy created | NO |
| Principles | AUTHORITY_FIRST, ONE_AUTHORITY_PER_CONCEPT, NO_DUPLICATE_ENGINE, PAYLOAD_ELIGIBILITY_BEFORE_OPTIMIZATION, FALLBACK_CONSERVATION, NO_ZERO_FILLING_UNKNOWN_COSTS, TECHNOLOGY_FAIRNESS, NO_DOUBLE_COUNTING, EXPERIMENT_FREEZE, HISTORICAL_RESULTS_PRESERVED, SCOPE_GOVERNOR, DEFINITION_OF_DONE, … (23 total) |

## TABLE 3 — Existing Transport Authority Trace (TRANSPORT_PARITY_AUTHORITY_TRACE)

| Concept | Current owner | Classification |
|---|---|---|
| Manual porter/cart physics + staffing + CapEx/OPEX | `conventional_transport_authority.py` (PorterOperatingPolicy, compute_manual_mission_timing, compute_porter_resource_requirement, CartClass) | REUSE + parity VIEW |
| Ordinary PTS | `conventional_transport_authority.py` (PneumaticTubeNetwork/DEFAULT_PTS_NETWORK) | EXTEND (profiles + eligibility view) |
| Rail-guided AGV (RGHT) | `conventional_transport_authority.AgvModelClass` (technology_class="RGHT") | LEGACY_PRESERVE |
| Free-roaming floor AGV/AMR | `transport_technology_authority.FLOOR_AGV_AMR` = NOT_IMPLEMENTED | GENUINE_GAP → NEW `floor_agv_amr_authority.py` |
| Dedicated RP-PTS | `dedicated_rp_pts_authority.py` | REUSE (reference) |
| MRT | `mrt_canonical_configuration` + `shared_mrt_multistream_authority` | REUSE (reference, untouched) |
| Cross-mode eligibility | (none unified) | GENUINE_GAP → NEW `transport_mode_eligibility_authority.py` |
| Modes-in-scope + fallback + parity contract | (none) | GENUINE_GAP → NEW `transport_mode_scope_authority.py` |
| Provenance/calibration vocabulary | `editable_default_authority.EditableParameter` | REUSE |

## TABLE 4 — Common Transport Vocabulary

| Family | Identifier |
|---|---|
| Manual | MANUAL |
| Pneumatic tube | PTS |
| Dedicated radiopharmaceutical PTS | DEDICATED_RP_PTS |
| Light-clinical free-roaming | AGV_AMR_LIGHT_CLINICAL |
| Heavy-logistics free-roaming | AGV_AMR_HEAVY_LOGISTICS |
| Magnetic rapid transit (reference) | MRT |

## TABLE 5 — Provenance / Calibration Vocabulary (reused)

| Status | Meaning |
|---|---|
| PUBLISHED_ENGINEERING_DEFAULT / REFERENCE_BENCHMARK / COST_REFERENCE | published planning reference |
| PROJECT_CONTROLLED_ASSUMPTION | project-controlled |
| CONTROLLED_ENGINEERING_ASSUMPTION | disclosed engineering planning assumption |
| NOT_CALIBRATED | no defensible value; never $0-filled |
| (never) CALIBRATED_PROJECT_VALUE | reserved for facility/vendor-confirmed only |

## TABLE 6 — Payload / Mission Taxonomy

| Stream | Notes |
|---|---|
| RADIOPHARMACEUTICAL_NUCLEAR | shielding/qualification gated |
| SPECIMEN_BLOOD (GENERAL_COMPATIBLE / PTS_SENSITIVE) | PTS-sensitive needs facility validation |
| PHARMACY_INFUSION | small compatible |
| STERILE_CLEAN_SUPPLY | small vs bulk distinguished by mass/volume |
| CLEAN_LINEN | bulk logistics |
| (MRT registry alias) LAUNDRY_CLEAN_LINEN ↔ CLEAN_LINEN | bridged, never renamed |

## TABLE 7 — Overall Capability Matrix (default eligibility, representative payloads)

| Stream | MANUAL | PTS | RP-PTS | AGV LIGHT | AGV HEAVY | MRT |
|---|---|---|---|---|---|---|
| Radiopharmaceutical | ELIGIBLE | QUAL_REQ | ELIGIBLE | QUAL_REQ | QUAL_REQ | ELIGIBLE |
| Specimen (general) | ELIGIBLE | ELIGIBLE | INELIGIBLE | ELIGIBLE | INELIGIBLE | ELIGIBLE |
| Pharmacy | ELIGIBLE | ELIGIBLE | INELIGIBLE | ELIGIBLE | INELIGIBLE | NOT_CALIBRATED* |
| Sterile (small) | ELIGIBLE | INELIGIBLE | INELIGIBLE | ELIGIBLE | ELIGIBLE | NOT_CALIBRATED* |
| Clean linen (bulk) | ELIGIBLE | INELIGIBLE | INELIGIBLE | INELIGIBLE | ELIGIBLE | INELIGIBLE |

*MRT pharmacy/sterile speed NOT_CALIBRATED per canonical authority; mass gate still applies. Eligibility computed by `transport_mode_eligibility_authority`; see `transport_mode_parity_data.json`.

## TABLE 8 — Radiopharmaceutical Eligibility Matrix (Sec 53)

| Mode | Default |
|---|---|
| MANUAL | ELIGIBLE (with shielded-container procedure; QUALIFICATION_REQUIRED without) |
| PTS | QUALIFICATION_REQUIRED |
| DEDICATED_RP_PTS | ELIGIBLE (nuclear-only dedicated) |
| AGV_AMR_LIGHT_CLINICAL | QUALIFICATION_REQUIRED |
| AGV_AMR_HEAVY_LOGISTICS | QUALIFICATION_REQUIRED |
| MRT | governed by canonical MRT authority (ELIGIBLE within 5 kg ceiling) |

Economics never manufacture radiation qualification (radiation qualification sentinel passes).

## TABLE 9 — Linen / Bulk Logistics Eligibility Matrix (Sec 54)

| Mode | Bulk linen (60 kg) |
|---|---|
| MANUAL | ELIGIBLE (subject to human/cart capacity) |
| PTS | INELIGIBLE |
| AGV_AMR_LIGHT_CLINICAL | INELIGIBLE (outside envelope) |
| AGV_AMR_HEAVY_LOGISTICS | ELIGIBLE |
| MRT | INELIGIBLE (13.5 kg > 5 kg ceiling) |

## TABLE 10 — Specimen Eligibility Matrix (Sec 55)

| Mode | General specimen | PTS-sensitive specimen |
|---|---|---|
| MANUAL | ELIGIBLE | ELIGIBLE |
| PTS | ELIGIBLE | FACILITY_VALIDATION_REQUIRED (→ ELIGIBLE once validated) |
| AGV_AMR_LIGHT_CLINICAL | ELIGIBLE (secured compartment) | ELIGIBLE |
| AGV_AMR_HEAVY_LOGISTICS | INELIGIBLE (stream not supported; not merely capacity) | INELIGIBLE |
| MRT | ELIGIBLE (within mass) | ELIGIBLE |

Heavy AGV never becomes the preferred specimen mode by capacity alone.

## TABLE 11 — Pharmacy / Sterile Eligibility (Sec 56)

| Payload | Eligible modes (default) |
|---|---|
| Small pharmacy/infusion | MANUAL, PTS, AGV_AMR_LIGHT_CLINICAL |
| Small sterile/clean | MANUAL, AGV_AMR_LIGHT_CLINICAL, AGV_AMR_HEAVY_LOGISTICS |
| Bulk sterile supply | MANUAL, AGV_AMR_HEAVY_LOGISTICS (light rejects by mass/volume) |

## TABLE 12 — Manual Physical Parameters (`conventional_transport_authority`)

| Parameter | Value |
|---|--:|
| Unloaded walk speed | 1.4 m/s |
| Loaded hand-carry speed | 1.1 m/s |
| Loaded cart speed | 0.9 m/s |
| Dispatch / load / unload / wait | 2 / 3 / 3 / 1 min |
| Elevator wait | 2 min |
| Shift hours / availability | 8 h / 85% |

## TABLE 13 — Manual Route-Time Reconciliation

T = dispatch + load + horizontal(dist/speed) + vertical(transitions×elevator_wait) + wait + unload + return(symmetric). ROUTE_CALIBRATED when distance supplied, else ROUTE_NOT_CALIBRATED. Verified in tests (calibrated 110 m; cart slower than hand; elevator adds vertical; symmetric return).

## TABLE 14 — Manual Staffing / FTE

FTE = max(peak-concurrency, ceil(labor-hours / (shift×availability×operating-days))). Never missions/day = porters. Annual labor OPEX = FTE × wage($17) × burden(1.3) × shift(8) × operating-days. Verified deterministically.

## TABLE 15 — Manual Capacity

Porter workload / cycle time / shift capacity via sweep-line peak concurrency. Not infinite.

## TABLE 16 — Manual CapEx

| Component | Value |
|---|---|
| General tote cart | $500 (PROPOSED only) |
| Linen cart | $800 (PROPOSED only) |
| Existing carts | $0 new-study CapEx |
| Shielded courier container | facility-configured (not fabricated) |

## TABLE 17 — Manual OPEX

Regular wages + overtime (via FTE peak) + cart maintenance ($40/$60/yr). Radiation exposure monitoring = NOT_MODELED (flagged, not $0).

## TABLE 18 — Manual Calibration Gaps

| Gap | Status |
|---|---|
| Radiation exposure economics | NOT_MODELED |
| Route distance (when geometry absent) | ROUTE_NOT_CALIBRATED |

## TABLE 19 — PTS Profiles

| Profile | Capsule | Speed | Bore | Provenance |
|---|--:|--:|--:|---|
| PTS_STANDARD_110MM | 2.0 kg | 6.0 m/s | 110 mm | active repo benchmark preserved |
| PTS_LARGE_160MM | 3.0 kg | 6.0 m/s | 160 mm | CONTROLLED_ENGINEERING_ASSUMPTION |

## TABLE 20 — PTS Physical Parameters

DEFAULT_PTS_NETWORK: 6 stations, 300 m network, 2 kg capsule, 6.0 m/s, dispatch 1.0 min, station handling 1.5 min.

## TABLE 21 — PTS Payload Envelope

Compatible: SPECIMEN_BLOOD, PHARMACY_INFUSION. Bulk linen / large sterile totes explicitly INELIGIBLE. Radiopharmaceutical QUALIFICATION_REQUIRED.

## TABLE 22 — PTS Specimen Validation

General compatible specimen → ELIGIBLE. PTS-sensitive specimen → FACILITY_VALIDATION_REQUIRED until `pts_sensitive_specimen_validated`.

## TABLE 23 — PTS Route-Time Reconciliation

route_time = dispatch(1.0) + network_length/speed + station_handling(1.5). Not porter walking; not instantaneous. Verified.

## TABLE 24 — PTS Capacity / Congestion

`pts_required_station_count` = max(1, average-workload, sweep-line peak concurrency). Not infinite; workload-derived.

## TABLE 25 — PTS Energy

Blower/drive lumped controlled benchmark ($1,000/yr); optional capsule-km coefficient additive (not substituted). Unknown electrical loads NOT_CALIBRATED, never $0.

## TABLE 26 — PTS Maintenance

$8,000/yr network maintenance + residual labor 0.2 FTE. Diverter/controls service NOT_CALIBRATED.

## TABLE 27 — PTS CapEx

stations × $45,000 + network × $250/m (PROPOSED only). Building penetrations/retrofit complexity NOT_CALIBRATED.

## TABLE 28 — PTS OPEX

maintenance + energy + residual labor (0.2 FTE × loaded cost). Known subtotal; total NOT_CALIBRATED.

## TABLE 29 — PTS Calibration Gaps

Blower calibrated power (controlled benchmark), diverter/controls service (NOT_CALIBRATED), building penetrations (NOT_CALIBRATED).

## TABLE 30 — Light AGV/AMR Physical Parameters (`floor_agv_amr_authority`)

| Parameter | Value |
|---|--:|
| Length × width × height | 0.70 × 0.55 × 1.20 m |
| Payload mass / volume | 40 kg / 60 L |
| Speed | 1.2 m/s |
| Battery / usable | 1.0 kWh / 80% |
| Energy / charging power | 0.10 kWh/km / 0.6 kW |
| Availability | 90% |
| Supported streams | SPECIMEN_BLOOD, PHARMACY_INFUSION, STERILE_CLEAN_SUPPLY |
| Radiopharm | QUALIFICATION_REQUIRED |

## TABLE 31 — Heavy AGV/AMR Physical Parameters

| Parameter | Value |
|---|--:|
| Length × width × height | 1.30 × 0.80 × 1.60 m |
| Payload mass / volume | 300 kg / 900 L |
| Speed | 1.0 m/s |
| Battery / usable | 4.0 kWh / 80% |
| Energy / charging power | 0.40 kWh/km / 2.0 kW |
| Availability | 90% |
| Supported streams | CLEAN_LINEN, STERILE_CLEAN_SUPPLY |
| Radiopharm | QUALIFICATION_REQUIRED |

## TABLE 32 — AGV/AMR Eligibility

Judged against the CONFIGURED class only. A payload rejected by light NEVER enlarges it or borrows heavy capacity (no-silent-enlarge, verified). Selecting heavy is an explicit decision.

## TABLE 33 — AGV/AMR Route-Time Reconciliation

T = load + horizontal(dist/speed) + vertical(elevator wait+ride per transition) + door(×delay) + unload + return(symmetric). Robots never teleport between floors (each vertical transition costs elevator time). ROUTE_CALIBRATED/NOT.

## TABLE 34 — AGV/AMR Elevator / Door Model

Elevator wait 2.5 min + ride 1.0 min per transition; door delay 0.25 min per door. First-class delays affecting route time / fleet.

## TABLE 35 — AGV/AMR Fleet Sizing

REQUIRED_FLEET = ceil(missions/day × (cycle + per-mission charging) / (operating-hours × 60 × availability)) × (1 + reserve). Charging duty folded into the cycle. Never a published hospital fleet count.

## TABLE 36 — AGV/AMR Battery / Charging

Battery capacity, usable SoC fraction (80%), energy/km, charging power, charging efficiency (90%), amortized replacement (light $2,000/4 yr; heavy $5,000/4 yr). Battery replacement never $0 when unknown → controlled benchmark.

## TABLE 37 — AGV/AMR Energy

Annual known kWh = (traction + idle) / charging_efficiency (charging losses folded ONCE — traction and charging electricity never double-counted). Facility charging-network standby = NOT_CALIBRATED, never $0. Boundary documented.

## TABLE 38 — AGV/AMR Maintenance

Vehicle preventive+corrective (light $3,500/heavy $6,000 per vehicle-yr) + charging-station maintenance ($800/station-yr) + amortized battery. Vendor service contract NOT_CALIBRATED.

## TABLE 39 — Light AGV/AMR CapEx (fleet 3, 2 stations, 2 elevators, 4 doors)

| Component | Qty | Unit | Value |
|---|--:|--:|--:|
| Vehicles | 3 | $90,000 | $270,000 |
| Charging stations | 2 | $12,000 | $24,000 |
| Fleet-management (once) | 1 | $120,000 | $120,000 |
| Elevator integration | 2 | $25,000 | $50,000 |
| Door/access integration | 4 | $3,000 | $12,000 |
| Install/commissioning (once) | 1 | $40,000 | $40,000 |
| **Known subtotal** | | | **$516,000** |
| Unknown | | | Facility network/server allocation (NOT_CALIBRATED) |

## TABLE 40 — Heavy AGV/AMR CapEx (fleet 3, 2 stations, 2 elevators, 4 doors)

| Component | Qty | Unit | Value |
|---|--:|--:|--:|
| Vehicles | 3 | $130,000 | $390,000 |
| Charging stations | 2 | $12,000 | $24,000 |
| Fleet-management (once) | 1 | $120,000 | $120,000 |
| Elevator integration | 2 | $25,000 | $50,000 |
| Door/access integration | 4 | $3,000 | $12,000 |
| Install/commissioning (once) | 1 | $40,000 | $40,000 |
| **Known subtotal** | | | **$636,000** |

Fleet-manager + install are charged ONCE (not × vehicle) — verified.

## TABLE 41 — Light AGV/AMR OPEX (fleet 3, workload sample)

Known subtotal ≈ **$57,660/yr** = electricity + vehicle maint (3×$3,500) + amortized battery (3×$500) + station maint (2×$800) + fleet software ($30,000 once) + supervision (0.2 FTE × $70,000). Unknown: vendor service contract, network standby.

## TABLE 42 — Heavy AGV/AMR OPEX (fleet 3, workload sample)

Known subtotal ≈ **$67,590/yr** = electricity + vehicle maint (3×$6,000) + amortized battery (3×$1,250) + station maint + software (once) + supervision. Unknown: same categories.

## TABLE 43 — AGV/AMR Calibration Gaps

Vehicle/battery costs = CONTROLLED_ENGINEERING_ASSUMPTION; vendor service contract + facility charging-network standby = NOT_CALIBRATED. None $0-filled.

## TABLE 44 — Four-Technology Physics Parity

| Category | MANUAL | PTS | AGV LIGHT | AGV HEAVY | MRT(ref) |
|---|---|---|---|---|---|
| Payload limit | cart 20–80 kg | 2–3 kg capsule | 40 kg | 300 kg | 5 kg gross |
| Speed | 0.9–1.1 m/s | 6.0 m/s | 1.2 m/s | 1.0 m/s | 10 m/s straight |
| Route time | MODELED | MODELED | MODELED | MODELED | MODELED(canonical) |
| Vertical | elevator wait | station network | elevator wait+ride | elevator wait+ride | canonical |
| Energy | N/A (human) | CONTROLLED_BENCHMARK | MODELED(traction) | MODELED(traction) | canonical |
| Fleet | FTE peak | station peak | workload+charging | workload+charging | canonical carriers |
| Eligibility | broad | narrow | compact | bulk | ≤5 kg |

Physics parity control reports times where eligible; never concludes "fastest = best".

## TABLE 45 — Four-Technology Capacity Parity

| Mode | Capacity basis | Infinite? |
|---|---|---|
| MANUAL | porter peak-concurrency FTE | NO |
| PTS | carrier/station peak-concurrency | NO |
| AGV LIGHT | workload×(cycle+charging)/available | NO |
| AGV HEAVY | workload×(cycle+charging)/available | NO |
| MRT(ref) | canonical heterogeneous carrier fleet | NO |

## TABLE 46 — Four-Technology CapEx Parity (schema)

Every mode exposes KNOWN_CAPEX + UNKNOWN_CAPEX (listed separately, never $0 in subtotal). Manual (carts, PROPOSED), PTS (stations+network), AGV (vehicles+stations+integration once), MRT (owned by canonical authority, reference-only).

## TABLE 47 — Four-Technology OPEX Parity (schema)

Every mode exposes KNOWN_ANNUAL_{LABOR,ENERGY,MAINTENANCE,SOFTWARE,OTHER}_OPEX + UNKNOWN_OPEX_CATEGORIES + KNOWN_ANNUAL_OPEX_SUBTOTAL + TOTAL_OPEX_STATUS = KNOWN_SUBTOTAL_ONLY_TOTAL_NOT_CALIBRATED. NOT_APPLICABLE used where a mode lacks a component (e.g. Manual energy).

## TABLE 48 — Controlled Benchmark Register

49 free-roaming AGV/AMR controlled benchmarks (all `EditableParameter`, unit+source+status explicit, editable, replaceable). Full register in `transport_mode_parity_data.json`. UNLABELED_CONTROLLED_BENCHMARKS = 0.

## TABLE 49 — Unknown / NOT_CALIBRATED Register

| Item | Mode | Status |
|---|---|---|
| Radiation exposure economics | MANUAL | NOT_MODELED |
| Blower calibrated power | PTS | CONTROLLED_BENCHMARK |
| Building penetrations/retrofit | PTS | NOT_CALIBRATED |
| Vendor service contract | AGV | NOT_CALIBRATED |
| Charging-network standby electricity | AGV | NOT_CALIBRATED |
| Facility network/server allocation | AGV | NOT_CALIBRATED |
| Standby/controls/cooling electricity | MRT(ref) | NOT_CALIBRATED (canonical) |

## TABLE 50 — No-Silent-Zero Audit

Unknown CapEx/OPEX/energy listed separately, never in known subtotal; unknown eligibility never ELIGIBLE; unknown capacity never infinite; unknown speed never infinite. Verified by deterministic tests.

## TABLE 51 — No-Double-Counting Audit

PTS CapEx = stations + network (no third term); Manual labor and cart maintenance are separate terms; AGV charging electricity folded into traction once; fleet-manager/software counted once (not × vehicle). Verified.

## TABLE 52 — Transport-Modes-In-Scope Backend

`TransportModesInScope` represents ALL / MANUAL_ONLY / PTS_ONLY / LIGHT_ONLY / HEAVY_ONLY / MRT_ONLY / MANUAL+PTS / MANUAL+MRT / MANUAL+HEAVY / PTS+HEAVY+MANUAL / ALL_EXCEPT_MRT / ALL_EXCEPT_ROBOTS. Backend only, no UI.

## TABLE 53 — Exclusion Sentinel Results (Sec 89)

Scope [MANUAL, PTS] → MRT/AGV are EXCLUDED_BY_SCOPE regardless of eligibility/economics (eligibility gate takes no economics; exclusion dominates). Verified.

## TABLE 54 — Fallback Conservation Results (Sec 90)

INPUT_MISSIONS == ASSIGNED + UNMET in all cases. Scope [MRT] + bulk linen → linen UNMET (Manual excluded, never silently inserted). No mission lost. Verified.

## TABLE 55 — Eligibility Sentinel Results (Sec 91)

Payload exceeding a class's physical envelope stays INELIGIBLE even when that class is the only in-scope mode (economics cannot rescue). Verified.

## TABLE 56 — Radiation Qualification Sentinel Results (Sec 92)

Radiopharm made economically attractive stays QUALIFICATION_REQUIRED for PTS/AGV-light/AGV-heavy. Economics never create qualification. Verified.

## TABLE 57 — Authority Consumer Map (Sec 81-82)

| Authority | Consumer status |
|---|---|
| MANUAL / PTS / RGHT (conventional_transport_authority) | RUNTIME_CONSUMED_NOW (existing four-architecture runtime) |
| `floor_agv_amr_authority` | ISOLATED_AUTHORITY_READY_FOR_NEXT_SUPER_BUILD (consumed by tests) |
| `transport_mode_eligibility_authority` | ISOLATED_AUTHORITY_READY_FOR_NEXT_SUPER_BUILD |
| `transport_mode_scope_authority` | ISOLATED_AUTHORITY_READY_FOR_NEXT_SUPER_BUILD |
| `transport_parity_view` | ISOLATED_AUTHORITY_READY_FOR_NEXT_SUPER_BUILD |
| CURRENT_FOUR_ARCHITECTURE_RUNTIME_USES_PTS / AGV_AMR | **NO** (honest; optimizer integration is the next build) |

## TABLE 58 — MRT Preservation

| Field | Value |
|---|---|
| MRT_CANONICAL_CONFIGURATION_CHANGED | NO |
| MRT_RUNTIME_CHANGED | NO |
| MRT preservation tests | test_mrt_canonical_configuration + test_mrt_canonical_runtime_migration PASS (within 433) |
| MRT in this build | REFERENCE-ONLY (parity view reads canonical authority, recomputes nothing) |

## TABLE 59 — Experiment Preservation

| Field | Value |
|---|---|
| CORRECTED_EXPERIMENT_REPORT_CHANGED | NO |
| CORRECTED_EXPERIMENT_MATRIX_CHANGED | NO |
| PART3E / 3E.1 / 3E.2 / short-half-life logic | UNCHANGED |
| Part 3E test suites | PASS (within 256) |

## TABLE 60 — Regression Results

| Suite group | Count |
|---|--:|
| NEW parity tests (floor_agv 37 + parity 46 + manual_pts 28) | 111 passed |
| Backward-compat transport/conventional/opex/governance/RP-PTS | 202 passed (+1 pre-existing unrelated generator-catalog failure) |
| MRT preservation + infra/equipment/operational_day + mrt_transport_separation | 433 passed |
| Part 3E family + parity tests together | 256 passed |

The single failing test (`test_generator_benchmark_uniform_across_initial_models`) is pre-existing at baseline `cb4d4f4` (proven by stashing this build's changes — it fails identically), asserts a generator-catalog size this build never touched, and is unrelated to transport parity.

## TABLE 61 — Remaining Integration Work

| Item | Status |
|---|---|
| Generalized multi-transport optimizer | NOT IMPLEMENTED (next Super-Build) |
| True Hybrid composition of allowed modes | NOT IMPLEMENTED (authorities ready) |
| Wiring parity authorities into four-architecture runtime | NOT DONE (isolated, ready) |
| Facility-validated radiopharm PTS/AGV qualification | QUALIFICATION_REQUIRED gate present, awaits real qualification data |
| Vendor-calibrated AGV economics | controlled benchmarks; awaits vendor quotes |

## TABLE 62 — Readiness for Generalized Multi-Transport Optimizer

`FUTURE_OPTIMIZER_CONTRACT` documented in `transport_mode_scope_authority`:
TRANSPORT_MODES_IN_SCOPE + TRANSPORT_ELIGIBILITY_AUTHORITY + MODE_SPECIFIC_PHYSICS + MODE_SPECIFIC_ECONOMICS → GENERALIZED CANDIDATE GENERATION. `GENERALIZED_OPTIMIZER_INTEGRATED_NOW = False`. **READY_FOR_GENERALIZED_MULTI_TRANSPORT_OPTIMIZER = YES.**

---

## FINAL SUPER-BUILD REPORT (Sec 99)

```
KIRO_SUPER_BUILD_1 = COMPLETE
STARTING_HEAD = cb4d4f4
SUPER_BUILD_GOVERNANCE_ESTABLISHED = YES   GOVERNANCE_OWNER = engineering_authority.py
MANUAL_AUTHORITY_COMPLETE = YES (reused + parity view)
PTS_AUTHORITY_COMPLETE = YES (extended: profiles, specimen validation, radiopharm QUALIFICATION_REQUIRED)
AGV_AMR_LIGHT_AUTHORITY_COMPLETE = YES
AGV_AMR_HEAVY_AUTHORITY_COMPLETE = YES
TRANSPORT_ELIGIBILITY_AUTHORITY_COMPLETE = YES
TRANSPORT_MODE_SCOPE_AUTHORITY_COMPLETE = YES
TRANSPORT_PARITY_RESULT_CONTRACT_COMPLETE = YES
MANUAL_ROUTE_PHYSICS_COMPLETE = YES   MANUAL_STAFFING_COMPLETE = YES   MANUAL_CAPEX_COMPLETE = YES   MANUAL_OPEX_COMPLETE = YES
PTS_ROUTE_PHYSICS_COMPLETE = YES   PTS_CAPACITY_COMPLETE = YES   PTS_ENERGY_COMPLETE = YES   PTS_MAINTENANCE_COMPLETE = YES
PTS_CAPEX_COMPLETE = YES   PTS_OPEX_COMPLETE = YES   PTS_SPECIMEN_VALIDATION_MODELED = YES   PTS_RADIOPHARMACEUTICAL_DEFAULT = QUALIFICATION_REQUIRED
AGV_AMR_LIGHT_ROUTE_PHYSICS_COMPLETE = YES   AGV_AMR_HEAVY_ROUTE_PHYSICS_COMPLETE = YES
AGV_AMR_FLEET_SIZING_COMPLETE = YES   AGV_AMR_BATTERY_CHARGING_COMPLETE = YES   AGV_AMR_ELEVATOR_DOOR_COMPLETE = YES
AGV_AMR_ENERGY_COMPLETE = YES   AGV_AMR_MAINTENANCE_COMPLETE = YES   AGV_AMR_CAPEX_COMPLETE = YES   AGV_AMR_OPEX_COMPLETE = YES
AGV_AMR_RADIOPHARMACEUTICAL_DEFAULT = QUALIFICATION_REQUIRED
FALLBACK_CONSERVATION_PRESENT = YES   TRANSPORT_MODE_EXCLUSION_PRESENT = YES
NO_SILENT_ZERO_GOVERNOR_PRESENT = YES   NO_DOUBLE_COUNT_GOVERNOR_PRESENT = YES
CONTROLLED_BENCHMARK_REGISTER_PRESENT = YES   UNLABELED_CONTROLLED_BENCHMARKS = 0
NEW_PARITY_TESTS = 111   BACKWARD_COMPATIBILITY_TESTS = 202 passed (+1 pre-existing unrelated)   MRT_PRESERVATION_TESTS = PASS (within 433)
MRT_CANONICAL_CONFIGURATION_CHANGED = NO   MRT_RUNTIME_CHANGED = NO   PART3E_CHANGED = NO
CORRECTED_EXPERIMENT_REPORT_CHANGED = NO   CORRECTED_EXPERIMENT_MATRIX_CHANGED = NO
DECAY_PHYSICS_CHANGED = NO   CYCLOTRON_PRODUCTION_PHYSICS_CHANGED = NO   GENERATOR_PHYSICS_CHANGED = NO
SCANNER_TIMING_CHANGED = NO   PART_3D_FEASIBILITY_LOGIC_CHANGED = NO   EQUAL_BUDGET_CHANGED = NO
FILES_CREATED = floor_agv_amr_authority.py, transport_mode_eligibility_authority.py, transport_mode_scope_authority.py,
                transport_parity_view.py, test_floor_agv_amr_authority.py, test_transport_mode_parity.py,
                test_manual_pts_parity_controls.py, TRANSPORT_MODE_PARITY_AUTHORITY_REPORT.md, transport_mode_parity_data.json
FILES_CHANGED  = engineering_authority.py (+governance registry), transport_technology_authority.py (FLOOR_AGV status)
READY_FOR_TRANSPORT_PARITY_CHECKPOINT = YES
READY_FOR_GENERALIZED_MULTI_TRANSPORT_OPTIMIZER = YES
```

## Hard Completion Gates (Sec 100)

All required gates TRUE: Manual/PTS/AGV-light/AGV-heavy/eligibility/scope authorities COMPLETE; Manual/PTS/AGV CapEx+OPEX COMPLETE; FALLBACK_CONSERVATION + TRANSPORT_MODE_EXCLUSION + NO_SILENT_ZERO + NO_DOUBLE_COUNT PRESENT; UNLABELED_CONTROLLED_BENCHMARKS = 0; NEW_PARITY_TESTS = 111 ≥ 100; MRT_CANONICAL_CONFIGURATION_CHANGED / MRT_RUNTIME_CHANGED / PART3E_CHANGED / CORRECTED_EXPERIMENT_* / DECAY / CYCLOTRON / GENERATOR / SCANNER / PART_3D / EQUAL_BUDGET all NO; DIRECTLY_AFFECTED_REGRESSION = PASS (the single failing test is pre-existing and unrelated).

**KIRO_SUPER_BUILD_1 = COMPLETE.** STOP — no stage/commit/push. The parity work is left uncommitted for review; a separate checkpoint prompt will follow. The generalized multi-transport optimizer is the NEXT Super-Build and is NOT begun here.
