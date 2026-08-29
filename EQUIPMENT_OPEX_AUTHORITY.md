# Equipment OPEX Authority

**Type:** ENGINE BUILD (narrow) — physical-driver + monetary-component annual-OPEX authority
**Starting HEAD:** `df7bf03` (origin/main, clean, divergence 0/0)
**Engine files created:** `equipment_opex_authority.py`, `test_equipment_opex_authority.py`
**Engine files modified:** none (composition-only; zero changes to existing engines)
**Gap:** OG-OPEX-1 remains **PARTIAL** (physical driver layer complete; monetary
calibration inputs still unavailable) — this build makes that partiality
*explicit, componentized, and Part-3E-consumable*, without fabricating a single
dollar.

> This is **not** Part 3E, **not** a procurement engine, and **not** a request
> to invent annual equipment costs. It is the canonical seam that turns
> *patient/operational demand → equipment workload → utilization → physical OPEX
> drivers → evidence-based unit costs → annual OPEX components*, keeping every
> unavailable input honestly `NOT_CALIBRATED` / `NOT_AVAILABLE`.

---

## A. Architecture

`equipment_opex_authority.py` is a thin **composition** layer over the existing
physical duty/energy authority. It introduces no new duty-cycle engine, no new
decay/production physics, and no competing catalog.

```
PATIENT / OPERATIONAL DEMAND
   → EQUIPMENT WORKLOAD            (existing: schedule / production plan)
   → UTILIZATION / DUTY            (existing: equipment_energy_opex state-minutes,
                                    cyclotron production cycles, generator life)
   → PHYSICAL OPEX DRIVERS         (this module: EquipmentOpexComponent.physical_*)
   → EVIDENCE-BASED UNIT COSTS     (this module: EquipmentOpexComponent.unit_cost_*)
   → ANNUAL OPEX COMPONENTS        (this module: build_opex_component / _assemble_result)
```

Composed authorities (reused, never duplicated):

| Reused authority | What it provides | This module's use |
|---|---|---|
| `equipment_energy_opex.EquipmentDailyEnergyResult` | schedule-derived state-minutes + `calculated_energy_kwh` + `uncalibrated_state_minutes` + energy calibration status | scanner/cyclotron energy component input |
| `cyclotron_catalog` (`CyclotronCatalogModel`) | `production_calibration_status`, `schedulable_radionuclides` | cyclotron identity + production-calibration disclosure |
| `long_horizon_operational_planning.ProductionCycleRecord` | per-cycle `start/end` minutes | cyclotron beam-on utilization |
| `generator_catalog.GeneratorCatalogModel` | `useful_life_days`, `requires_electrical_power`, economics | generator replacement schedule + procurement/energy status |
| `scanner_catalog.ScannerCatalogModel` | `power_specification_status`, `active_power_kw` | scanner power NOT_CALIBRATED preservation |
| `MRT_ELECTRICITY_TARIFF_USD_PER_KWH` (existing) | `CONTROLLED_ASSUMPTION` tariff ($0.12–0.18/kWh) | energy unit-cost basis (never promoted) |
| `healthcare_integration.EconomicComparabilityStatus` | comparability vocabulary | result comparability status (reused verbatim) |

## B. Evidence hierarchy (reused, not reinvented)

The repository already carries two conceptually-equivalent calibration
vocabularies (lowercase catalog `calibration_status`; UPPERCASE economic
tokens). This module maps both onto a single ordered reference ladder without
introducing competing vocabulary:

```
SITE_CALIBRATED > MANUFACTURER_SPECIFIED > COMMERCIAL_QUOTE > LITERATURE_DERIVED
  > MODELED_ESTIMATE > CONTROLLED_ASSUMPTION > NOT_CALIBRATED > NOT_AVAILABLE
```

- `map_catalog_status_to_evidence()` normalizes a catalog token onto the ladder
  (never inventing a stronger class than the catalog asserts).
- `weakest_evidence(*statuses)` returns the **weakest** class — the strongest
  input must never falsely promote the whole result (Section 7).
- The **physical driver** and the **monetary unit cost** carry **separate**
  evidence classes. Example: cyclotron beam-on hours can be `SITE_CALIBRATED`
  (schedule-derived) while facility kW is `NOT_CALIBRATED` → the energy dollar
  result is `NOT_CALIBRATED`.

## C. Componentization & no-zero-fill

`EquipmentOpexComponent` fields: `component_type`, `physical_quantity`,
`physical_unit`, `physical_evidence_status`, `unit_cost_usd`, `unit_cost_basis`,
`annual_cost_usd`, `calculation_status`, `provenance`, `limitations`.

`build_opex_component()` is the **single no-zero-fill choke point**. A dollar
value is produced **only** when BOTH the physical quantity and the unit cost are
present AND each carries at least `CONTROLLED_ASSUMPTION` evidence. Otherwise
`annual_cost_usd is None` (never `0.0`) and `calculation_status` names exactly
which side is missing (`PHYSICAL_QUANTITY_NOT_CALIBRATED`,
`UNIT_COST_NOT_CALIBRATED`, `NOT_CALIBRATED`, or `NOT_APPLICABLE`).

## D. Scanner findings

- Duty is real (schedule-derived scan-minutes via `equipment_energy_opex`).
- Catalog power is `NOT_CALIBRATED` for all six models (`active_power_kw = null`)
  → scanner **energy dollars remain `NOT_CALIBRATED`**; the physical quantity is
  `None` (never a fabricated `0 kWh`/`$0`), and the uncalibrated duty-minutes are
  preserved on the component's `limitations`.
- Service/maintenance price `NOT_CALIBRATED` (catalog economics all
  `NOT_CALIBRATED`). Never `$0`.
- If site-measured power is ever supplied, the calibrated path annualizes the
  schedule-derived kWh × tariff and reports `CALCULATED`.

## E. Cyclotron findings

- Utilization is real and schedule-derived: `derive_cyclotron_utilization_from_cycles`
  folds `ProductionCycleRecord` intervals into `production_cycles`,
  `beam_on_minutes`, `beam_on_hours` (proof: 2 cycles of 90 min → 3.0 beam-on
  hours). The `DEMAND → CYCLES` direction is preserved; capacity → demand is
  never introduced.
- The cyclotron catalog carries **no facility electrical load** → energy stays
  `NOT_CALIBRATED`. Beam current / EOB activity are **never** converted to
  facility kW (a workload driver is not an electrical load).
- Consumable-use count is a valid driver (cycles × uses/cycle) but the unit cost
  is absent → consumable dollars `NOT_CALIBRATED` (driver preserved, `$` withheld).
- Service price `NOT_CALIBRATED`; any %-of-CapEx rule would be a
  `CONTROLLED_ASSUMPTION`, never `MANUFACTURER_SPECIFIED`, and none is applied.
- **Production calibration status** (a *workload* dimension) is independent of
  OPEX-dollar calibration and is surfaced only as a limitation note — it never
  promotes or demotes an OPEX component.

## F. Generator findings

- A Mo-99/Tc-99m generator behaves as recurring **procurement**, not permanent
  capital. `derive_generator_replacement_schedule` derives generators/horizon in
  **units** from `useful_life_days` (ceiling of horizon/life × concurrent lines;
  proof: 365 d ÷ 14 d = 27 generators). Longer horizon can never reduce the count
  (monotonicity).
- Procurement **dollars** remain `NOT_CALIBRATED` (catalog price absent) → schedule
  `CALCULABLE`, procurement `$` withheld. No speculative market price is inserted.
- Passive lead-shielded column generators (`requires_electrical_power = false`)
  have energy explicitly `NOT_APPLICABLE` — never a fabricated `$0` that would
  inflate the known subtotal or falsely improve comparability.
- Generator decay/elution physics is untouched (consumed, not rewritten).

## G. Utility / service findings

- `LOCAL_ELECTRICITY_TARIFF_STATUS = CONTROLLED_ASSUMPTION` — the existing
  `electricity_cost_per_kwh` / `MRT_ELECTRICITY_TARIFF_USD_PER_KWH` concept is
  reused as the energy unit-cost basis; **never** labeled `MANUFACTURER_SPECIFIED`.
  It is a valid site unit cost awaiting a physical consumption it can multiply.
- `LOCAL_WATER_TARIFF_STATUS`, `LOCAL_WASTE_TARIFF_STATUS`,
  `OTHER_SITE_UNIT_COST_STATUS = NOT_CALIBRATED` (no repository authority).
- `SERVICE_CONTRACT_EVIDENCE_STATUS = NOT_CALIBRATED` (scanner/cyclotron/generator).

## H. Known subtotal vs total OPEX

`known_annual_opex_subtotal_usd` sums **only** calculated components and is always
a float (0.0 when none are calculated — an honest "nothing calibrated yet", not a
claim of zero cost). `total_annual_opex_usd` is `None` and
`total_annual_opex_status = NOT_CALIBRATED` while **any** applicable component is
uncalibrated; the total dollar figure is reported **only** when every applicable
component is `CALCULATED`. This preserves the existing MRT Pharma doctrine that a
known subtotal may be numeric while the total remains `NOT_CALIBRATED`.

## I. Calendar-duty integration

The direction `HOSPITAL MASTER CALENDAR → EQUIPMENT STATE TIME → PHYSICAL
UTILIZATION → OPEX DRIVERS` is authoritative and preserved:
- scanner scan windows → active scanner minutes (`equipment_energy_opex`);
- cyclotron production windows → beam-on minutes (`ProductionCycleRecord`);
- generator useful life → replacement frequency.
`OPEX target → equipment utilization` is never introduced. `annualize_horizon_quantity`
refuses to blindly scale an unrepresentative/short/commissioning horizon (returns
`None` + `HORIZON_NOT_REPRESENTATIVE_REPORT_PERIOD_ONLY`), so a stress-test day is
never extrapolated to a misleading annual figure.

## J. Part 3E interface

`EquipmentOpexResult` exposes exactly what Part 3E Phase 1 needs to compare
candidates honestly, with **no patient-demand mutation** and no method that
alters demand: `known_annual_opex_subtotal_usd`, `total_annual_opex_status`,
`comparability_status`, per-component `calculation_status`, and `limitations`.
Part 3E may proceed with **qualified economics** — a known subtotal plus
explicitly-unknown components — without requiring a fully-calibrated total.

## K. Remaining calibration gaps (OG-OPEX-1, PARTIAL)

Closing OG-OPEX-1 requires, per equipment class, separately-provenanced monetary
inputs that do not exist in the repository today:
- scanner/cyclotron **facility power kW** (energy dollars blocked until supplied);
- **service/maintenance** commercial price (per class);
- cyclotron **consumable** unit costs (targets/foils/ion-source/chemistry/QC);
- **generator procurement** price (and QC/disposal/logistics).
Each must arrive as its own evidence class (weakest governs the component). None
may be back-derived from EOB activity, `nameplate × 8760`, or a fixed %-of-CapEx
presented as manufacturer-specified.

## L. Physical git state

Files created: `equipment_opex_authority.py`, `test_equipment_opex_authority.py`,
`EQUIPMENT_OPEX_AUTHORITY.md`. Governance docs updated:
`MRT_PHARMA_AUTHORITY_INDEX.md`, `MRT_PHARMA_OPEN_GAPS.md` (OG-OPEX-1 refined),
`MRT_PHARMA_PRODUCT_DOCTRINE.md`, `MRT_PHARMA_BUILD_LEDGER.md`. **No engine file
modified. No commit. No push. No stage.**

## M. Regression evidence

- OPEX authority + `equipment_energy_opex` + scanner review = **102 passed**
- cyclotron catalog/fleet/windows/production/estimation/evidence + generator native
  + long-horizon + production-clinical schedule = **224 passed**
- multi-isotope decay + F-18 decay + `equal_budget` + authority index = **158 passed**
- Part 3D physical feasibility = **46 passed**
- capital project API = **27 passed**
- four-architecture optimization = **199 passed, 1 skipped**
