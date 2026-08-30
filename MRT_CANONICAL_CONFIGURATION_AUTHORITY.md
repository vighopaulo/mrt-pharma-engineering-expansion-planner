# MRT Canonical Configuration Authority

**Build:** MRT Canonical Configuration Correction & Legacy-Assumption Eradication
**Type:** Correction build (not a new concept, not a forced-win, not a lockdown/what-if/UI build).
**Starting authority:** branch `main`, HEAD `37a2564`, `origin/main = 37a2564`, divergence `0 / 0`, working tree clean (only allowed untracked artifact `AS_IS_DIGITAL_TWIN_PHASE_1A_SEAM_REPORT.md`).
**New code owner:** `mrt_canonical_configuration.py` (single source of truth).
**Focused test:** `test_mrt_canonical_configuration.py`.

All physical/economic values below are `CONTROLLED_ENGINEERING_ASSUMPTION` or `CONTROLLED_ENGINEERING_ENVELOPE`. None is manufacturer-calibrated.

---

## 1. Correction purpose

The repository accumulated multiple generations of MRT physical and economic assumptions. The current design is the compact reduced MRT design. This build establishes ONE canonical current MRT configuration, adds the mass/volume governors, and corrects the ACTIVE consumers that diverged from the canonical current basis — while preserving (never deleting) the separate documented heavy-MRT scope. It does not attempt to make MRT win; after the correction MRT may still lose, which is acceptable.

Governing chain: forensic audit → one canonical configuration → active-consumer correction → CapEx/OPEX reconciliation → mission-eligibility reconciliation → regression → contaminated-result inventory → stop. Part 3E / 3E.1 / 3E.2 experiments are **not** rerun in this build.

---

## 2. Legacy-assumption trace (MRT_LEGACY_ASSUMPTION_TRACE)

Two parallel MRT bases were found. The repository had **no single** canonical MRT owner before this build.

| File | Symbol | Value | Consumer | Classification | Action |
|---|---|---|---|---|---|
| `shared_mrt_multistream_authority.py` | `LIGHT_MRT_LOADED_MASS_CEILING_KG` | 5.0 kg | mass governor | CURRENT_CORRECT | promoted to canonical |
| `shared_mrt_multistream_authority.py` | `LIGHT_MRT_CARRIER_STRUCTURE_MASS_KG` | 1.5 kg | compatibility | CURRENT_CORRECT | preserved |
| `shared_mrt_multistream_authority.py` | `LIGHT_MRT_STREAM_PAYLOAD_MASS_KG[CLEAN_LINEN]` | 12.0 kg | rejection input | DERIVED_FROM_OBSOLETE (used correctly to reject linen) | preserved as rejection input |
| `shared_mrt_multistream_authority.py` | `LIGHT_MRT_GUIDEWAY_CAPEX_PER_M` | $2,000/m → **$2,500/m** | light-MRT CapEx | ACTIVE_DIVERGENT | **corrected → canonical $2,500/m** |
| `mrt_transport_energy_maintenance_authority.py` | `EMPTY_MRT_CARRIER_MASS_KG` | 2.0 kg | mass basis | CURRENT_CORRECT | bound to canonical |
| `mrt_transport_energy_maintenance_authority.py` | `MAX_MRT_PAYLOAD_KG` | 3.0 kg | mass basis | CURRENT_CORRECT | derived from canonical (5−2) |
| `mrt_transport_energy_maintenance_authority.py` | `MRT_CARRIER_CAPEX_USD` | $5,000 → **$2,000** | carrier CapEx / maintenance | ACTIVE_DIVERGENT | **corrected → canonical $2,000** |
| `models.py` `PlannerAssumptions` | `mrt_guideway_capex_per_m` | $5,000/m | heavy MRT CapEx fallback | ACTIVE_OBSOLETE_PRESERVED | preserved (separate scope) |
| `models.py` `PlannerAssumptions` | `mrt_carrier_capex_per_installed_unit` | $10,000 | heavy MRT CapEx | ACTIVE_OBSOLETE_PRESERVED | preserved (separate scope) |
| `models.py` `PlannerAssumptions` | `mrt_horizontal_speed_m_per_s` / `mrt_vertical_speed_m_per_s` | 3.0 / 1.5 m/s | heavy MRT route time | ACTIVE_OBSOLETE_PRESERVED | preserved; canonical straight speed 10 m/s established separately |
| `operational_day_orchestrator.py` | `NUCLEAR_SHIELDED_CARRIER_EMPTY_MASS_KG` | 12.0 kg | heavy carrier mass | ACTIVE_OBSOLETE_PRESERVED | preserved (separate scope) |
| `operational_day_orchestrator.py` | `CONTROLLED_NUCLEAR_PAYLOAD_MASS_KG` / `CONTROLLED_LINEN_PAYLOAD_MASS_KG` | 6.5 / 12.0 kg | heavy loaded mass (→18.5/17/7) | ACTIVE_OBSOLETE_PRESERVED | preserved (separate scope) |
| `test_operational_day_orchestration.py` | `test_nuclear_empty_mass_is_12kg` etc. | 12/18.5/17/7 kg | heavy-scope tests | TEST_LOCKING_OLD_TRUTH (preserved scope) | left intact |
| `test_phase3_1_...py` | `test_4/5/10` | $5,000 / $2,000/m / $500 | current-config locks | TEST_LOCKING_OLD_TRUTH | **updated to canonical $2,000 / $2,500/m / $200** |

Gaps with **no prior owner**, newly established in the canonical authority: carrier dimensions `0.200 × 0.120 × 0.100 m`, guideway envelope `0.400 × 0.180 m`, and max straight speed `10.0 m/s`. No per-lane guideway doubling and no whole-carrier tungsten were found anywhere (confirmed absent). No universal onboard refrigeration exists (only `NOT_CALIBRATED` superconducting/cryo placeholders).

---

## 3. Authority-chain trace (current owners)

| Concern | Current canonical owner | Notes |
|---|---|---|
| Carrier gross/empty/payload mass | `mrt_canonical_configuration` | 5.0 / 2.0–3.0 / 2.0–3.0 kg |
| Carrier dimensions | `mrt_canonical_configuration` | new: 0.200 × 0.120 × 0.100 m |
| Carrier straight speed | `mrt_canonical_configuration` | new: 10.0 m/s (segment dynamics NOT_CALIBRATED) |
| Carrier CapEx | `mrt_canonical_configuration.CARRIER_CAPEX_USD` | $2,000; energy-authority param now binds to it |
| Guideway dimensions | `mrt_canonical_configuration` | new: 0.400 × 0.180 m two-way envelope |
| Guideway CapEx | `mrt_canonical_configuration.TWO_WAY_GUIDEWAY_CAPEX_USD_PER_M` | $2,500/m; `shared_mrt_multistream_authority` now binds to it |
| MRT energy model | `mrt_transport_energy_maintenance_authority.compute_mrt_mission_energy` (E=P·t) + canonical sensitivity | motion-power sensitivity in canonical module |
| MRT maintenance | `mrt_transport_energy_maintenance_authority` (10%/yr) | now on the $2,000 carrier CapEx |
| Mission eligibility | `mrt_canonical_configuration` governors + `shared_mrt_multistream_authority.evaluate_light_mrt_stream_compatibility` | linen excluded |
| Architecture naming | `whole_oncology_four_architecture_optimization` | MRT_DOMINANT = policy, not hardware |
| Route time | `mrt_auxiliary_systems_authority` / `spatial_benchmark` | distance/speed; curve dynamics NOT_CALIBRATED |
| Fleet sizing | `mrt_carrier_fleet.resolve_mrt_carrier_fleet` | unchanged; single algorithm |

---

## 4. Canonical mass basis

`MAX_GROSS_MOVING_MASS_KG = 5.0` — TOTAL moving mass (carrier + shielding + coils + electronics + insert + payload). This is **not** empty mass. Empty-carrier target 2.0–3.0 kg; payload target 2.0–3.0 kg; both bounded by the 5.0 kg gross ceiling. Internal consistency asserted: 2.0 + 3.0 ≤ 5.0.

## 5. Carrier geometry

`CONTROLLED_ENGINEERING_ENVELOPE` 200 mm × 120 mm × 100 mm (external). Internal usable volume is `NOT_CALIBRATED` (wall/shield/coil thickness uncalibrated).

## 6. Speed semantics

`MAX_STRAIGHT_SPEED_M_PER_S = 10.0` (= 36 km/h) is the straight-segment design speed only. Curve / vertical / transition / junction / station-approach / braking dynamics: `SEGMENT_SPEED_MODEL_STATUS = NOT_CALIBRATED`. Route time computed as distance/straight-speed is a disclosed limitation, not calibrated curve dynamics.

## 7. Carrier structure

One common compact carrier platform (`COMMON_CARRIER_PLATFORM = True`). The carrier IS the transport pig; no second external pig required.

## 8. Shielding

`LOCALIZED_SHIELDING = True` — localized tungsten-composite shielding around the radioactive payload region only, mission-dependent. The whole carrier is not solid tungsten; shielding mass is not applied to non-radioactive missions. Gross mass remains ≤ 5.0 kg.

## 9. Thermal management

`POWERED_ONBOARD_REFRIGERATION = False`. Guideway/environmental cooling, passive conditioning, and mission-specific thermal inserts remain separate legitimate authorities; none is removed.

## 10. Carrier CapEx

`CARRIER_CAPEX_USD = $2,000` (corrects the prior divergent $5,000 Light-MRT default). The heavy $10,000/carrier remains ONLY in the preserved heavy scope.

## 11. Guideway geometry

`CONTROLLED_ENGINEERING_ENVELOPE` ~400 mm × 180 mm, complete two-way.

## 12. Guideway CapEx

`TWO_WAY_GUIDEWAY_CAPEX_USD_PER_M = $2,500` per linear metre of complete two-way guideway — NOT per lane, never doubled to $5,000/m. Corrects the prior divergent $2,000/m. `TWO_WAY_COST_NOT_DOUBLED_BY_LANE_COUNT = YES`.

## 13. Mission envelope

Compact time-sensitive micro-logistics: radiopharmaceutical vials/syringes, blood, specimens, small pharmacy/sterile payloads. Governed jointly by the mass governor and the volume governor.

## 14. Excluded bulky logistics

Bulk linen (`CLEAN_LINEN` / `LAUNDRY_CLEAN_LINEN`) is excluded (`BULK_LINEN_ELIGIBLE = False`) regardless of a contrived below-ceiling mass. The MRT is never enlarged to accommodate linen.

## 15. Complementary Manual semantics

`DEFAULT_BULKY_LOGISTICS_MODE = "MANUAL"`. No AGV/AMR/robot is auto-inserted merely because MRT excludes a mission.

## 16. Architecture naming

Product-facing: **MANUAL_CONVENTIONAL / AUTOMATED_CONVENTIONAL / MRT / HYBRID**.
`MRT_DOMINANT` is a deployment **policy** (all-eligible-ward coverage), not separate hardware — the same pipeline, carriers, and economics as `HYBRID_MRT` with wider coverage. `LIGHT_MRT` is the current design basis (now canonical). Legacy enum names are retained for compatibility only and do not imply legacy hardware.
`PRODUCT_FACING_MRT_ARCHITECTURE_NAME = MRT`; `LEGACY_MRT_DOMINANT_NAME_STILL_ACTIVE = YES (policy)`; `LEGACY_LIGHT_MRT_NAME_STILL_ACTIVE = YES (design basis)`; `LEGACY_NAMES_COMPATIBILITY_ONLY = YES`.

## 17. Energy-model status

`MRT_ENERGY_MODEL_STATUS = CONTROLLED_ENGINEERING_SENSITIVITY`. Motion electricity = E = P·t (route horizontal/vertical decomposition), using a single lumped controlled active-power draw (LOW confidence, not prototype-measured, not kinetic-derived). Kinetic acceleration energy (`compute_acceleration_energy_j`) is a disclosure-only lower bound, never added to the active-power electricity.

## 18. Controlled power sensitivity

| Case | Active power (kW) | kWh/carrier-km @ 36 km/h |
|---|--:|--:|
| LOW | 0.75 | 0.020833 |
| BASE | 1.50 | 0.041667 |
| HIGH | 3.00 | 0.083333 |
| STRESS | 5.00 | 0.138889 |

`KWH_PER_CARRIER_KM = ACTIVE_POWER_KW / 36`. Uses actual carrier-km workload; kinetic energy never double-counted.

## 19. Standby / controls / cooling separation

`NETWORK_STANDBY_POWER_KW_STATUS`, `CONTROLS_POWER_KW_STATUS`, `GUIDEWAY_COOLING_POWER_KW_STATUS` = `NOT_CALIBRATED`. Each stream is modeled separately and summed at most once.

- `MRT_MOTION_ELECTRICITY_SEPARATE = YES`
- `MRT_STANDBY_ELECTRICITY_SEPARATE = YES`
- `MRT_CONTROLS_ELECTRICITY_SEPARATE = YES`
- `MRT_COOLING_ELECTRICITY_SEPARATE = YES`
- `MRT_ELECTRICITY_DOUBLE_COUNTING_PRESENT = NO`

## 20. MRT annual OPEX reconciliation

`compute_mrt_annual_electricity(...)` exposes its inputs (carrier-km/day, operating days, active-power case, speed, standby/controls/cooling kWh/day, tariff) and produces motion/standby/controls/cooling kWh/year plus the known subtotal and cost. NOT_CALIBRATED components are reported in `unknown_components`, never zero-filled. Physical kWh is kept separate from the tariff (`CONTROLLED_ELECTRICITY_TARIFF_USD_PER_KWH = 0.15`, a controlled default; a project-supplied tariff is preserved as PROJECT_SUPPLIED). Maintenance (Section 22) is kept separate from electricity.

Worked control: motion 12.5 + standby 24 + cooling 48 = 84.5 kWh/day × 365 = 30,842.5 kWh/yr; × $0.15 = $4,626.375/yr (controls left NOT_CALIBRATED).

## 21. Automated Conventional OPEX fairness

`AUTOMATED_CONVENTIONAL_OPEX_ZERO_FILLED = NO`. AGV (`DEFAULT_AGV_MODEL`): maintenance $4,000, energy $1,500, supervision 0.1 FTE, integration CapEx separate. Ordinary PTS (`DEFAULT_PTS_NETWORK`): maintenance $8,000, energy $1,000, residual 0.2 FTE. `AUTOMATED_CONVENTIONAL_KNOWN_ANNUAL_OPEX` = fleet×(maintenance+energy) + labor. `AUTOMATED_CONVENTIONAL_UNKNOWN_OPEX` = battery replacement / fleet software (not separately modeled; flagged, not fabricated). No costs invented to make Automated look worse.

## 22. Manual OPEX preservation

`MANUAL_OPEX_CHANGED_BY_MRT_CORRECTION = NO`. Porter wage/loaded multiplier/shift/operating-days/FTE/overtime remain governed by their existing authority. The correction touched only MRT authorities.

## 23. Hybrid assignment semantics

Hybrid means an actual mixture: MRT handles eligible compact/time-sensitive missions; Manual handles MRT-excluded bulky missions by default; Automated Conventional handles a subset only if explicitly selected. MRT infrastructure is not charged for missions it does not serve; excluded missions (linen) fall back to Manual.

## 24. MRT CapEx reconciliation

`canonical_spatial_authority.compute_mrt_transport_only_capex(...)` line-items guideway, carriers, vestibules, endpoints, controls (once), installation/commissioning (once). Controls/install are boolean-once flags (never per-metre). NOT_CALIBRATED lines are excluded, never fabricated. With canonical unit costs:

| Component | Control | Value |
|---|---|--:|
| Guideway (100 m two-way) | 100 × $2,500 | $250,000 (not $500,000) |
| Guideway (500 m two-way) | 500 × $2,500 | $1,250,000 |
| Carriers (20) | 20 × $2,000 | $40,000 |
| Controls | once | $100,000 |
| Installation/commissioning | once | $300,000 |

## 25. Guideway-length semantics

`GUIDEWAY_LENGTH_SEMANTICS`: CapEx length = physical guideway centreline length; the guideway is a complete two-way assembly, so length is not doubled for outbound + return traffic — $2,500/m already prices both directions.

## 26. Carrier-count semantics

Carrier count remains workload/concurrency-derived via the existing `mrt_carrier_fleet.resolve_mrt_carrier_fleet` authority. This build corrected only the unit carrier price ($2,000) and the incompatible mass assumptions; it did not build a new fleet-sizing engine.

## 27. Transport-time limitation

Route travel time uses distance / straight-line speed. Curve/transition/vertical dynamics are `NOT_CALIBRATED`; the resulting time is not claimed as calibrated curve dynamics. Movement animation/trajectory functionality is preserved (untouched).

## 28. Contaminated-result inventory

The Part 3E-family reports consume the four-architecture economics, which include MRT-family CapEx computed under pre-correction values. Classification (reports **not** rewritten in place):

| Report | Physics | Economics | Classification |
|---|---|---|---|
| `RADIONUCLIDE_AWARE_ARCHITECTURE_AUTHORITY_PART_3E.md` | decay/production/scanner STILL_VALID | MRT-family ECONOMICS_SUPERSEDED | PHYSICS_PARTIALLY_SUPERSEDED |
| `PART_3E_1_RADIONUCLIDE_EXPERIMENT_CAMPAIGN_REPORT.md` | retention/required-upstream STILL_VALID | MRT_DOMINANT/HYBRID_MRT rows ECONOMICS_SUPERSEDED | PHYSICS_PARTIALLY_SUPERSEDED |
| `PART_3E_2_DECISION_ENVELOPE_AND_CROSSOVER_REPORT.md` | boundary identity STILL_VALID | MRT-family crossover thresholds ECONOMICS_SUPERSEDED | ECONOMICS_SUPERSEDED |

The decisive preferred→second-best boundary (MANUAL vs AUTOMATED) is CapEx-led and MRT-independent, so the preferred architecture (MANUAL) is expected to remain stable; only MRT-family absolute economics and crossover thresholds are superseded.

## 29. Experiments requiring rerun

- `PART3E_RERUN_REQUIRED = YES` (economics; physics still valid)
- `PART3E_1_RERUN_REQUIRED = YES` (MRT-family economics)
- `PART3E_2_RERUN_REQUIRED = YES` (MRT-family crossover thresholds; preferred architecture likely stable)
- `SHORT_HALF_LIFE_EXPERIMENT_RERUN_REQUIRED = YES` (EXP4/5/6/7 consume MRT transport/economics; decay math itself unchanged)

These are **not** rerun in this build (per the correction governance). The next experiment campaign determines the winner.

## 30. Unresolved calibration gaps

- Internal usable payload volume (wall/shield/coil thickness) — `NOT_CALIBRATED`.
- Curve/transition/vertical segment speed dynamics — `NOT_CALIBRATED`.
- Standby / controls / cooling electrical power — `NOT_CALIBRATED`.
- Localized shielding mass for radiopharmaceutical missions — disclosed best-case ≤ 5 kg, `UNVALIDATED`.
- Automated Conventional battery-replacement / fleet-software OPEX — `UNKNOWN` (flagged, not fabricated).
- Preserved heavy-MRT scope (`models.PlannerAssumptions`, `operational_day_orchestrator`) — retained as a separate documented configuration; not reconciled into the canonical current basis in this build.

**No forced MRT win:** the guideway correction raised cost ($2,000 → $2,500/m) and the carrier correction set $2,000 (not lower); no MRT efficiency/advantage was fabricated.
