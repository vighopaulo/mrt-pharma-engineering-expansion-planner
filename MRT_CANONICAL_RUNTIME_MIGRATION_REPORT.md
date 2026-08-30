# MRT Canonical Runtime Migration — Report

**Build:** MRT Runtime Migration to Canonical Compact MRT (IMPLEMENT → VERIFY → REPORT → STOP; no commit/push).
**Starting checkpoint:** HEAD `ec02243`, `origin/main = ec02243`, divergence `0 / 0`.
**Canonical authority:** `mrt_canonical_configuration.py` (single source of truth + `MrtRuntimeConfig`).
**Scope:** wire the CURRENT four-architecture MRT/Hybrid runtime (and thereby the Part 3E bouquet) to consume the canonical compact MRT configuration instead of the preserved heavy `PlannerAssumptions`/heavy-fleet defaults, WITHOUT globally repurposing shared assumptions and WITHOUT deleting the heavy scope.

All physical/economic canonical values are `CONTROLLED_ENGINEERING_ASSUMPTION`, never manufacturer-calibrated. This build does **not** rerun any experiment; Part 3E / 3E.1 / 3E.2 / short-half-life reports remain superseded/pending rerun.

---

## TABLE 1 — Starting Repository State

| Item | Value |
|---|---|
| HEAD | `ec02243` |
| origin/main | `ec02243` |
| divergence | 0 / 0 |
| Modified (in-scope) | hybrid_optimization.py, inbound_patient_program.py, mrt_canonical_configuration.py, operational_day_orchestrator.py, shared_mrt_multistream_authority.py, whole_oncology_four_architecture_optimization.py |
| Created | test_mrt_canonical_runtime_migration.py, MRT_CANONICAL_RUNTIME_MIGRATION_REPORT.md |
| Excluded artifact (untracked, untouched) | AS_IS_DIGITAL_TWIN_PHASE_1A_SEAM_REPORT.md |

## TABLE 2 — Pre-Migration Runtime Consumer Chain (heavy)

| Concern | Chain | Heavy value |
|---|---|---|
| Guideway | `evaluate_mrt_dominant`/`evaluate_hybrid_mrt` → `_evaluate_mrt_style_architecture` → `_nuclear_result` → `evaluate_hybrid_zone_candidate` → `compute_inbound_room_guideway_extension` | `PlannerAssumptions.mrt_guideway_capex_per_m` = $5,000/m |
| Flat base | `evaluate_hybrid_zone_candidate` | `PlannerAssumptions.mrt_infrastructure_capex` = $6,000,000 |
| Carrier (embedded) | `evaluate_hybrid_zone_candidate` | `PlannerAssumptions.mrt_carrier_capex_per_installed_unit` = $10,000 |
| Carrier (incremental) | `compute_shared_mrt_economic_result` → `compute_heterogeneous_shared_carrier_fleet` → `compute_carrier_fleet_capex` | $10,000 nuclear / $1,000 general-light |
| Part 3E | `_BOUQUET` → `evaluate_mrt_dominant`/`evaluate_hybrid_mrt` | inherits heavy |

## TABLE 3 — Canonical vs Heavy Configuration

| Parameter | Canonical (current) | Heavy (preserved legacy) |
|---|--:|--:|
| Gross moving mass ceiling | 5.0 kg | (n/a; heavy 12/6.5/18.5 kg carriers) |
| Carrier CapEx | $2,000 | $10,000 |
| Two-way guideway CapEx | $2,500/m | $5,000/m |
| Flat infrastructure base | $0 (none) | $6,000,000 |
| Straight-line speed | 10 m/s | 3.0 m/s horizontal / 1.5 m/s vertical |
| Carrier maintenance | 10% → $200/carrier-yr | 10% of $5k / flat $500 |

## TABLE 4 — Runtime Configuration Injection Seam

| Function | Optional param added | Default | Set to canonical by |
|---|---|---|---|
| `inbound_patient_program.compute_inbound_room_guideway_extension` | `guideway_capex_per_m_override` | None (heavy) | hybrid via config |
| `hybrid_optimization.evaluate_hybrid_zone_candidate` | `mrt_runtime_config` | None (heavy) | `wo4a._nuclear_result` |
| `operational_day_orchestrator.compute_carrier_fleet_capex` | `nuclear_unit_capex_usd`, `general_light_unit_capex_usd` | None (heavy) | het. fleet |
| `shared_mrt_multistream_authority.compute_heterogeneous_shared_carrier_fleet` | `carrier_unit_capex_usd_override` | None (heavy) | shared econ |
| `shared_mrt_multistream_authority.compute_shared_mrt_economic_result` | `mrt_runtime_config` | None (heavy) | `wo4a._evaluate_mrt_style_architecture` |
| `wo4a._nuclear_result` | `mrt_runtime_config` | None | `_evaluate_mrt_style_architecture` (= `CANONICAL_MRT_RUNTIME_CONFIG`) |

`baseline.assumptions` / `PlannerAssumptions` were **NOT** globally repurposed (proven unsafe: independently consumed by equal_budget, optimization, architecture_optimizer, infrastructure_capex, shared_network, ui_logic, reporting_engine — none flow through `evaluate_hybrid_zone_candidate`).

## TABLE 5 — $6M Heavy Flat-Base Removal

| Path | Flat base charged | Replaced by |
|---|--:|---|
| Current MRT | $0 | guideway + carriers + endpoints + (vestibule/controls/install where applicable), no flat base |
| Current Hybrid | $0 | same |
| Part 3E MRT | $0 | inherits current MRT |
| Legacy (`PlannerAssumptions`) | $6,000,000 | unchanged (preserved) |

Empirical: perturbing `mrt_infrastructure_capex` by +$1,000,000 leaves current MRT CapEx unchanged (delta $0).

## TABLE 6 — Carrier Pricing Migration

| Path | Carrier unit | Heavy leak? |
|---|--:|---|
| Current MRT | $2,000 | NO |
| Current Hybrid | $2,000 | NO |
| Part 3E MRT | $2,000 | NO |
| Legacy default (`compute_carrier_fleet_capex` no override) | $10,000 / $1,000 | preserved |

Control: 20 carriers × $2,000 = $40,000.

## TABLE 7 — Guideway Pricing Migration

| Path | Guideway unit | Two-way doubled? |
|---|--:|---|
| Current MRT / Hybrid / Part 3E | $2,500/m | NO |
| Legacy `PlannerAssumptions` | $5,000/m | preserved |

Control: 100 m two-way × $2,500 = $250,000 (not $500,000).

## TABLE 8 — Empirical MRT Sentinel Proof

| Perturbation (+$1,000) | Current MRT CapEx delta | Verdict |
|---|--:|---|
| HEAVY (`PlannerAssumptions` guideway+carrier+base) | $0 | heavy does NOT drive current MRT ✓ |
| CANONICAL (runtime config guideway+carrier) | +$235,000 | canonical DOES drive current MRT ✓ |

Baseline current MRT architecture-specific CapEx = **$4,871,000** (was heavy $11,480,000).

## TABLE 9 — Empirical Hybrid Sentinel Proof

| Perturbation (+$1,000) | Current Hybrid CapEx delta | Verdict |
|---|--:|---|
| HEAVY | $0 | ✓ |
| CANONICAL | +$47,000 | ✓ |

Baseline current Hybrid architecture-specific CapEx = **$981,500** (was heavy $7,106,000).

## TABLE 10 — Empirical Part 3E Sentinel Proof

| Perturbation (+$1,000) | Part 3E MRT CapEx delta | Verdict |
|---|--:|---|
| HEAVY | $0 | ✓ |
| CANONICAL | +$235,000 | ✓ |

Part 3E `_BOUQUET` dispatches MRT_DOMINANT/HYBRID_MRT to the migrated `wo4a` evaluators (never `evaluate_light_mrt_dominant`), so it inherits the canonical runtime.

## TABLE 11 — Mass-Governor Runtime Control

| Case | Fully-loaded mass | MRT missions | Manual fallback | Basis |
|---|--:|--:|--:|---|
| SPECIMEN_BLOOD (normal) | 3.5 kg | 170 | 0 | ≤ 5 kg ⇒ MRT |
| CLEAN_LINEN (normal) | 13.5 kg | 0 | 23 | > 5 kg ⇒ MANUAL |
| SPECIMEN_BLOOD (payload forced 9 kg) | 10.5 kg | 0 | 170 | > 5 kg ⇒ MANUAL **by mass, not name** |

Gate = `evaluate_light_mrt_stream_compatibility(stream)` (ceiling bound to canonical `MAX_GROSS_MOVING_MASS_KG` = 5.0). No per-mission masses fabricated; repository's existing per-stream figures used. No carrier auto-enlargement; no heavy fallback.

## TABLE 12 — Linen Negative Control

| Check | Result |
|---|---|
| CURRENT_MRT_RUNTIME_BULK_LINEN_ASSIGNED_TO_MRT | NO |
| CURRENT_HYBRID_RUNTIME_BULK_LINEN_ASSIGNED_TO_MRT | NO |
| DEFAULT_BULK_LINEN_MODE | MANUAL |
| ROBOT/AGV/AMR_AUTO_INSERTED | NO |
| HEAVY_MRT_CARRIER_SUBSTITUTED_FOR_LINEN | NO |

## TABLE 13 — Compact Specimen Positive Control

| Check | Result |
|---|---|
| MRT_ELIGIBLE | YES (3.5 kg ≤ 5 kg) |
| CANONICAL_COMMON_CARRIER_PLATFORM_USED | YES |
| RADIATION_SHIELDING_FORCED | NO (payload + structure only) |
| SEPARATE_LIGHT_MRT / BLOOD carrier hardware created | NO |

## TABLE 14 — Radiopharmaceutical Positive Control

| Check | Result |
|---|---|
| MRT_ELIGIBLE | YES (integral shielded carrier ≤ 5 kg) |
| CANONICAL_COMMON_CARRIER_PLATFORM_USED | YES |
| LOCALIZED_SHIELDING_REQUIRED | YES |
| POWERED_ONBOARD_REFRIGERATION_INSERTED | NO |
| EXTERNAL_SECOND_PIG_REQUIRED | NO |
| MAX_GROSS_MOVING_MASS_KG | 5.0 |

## TABLE 15 — Speed Semantics

| Segment | Current runtime value | Status |
|---|---|---|
| Canonical straight-line max | 10 m/s | CONTROLLED (config) |
| Route-time horizontal (spatial_benchmark) | 3.0 m/s | HEAVY — not yet migrated (shared route-time physics) |
| Route-time vertical | 1.5 m/s | NOT canonical-defined; not fabricated |
| Curve / transition / station / braking | — | `SEGMENT_SPEED_MODEL_NOT_CALIBRATED = YES` |

`VERTICAL/CURVE/TRANSITION_SPEED_AUTOMATICALLY_SET_TO_10 = NO`.

## TABLE 16 — Route-Time Semantics

| Field | Value |
|---|---|
| CURRENT_MRT_ROUTE_TIME_USES_CANONICAL_STRAIGHT_SPEED | **YES** (SPEED & OPEX completion build — see Tables 31-40) |
| CURRENT_HYBRID_ROUTE_TIME_USES_CANONICAL_STRAIGHT_SPEED | **YES** |
| VERTICAL_ROUTE_SPEED_STATUS | uncalibrated (1.5 m/s legacy; canonical does not define vertical) — PRESERVED, still authoritative |
| CURVE/TRANSITION_ROUTE_SPEED_STATUS | NOT_CALIBRATED (unchanged) |

**SUPERSEDED (SPEED & OPEX completion build):** the earlier limitation noted straight-speed migration was deferred to avoid contaminating shared route-time. That seam is now closed WITHOUT contamination via an explicit per-scenario `mrt_straight_speed_m_per_s_override` threaded only through the CURRENT MRT/Hybrid/Part 3E path (None everywhere else keeps the heavy 3.0 m/s). Vertical (1.5 m/s) / curve / transition / station physics are untouched. See Tables 31-40.

## TABLE 17 — Energy Authority

| Field | Value |
|---|---|
| CURRENT_MRT_RUNTIME_USES_CANONICAL_ENERGY_AUTHORITY | **YES** (SPEED & OPEX completion build — see Tables 41-46) |
| Canonical energy authority available | YES (`mrt_transport_energy_maintenance_authority` E=P·t + `mrt_canonical_configuration.compute_mrt_annual_electricity` motion-power sensitivity) |
| ENERGY_DOUBLE_COUNTING_PRESENT | NO |
| UNKNOWN_ENERGY_COMPONENTS_ZERO_FILLED | NO (standby/controls/cooling remain NOT_CALIBRATED, not $0) |

**SUPERSEDED (SPEED & OPEX completion build):** the current Hybrid/MRT/Part 3E OPEX ledger now sources MRT motion electricity from `compute_mrt_annual_electricity` (E=P·t on the REAL scheduled carrier-km/day) at the canonical $0.15/kWh tariff. Standby/controls/cooling remain NOT_CALIBRATED (reported in `unknown_components`, never $0-filled). See Tables 41-46.

## TABLE 18 — Maintenance Authority

| Field | Value |
|---|---|
| Canonical carrier maintenance | $200/carrier-yr (10% × $2,000) |
| `compute_mrt_carrier_annual_maintenance_usd(1)` | $200 |
| HEAVY_500_DOLLAR_MAINTENANCE_AFFECTS_CURRENT_MRT | NO (canonical authority on $2,000) |

## TABLE 19 — Heavy Configuration Isolation

| Field | Value |
|---|---|
| HEAVY_MRT_CONFIGURATION_STILL_PRESENT | YES (`PlannerAssumptions`, `operational_day_orchestrator`) |
| HEAVY_MRT_CONFIGURATION_USED_BY_CURRENT_MRT | NO (sentinel delta $0) |
| HEAVY_MRT_CONFIGURATION_USED_BY_CURRENT_HYBRID | NO |
| HEAVY_MRT_CONFIGURATION_USED_BY_PART3E | NO |
| Legitimate legacy consumers | equal_budget, optimization, architecture_optimizer, infrastructure_capex, shared_network, ui_logic, reporting_engine, inbound_patient_program (legacy path), operational_day_orchestrator day-orchestration |

## TABLE 20 — Light-MRT Compatibility

| Field | Value |
|---|---|
| SEPARATE_CURRENT_LIGHT_MRT_HARDWARE_REMAINS | NO — the canonical compact MRT IS the current MRT hardware |
| `evaluate_light_mrt_dominant` | remains as a compatibility/historical comparator; prices guideway from the SAME canonical `$2,500/m` (`compute_light_mrt_capex`); not part of the bouquet |
| Single current guideway price | `LIGHT_MRT_GUIDEWAY_CAPEX_PER_M == TWO_WAY_GUIDEWAY_CAPEX_USD_PER_M == $2,500/m` |

## TABLE 21 — Post-Migration Consumer Trace (empirical)

| Question | Answer |
|---|---|
| CURRENT_MRT_ARCHITECTURE_CONSUMES_CANONICAL_REDUCED_MRT | **YES** |
| CURRENT_HYBRID_ARCHITECTURE_CONSUMES_CANONICAL_REDUCED_MRT | **YES** |
| PART3E_BOUQUET_CONSUMES_CANONICAL_REDUCED_MRT | **YES** |
| HEAVY_MRT_CONFIGURATION_USED_BY_CURRENT_MRT | **NO** |
| HEAVY_MRT_CONFIGURATION_USED_BY_CURRENT_HYBRID | **NO** |
| HEAVY_MRT_CONFIGURATION_USED_BY_PART3E | **NO** |
| CURRENT_MRT_CARRIER_UNIT_CAPEX_USD | 2,000 |
| CURRENT_MRT_GUIDEWAY_UNIT_CAPEX_USD_PER_M | 2,500 |
| CURRENT_MRT_FLAT_BASE_CAPEX_USD | 0 |
| CURRENT_MRT_MAX_GROSS_MOVING_MASS_KG | 5.0 |
| CURRENT_MRT_STRAIGHT_MAX_SPEED_M_PER_S | 10.0 (config); route-time still 3.0 (limitation) |
| CURRENT_MRT_CARRIER_MAINTENANCE_USD_PER_YEAR | 200 |
| CURRENT_MRT_BULK_LINEN_ELIGIBLE | NO |

## TABLE 22 — Current Architecture Cost Snapshot (runtime verification only, NOT an experiment)

| Architecture | Architecture-specific CapEx | Known annual OPEX | Changed by migration? |
|---|--:|--:|---|
| MANUAL_CONVENTIONAL | $125,000 | $2,090,320 | NO |
| AUTOMATED_CONVENTIONAL | $1,925,000 | $2,210,772 | NO |
| MRT (current) | $4,871,000 | $1,022,430 | YES (was heavy $11,480,000) |
| HYBRID (current) | $981,500 | $2,231,390 | YES (was heavy $7,106,000) |

`MANUAL_RESULT_CHANGED_BY_MRT_MIGRATION = NO`; `AUTOMATED_RESULT_CHANGED_BY_MRT_MIGRATION = NO`. These values are for runtime verification only and do NOT declare a winner.

## TABLE 23 — Current MRT CapEx Reconciliation (line items)

| Component | Basis | Notes |
|---|---|---|
| Guideway | routed length × $2,500/m | canonical two-way, not lane-doubled |
| Carriers | count × $2,000 | canonical |
| Endpoints | count × $1,000 | existing controlled endpoint assumption |
| Vestibule / controls / installation / vertical transitions | separate line items where applicable | preserved, not folded into base |
| Flat heavy base | **$0** | removed (`FLAT_HEAVY_BASE_CAPEX = 0`) |
| Unknown/NOT_CALIBRATED | disclosed, never $0-filled | — |

## TABLE 24 — Current MRT OPEX Reconciliation

| Component | Status |
|---|---|
| Carrier maintenance | $200/carrier-yr (canonical, 10% × $2,000) |
| Motion / standby / controls / cooling electricity | canonical authority available; current Hybrid ledger uses per-scenario `annual_mrt_energy_kwh` (limitation) — standby/controls/cooling NOT_CALIBRATED, never $0-filled |
| Software/support/inspection | as modeled in existing ledger |
| UNKNOWN_MRT_OPEX_ZERO_FILLED | NO |

## TABLE 25 — Automated Conventional OPEX Reconciliation (unchanged by migration)

| Component | Value |
|---|--:|
| AGV maintenance | $4,000/vehicle-yr |
| AGV energy | $1,500/vehicle-yr |
| AGV supervision | 0.1 FTE |
| PTS maintenance | $8,000/network-yr |
| PTS energy | $1,000/network-yr |
| Battery replacement / fleet software | UNKNOWN (flagged, not fabricated) |

## TABLE 26 — Manual OPEX Reconciliation (unchanged by migration)

| Component | Status |
|---|---|
| Porter FTE / loaded cost / shift / overtime | governed by `PorterOperatingPolicy` (unchanged) |
| MANUAL_WAGE_AUTHORITY_CHANGED_BY_MIGRATION | NO |
| PORTER_FTE_FORMULA_CHANGED_BY_MIGRATION | NO |

## TABLE 27 — Regression Results

| Suite | Result |
|---|---|
| test_mrt_canonical_runtime_migration.py | (see run) |
| test_mrt_canonical_configuration.py | (see run) |
| test_whole_oncology_four_architecture_optimization.py | 200 passed, 1 skipped (2 TEST_LOCKING_OLD_TRUTH updated) |
| test_part3d_physical_feasibility_closure.py | (see run) |
| Part 3E family (aware/campaign/decision-envelope) | (see run) |
| shared MRT / phase3_1 / operational-day / conventional-transport | (see run) |

## TABLE 28 — Physics/Economic Preservation

| Authority | Changed? |
|---|---|
| DECAY_PHYSICS | NO |
| CYCLOTRON_PRODUCTION_PHYSICS | NO |
| GENERATOR_PHYSICS | NO |
| SCANNER_TIMING | NO |
| PART_3D_FEASIBILITY_LOGIC | NO |
| PART_3E_RADIONUCLIDE_LOGIC | NO |
| PART_3E_1_EXPERIMENT_LOGIC | NO |
| PART_3E_2_DECISION_LOGIC | NO |
| EQUAL_BUDGET | NO |
| HYBRID_DECAY_MATH | NO |
| MANUAL_WAGE_AUTHORITY | NO |
| AUTOMATED_CONVENTIONAL_BASE_AUTHORITY | NO |

Only MRT-runtime wiring changed (6 files).

## TABLE 29 — Remaining Calibration Gaps

| Gap | Status |
|---|---|
| Route-time straight speed (current runtime) | **MIGRATED to canonical 10 m/s** (SPEED & OPEX completion build; Tables 31-40) |
| Vertical / curve / transition segment dynamics | NOT_CALIBRATED (preserved; vertical 1.5 m/s still authoritative) |
| Current MRT energy OPEX via canonical energy authority | **RE-ROUTED** to `compute_mrt_annual_electricity` motion E=P·t (Tables 41-46) |
| Standby / controls / cooling electrical power | NOT_CALIBRATED (reported in `unknown_components`, never $0-filled) |
| Internal usable payload volume | NOT_CALIBRATED |

## TABLE 30 — Experiment-Rerun Flags (remain LOCKED)

| Flag | Value |
|---|---|
| PART3E_RERUN_REQUIRED | YES |
| PART3E_1_RERUN_REQUIRED | YES |
| PART3E_2_RERUN_REQUIRED | YES |
| SHORT_HALF_LIFE_EXPERIMENT_RERUN_REQUIRED | YES |

The runtime is now ready for a separately-authorized experiment rerun. The old reports remain superseded until physically rerun. This build does NOT rerun them and does NOT reinterpret them as current.


---

# SPEED & OPEX COMPLETION BUILD (Tables 31-50)

Continues the CURRENT working tree (HEAD `ec02243`, 0/0 divergence, no commit/push).
Closes the two runtime seams the prior build deferred: (1) route-time straight
speed → canonical 10 m/s; (2) MRT/Hybrid/Part 3E energy + maintenance OPEX →
canonical authority. Heavy legacy behaviour preserved for every `None` caller.
No experiment reruns. No fabrication. No zero-fill.

## TABLE 31 — Straight-Speed Migration Seam

| Field | Value |
|---|---|
| Seam | per-scenario `mrt_straight_speed_m_per_s_override: float\|None=None` |
| Threaded via | `NativeDecisionPipelineScenario` → `ProductionClinicalScenario` → `_resolve_mrt_route_profile` |
| Current-runtime source | `MrtRuntimeConfig.max_straight_speed_m_per_s` = 10.0 m/s (`evaluate_hybrid_zone_candidate` MRT request only) |
| Conventional request | UNCHANGED (fairness — Manual/Automated route physics untouched) |
| Legacy/default callers | `None` → heavy `PlannerAssumptions.mrt_horizontal_speed_m_per_s` (3.0 m/s) |
| Vertical / curve / transition / station | UNTOUCHED |
| `run_native_pathway_pipeline` signature | UNCHANGED (no contamination of shared standalone pipeline) |

## TABLE 32 — Files Changed (SPEED seam)

| File | Change |
|---|---|
| `decision_pipeline.py` | field on `NativeDecisionPipelineScenario`; threaded in `_build_schedule_for_batches` |
| `production_clinical_schedule.py` | field on `ProductionClinicalScenario`; consumed in `_resolve_mrt_route_profile` (horizontal only) |
| `spatial_benchmark.py` | kw-only param on `_build_request`, passed into the scenario |
| `hybrid_optimization.py` | MRT `_build_request` passes the canonical straight speed; conv request unchanged |
| `test_phase2b2_final_closure.py` | `_FakeMrtScenario` duck-typed fake gains the new optional field |

## TABLE 33 — 100 m Straight Control (Sec 9)

| Speed | Horizontal seconds for 100 m |
|---|--:|
| Canonical 10 m/s | 10.0 s |
| Heavy 3.0 m/s | 33.33 s |

## TABLE 34 — Route Decomposition Proof (dest F1-R02, benchmark 60×40 both-sides)

| Quantity | Value |
|---|--:|
| Horizontal distance | 33.0 m |
| Vertical distance | 4.0 m |
| H↔V transitions | 2 |
| Observed transport delta (override 10 vs heavy 3.0) | 0.128333 min |
| Expected horizontal-only delta | 0.128333 min |
| Vertical / transition / station terms | INVARIANT |

## TABLE 35 — Speed Sentinel

| Case | Result |
|---|---|
| Perturb heavy horizontal speed UNDER canonical override | Δ = 0 (canonical isolated) |
| Perturb the canonical override | Δ ≠ 0 (override authoritative) |
| Perturb heavy horizontal speed UNDER legacy `None` | Δ ≠ 0 (heavy authoritative for legacy) |

## TABLE 36 — Physics Preservation (SPEED)

| Field | Value |
|---|---|
| Vertical 1.5 m/s still authoritative under canonical override | YES (perturbing it moves transport time) |
| `SEGMENT_SPEED_MODEL_STATUS` | NOT_CALIBRATED (unchanged) |
| Curve / transition / braking dynamics | NOT_CALIBRATED (unchanged) |
| `VERTICAL/CURVE/TRANSITION_SPEED_AUTOMATICALLY_SET_TO_10` | NO |

## TABLE 37 — Decay Consequence (Sec 10, real runtime, mrt_floors={3})

| Metric | Canonical 10 m/s | Legacy 3 m/s |
|---|--:|--:|
| Mean elapsed release→administration (MRT patients) | 1.9883 min | 2.1167 min |
| Mean retained fraction | 0.987526 | 0.986727 |

Faster canonical straight speed → shorter transit (Δ 0.1283 min, == horizontal-only speed delta) → +0.000800 higher retained fraction. Faster ⇒ less in-transit decay ⇒ ≥ retention.

## TABLE 41 — Energy Authority (MIGRATED)

| Field | Value |
|---|---|
| CURRENT_MRT_RUNTIME_USES_CANONICAL_ENERGY_AUTHORITY | **YES** |
| Authority | `mrt_canonical_configuration.compute_mrt_annual_electricity` (motion E=P·t) |
| Motion workload | REAL scheduled MRT carrier-km/day = 2 × Σ(job route segment length)/1000 (round trip) |
| Active-power case | BASE (1.5 kW → 0.041667 kWh/carrier-km @ 36 km/h) |
| Tariff | `CONTROLLED_ELECTRICITY_TARIFF_USD_PER_KWH` = $0.15/kWh (physical kWh kept separate from tariff) |
| Standby / controls / cooling | NOT_CALIBRATED → `unknown_components`, NEVER $0-filled |
| ENERGY_DOUBLE_COUNTING_PRESENT | NO |
| UNKNOWN_ENERGY_COMPONENTS_ZERO_FILLED | NO |

## TABLE 42 — MRT Energy Row (real runtime, mrt_floors={3})

| Build | "MRT energy" qty (kWh/yr) | Unit cost | Annual $ |
|---|--:|--:|--:|
| Canonical | 6.75 (motion, 270 m one-way/day → 0.54 carrier-km/day) | $0.15 | $1.01 |
| Legacy `None` | 25,000 (static per-scenario assumption) | $0.18 | $4,500.00 |

**Honest nuance:** the "MRT energy" row keeps `calibration_status = NOT_CALIBRATED` because standby/controls/cooling are uncalibrated; the kWh value is now canonical motion-physics-derived (workload-scaled), not the prior arbitrary static figure. Full energy remains NOT_CALIBRATED; only motion is known.

## TABLE 43 — Maintenance Authority (MIGRATED)

| Row | Canonical | Legacy `None` (heavy) |
|---|--:|--:|
| MRT carrier maintenance (per carrier-yr) | $200 (10% × $2,000) | $500 |
| Guideway annual maintenance (per m-yr) | $250 ($2,500/m × 10%, "Scenario calibrated input") | $150 ($5,000/m × 3% fallback) |
| HEAVY_500_DOLLAR_MAINTENANCE_AFFECTS_CURRENT_MRT | NO | — |

## TABLE 44 — Stream Distinctness (no merge)

| Stream | Category | Migrated? |
|---|---|---|
| MRT energy (motion electricity) | ENERGY | YES → canonical |
| MRT carrier maintenance | MRT | YES → canonical $200 |
| Guideway annual maintenance | MRT | YES → canonical $250/m |
| MRT carrier allocated electricity | MRT | UNCHANGED (distinct third electricity-adjacent term, $250) |
| MRT support labor | LABOR | UNCHANGED |

## TABLE 45 — Energy + Maintenance Sentinel (real runtime)

| Case | Result |
|---|---|
| Perturb heavy carrier-maint / guideway-frac / guideway-capex UNDER canonical | Δ = $0 on all three MRT rows (isolated) |
| Same perturbation UNDER legacy `None` | carrier +$4,500, guideway +$668,250 (heavy authoritative for legacy) |
| No-double-count | each MRT energy/maintenance row appears exactly once in the hybrid ledger |
| `compute_shared_mrt_economic_result` | consumes hybrid OPEX ledger unchanged; adds only disjoint container OPEX (+CapEx) |

## TABLE 46 — OPEX Seam Files Changed

| File | Change |
|---|---|
| `hybrid_optimization.py` | `_build_hybrid_opex_result` gains `mrt_runtime_config` + `mrt_carrier_km_per_day`; canonical energy/maintenance sourcing; call site computes real carrier-km/day and forwards the config. `mrt_transport_energy_maintenance_authority` imported lazily (circular-import safety). |

## TABLE 47 — Fairness (Manual + Automated Conventional)

| Architecture | CapEx | Annual OPEX | Byte-identical under drastic heavy-MRT perturbation? |
|---|--:|--:|---|
| MANUAL_CONVENTIONAL | $125,000 | $1,219,920 | YES |
| AUTOMATED_CONVENTIONAL | $1,475,000 | $1,320,872 | YES |

Manual/Automated evaluators take no `mrt_runtime_config` and never read MRT authorities — structurally unaffected.

## TABLE 48 — Post-Completion Hard Gates

| Gate | Value |
|---|---|
| CURRENT_MRT_ARCHITECTURE_CONSUMES_CANONICAL_STRAIGHT_SPEED | YES |
| CURRENT_MRT_RUNTIME_USES_CANONICAL_ENERGY_AUTHORITY | YES |
| CURRENT_MRT_RUNTIME_USES_CANONICAL_CARRIER_MAINTENANCE | YES ($200) |
| CURRENT_MRT_RUNTIME_USES_CANONICAL_GUIDEWAY_MAINTENANCE | YES ($250/m) |
| HEAVY_500_DOLLAR_MAINTENANCE_AFFECTS_CURRENT_MRT | NO |
| ENERGY_DOUBLE_COUNTING_PRESENT | NO |
| UNKNOWN_ENERGY_COMPONENTS_ZERO_FILLED | NO |
| MANUAL/AUTOMATED_CONVENTIONAL_UNCHANGED | YES |

## TABLE 49 — Regression (this build, all green, 0 failures)

| Suite group | Count |
|---|--:|
| `test_mrt_canonical_runtime_migration.py` (54 + 20 new speed/OPEX) | 74 |
| four-architecture optimization | 200 (+1 skip) |
| canonical config + reactive + phase3_1 | 143 |
| infra_opex + hybrid family + energy/equipment + shared_mrt | 220 |
| part3e + part3e2 + operational_day + infra_capex + patient_econ + lifecycle | 410 |
| phase2b2 + decision_pipeline | 52 |
| mrt_carrier_fleet + transport_separation + build3c(+1) | 98 |
| transport_spatial 1-4 + conv_route + retention + spatial_benchmark | 203 |
| part3e experiment campaign | 24 |

## TABLE 50 — Experiment-Rerun Flags (remain LOCKED — unchanged)

| Flag | Value |
|---|---|
| PART3E_RERUN_REQUIRED | YES |
| PART3E_1_RERUN_REQUIRED | YES |
| PART3E_2_RERUN_REQUIRED | YES |
| SHORT_HALF_LIFE_EXPERIMENT_RERUN_REQUIRED | YES |

This build does NOT rerun experiments and does NOT reinterpret superseded reports as current. The runtime now consumes the canonical straight speed and canonical energy+maintenance authority; a separately-authorized rerun remains required to refresh the Part 3E/3E.1/3E.2/short-half-life experiment reports.


---

# CHECKPOINT ADDENDUM — Sec 27 Required-Table Completeness

The Speed & OPEX completion tables above (31-50) were authored before the
checkpoint task fixed the exact Sec 27 table titles. This addendum supplies the
three reconciliation tables named explicitly in Sec 27 (38 Motion Energy, 39
Standby/Controls/Cooling, 40 Maintenance) and a crosswalk so every Sec 27
required table is physically present. No table is omitted. Nothing NOT_CALIBRATED
is represented as calibrated.

## Sec 27 Required-Table Crosswalk

| Sec 27 required table | Physically present as |
|---|---|
| 31 Pre-Completion Speed Runtime | Table 16 "Route-Time Semantics" (pre-migration rows, SUPERSEDED note) |
| 32 Post-Completion Speed Runtime | Table 31 "Straight-Speed Migration Seam" + Table 16 (post rows) |
| 33 Speed Sentinel Proof | Table 35 "Speed Sentinel" |
| 34 100 m Straight Route Control | Table 33 "100 m Straight Control" |
| 35 Vertical / Curve / Transition Status | Table 36 "Physics Preservation (SPEED)" + Addendum Table 35B |
| 36 Pre-Completion MRT OPEX Chain | Table 17 (pre) + Table 42/43 "Legacy None" columns |
| 37 Post-Completion MRT OPEX Chain | Table 41/42/43 "Canonical" columns |
| 38 Motion Energy Reconciliation | Addendum Table 38 (below) |
| 39 Standby/Controls/Cooling Reconciliation | Addendum Table 39 (below) |
| 40 Maintenance Reconciliation | Addendum Table 40 (below) |
| 41 Energy Sentinel Proof | Table 45 "Energy + Maintenance Sentinel" |
| 42 MRT OPEX Integration Proof | Table 42 + Table 45 (no-double-count row) |
| 43 Hybrid OPEX Integration Proof | Table 45 (`compute_shared_mrt_economic_result` row) |
| 44 Part 3E OPEX Integration Proof | Table 44 "Stream Distinctness" + Part 3E inherits via `_evaluate_mrt_style_architecture` |
| 45 Manual OPEX Preservation | Table 47 "Fairness" (Manual row) |
| 46 Automated Conventional OPEX Preservation | Table 47 "Fairness" (Automated row) |
| 47 Current Four-Architecture OPEX Snapshot | Addendum Table 47B (below) |
| 48 Physics Preservation | Table 36 + Addendum Table 48B |
| 49 Remaining Calibration Gaps | Table 29 (updated) |
| 50 Experiment-Rerun Readiness | Table 30 + Table 50 (LOCKED) |

## Table 35B — Vertical / Curve / Transition / Station / Braking Status

| Segment | Current speed | Status |
|---|---|---|
| Straight / horizontal | 10.0 m/s | CANONICAL (migrated) |
| Vertical | 1.5 m/s | LEGACY-PRESERVED, still authoritative (not canonical-defined, not fabricated) |
| Curve | — | NOT_CALIBRATED |
| Transition (H↔V) | — | NOT_CALIBRATED (`SEGMENT_SPEED_MODEL_STATUS`) |
| Station approach | — | NOT_CALIBRATED |
| Braking | — | NOT_CALIBRATED |

None auto-set to 10. `VERTICAL/CURVE/TRANSITION/BRAKING_SPEED_AUTOMATICALLY_SET_TO_10 = NO`.

## Table 38 — Motion Energy Reconciliation

| Field | Value |
|---|--:|
| Authority | `mrt_canonical_configuration.compute_mrt_annual_electricity` (motion E=P·t) |
| Active-power case | BASE = 1.5 kW |
| Canonical straight speed | 10 m/s = 36 km/h |
| BASE_MOTION_KWH_PER_CARRIER_KM = 1.5 / 36 | 0.0416666667 |
| Workload (real, mrt_floors={3}) | 270 m one-way/day → 0.54 carrier-km/day round trip |
| Motion kWh/year (300 operating days) | 6.75 |
| Tariff | $0.15/kWh (physical kWh kept separate from tariff) |
| Motion electricity $/year | $1.01 |
| Fabricated annual mission count | NO — real scheduled carrier-km used |

## Table 39 — Standby / Controls / Cooling Reconciliation

| Stream | Status | Contributes to known total? | $0-filled? |
|---|---|---|---|
| Network standby power | NOT_CALIBRATED | NO (in `unknown_components`) | NO |
| Controls power | NOT_CALIBRATED | NO (in `unknown_components`) | NO |
| Guideway cooling power | NOT_CALIBRATED | NO (in `unknown_components`) | NO |

`UNKNOWN_ENERGY_COMPONENTS_ZERO_FILLED = NO`. Each stream is modeled separately and summed at most once; motion is the only KNOWN electricity stream. `ENERGY_DOUBLE_COUNTING_PRESENT = NO`.

## Table 40 — Maintenance Reconciliation

| Row | Canonical current | Legacy `None` (heavy, preserved) |
|---|--:|--:|
| Carrier maintenance | $200/carrier-yr (10% × $2,000) | $500/carrier-yr |
| Guideway maintenance | $250/m-yr ($2,500/m × 10%) | $150/m-yr ($5,000/m × 3% fallback) |
| Maintenance kept separate from electricity | YES | YES |
| `HEAVY_500_DOLLAR_MAINTENANCE_AFFECTS_CURRENT_MRT` | NO | — |

## Table 47B — Current Four-Architecture OPEX / CapEx Snapshot (real runtime, `build_common_project_baseline`, RETROFIT/CAPITAL_PLANNING)

| Architecture | Architecture-specific CapEx | Changed by MRT migration? |
|---|--:|---|
| MANUAL_CONVENTIONAL | $125,000 | NO |
| AUTOMATED_CONVENTIONAL | $1,925,000 | NO |
| MRT_DOMINANT (current canonical) | $4,871,000 | YES (was heavy > $11.48M) |
| HYBRID_MRT (current canonical) | $981,500 | YES (was heavy) |
| PART3E MRT_DOMINANT (inherits canonical) | $4,871,000 | YES |

Manual/Automated byte-identical under drastic heavy-MRT perturbation (structurally never read MRT authorities).

## Table 48B — Physics / Economics Preservation (diff-scoped)

| Field | Value |
|---|---|
| DECAY_PHYSICS_CHANGED | NO (half-life 109.8 identical canonical vs legacy; only elapsed time changed) |
| CYCLOTRON_PRODUCTION_PHYSICS_CHANGED | NO |
| GENERATOR_PHYSICS_CHANGED | NO |
| SCANNER_TIMING_CHANGED | NO |
| PART_3D_FEASIBILITY_LOGIC_CHANGED | NO |
| PART_3E_RADIONUCLIDE_LOGIC_CHANGED | NO |
| PART_3E_1_EXPERIMENT_LOGIC_CHANGED | NO |
| PART_3E_2_DECISION_LOGIC_CHANGED | NO |
| EQUAL_BUDGET_CHANGED | NO |
| HYBRID_DECAY_MATH_CHANGED | NO |
| MANUAL_WAGE_AUTHORITY_CHANGED | NO |
| AUTOMATED_CONVENTIONAL_BASE_AUTHORITY_CHANGED | NO |

Only narrowly-scoped current-MRT runtime wiring files changed.
