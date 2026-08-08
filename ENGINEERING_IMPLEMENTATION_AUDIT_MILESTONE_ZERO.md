# ENGINEERING IMPLEMENTATION AUDIT - MILESTONE ZERO

## 1. Executive Summary

This is a read-only forensic audit of the current repository state.

Key conclusion: the currently executable single-expansion planner (app.py -> optimization.py) does not reproduce the historical observed capex pair ($9.2M conventional, $28.405M MRT). The current code reproduces:

- Conventional CapEx: $11,750,000
- MRT CapEx: $24,405,000
- Difference: $12,655,000

These totals reconcile exactly to the equations in optimization.py for the provided reference scenario (100 -> 180 patients/day, demand cap 180, 3 scanners, 6 injection rooms, 6 uptake rooms, usable doses 120, existing cyclotron yes, 20-minute conventional transport, 30-second MRT transport, 2 MRT-connectable rooms, F-18).

Therefore, if UI users still see ~$9.2M and $28.405M, that indicates a scenario mismatch, stale run, or non-current code path outside the current executable baseline.

High-priority findings include:

- Shared-network module is non-executable in current baseline (import failure due missing model classes).
- Shared-network ledger boolean for backbone charge is incorrect by construction.
- Planner assumptions table labels operating_hours_per_day as minutes.
- ROI label is ambiguous versus implemented multi-year cumulative formula.

## 2. Current Reference Scenario

Scenario used for reproducibility (from request and code defaults):

- Project: MRT Expansion Study
- Current patients/day: 100
- Target patients/day: 180
- Maximum expected demand/day: 180
- Current scanners: 3
- Current injection rooms: 6
- Current uptake rooms: 6
- Current usable doses/day: 120
- Existing cyclotron: Yes
- Conventional transport: 20 min
- MRT transport: 30 sec = 0.5 min
- Existing MRT-connectable rooms: 2
- Revenue per scan: $300
- Operating days/year: 300
- Radionuclide: F-18 (half-life from radionuclides.json)

Evidence:

- Defaults and inputs in app: app.py lines 133-266
- Assumptions defaults: models.py lines 15-36
- Reference execution script run against current code returned:
  - CONVENTIONAL_CAPEX 11750000.0
  - MRT_CAPEX 24405000.0
  - CONVENTIONAL_ROI 1134.0425531914893
  - MRT_ROI 457.4677320221266
  - CONVENTIONAL_PAYBACK 0.8103448275862069
  - MRT_PAYBACK 1.7938257993384785
  - CONV_RETENTION 88.13889028316868
  - MRT_RETENTION 99.68485682924154

## 3. Repository Architecture

Primary executable single-expansion path:

1. app.py builds PlannerInputs and PlannerAssumptions (app.py lines 249-266, ui_logic.py lines 49-65)
2. diagnostics.validate and resolve_half_life_min gate input and radionuclide half-life (diagnostics.py lines 15-53)
3. optimization.conventional and optimization.mrt compute plans (optimization.py lines 60-297)
4. finance.incremental_financials computes annual revenue/net cash, NPV, ROI, payback (finance.py lines 4-37)
5. reporting_engine maps report object to dataframes and Excel export (reporting_engine.py lines 54-166)

Compatibility/wrapper modules exist but mostly re-export:

- resource_optimization_engine.py -> optimization (lines 1-3)
- financial_engine.py -> finance (lines 1-3)
- validation_engine.py -> diagnostics (lines 1-3)
- capacity_engine.py/decay_engine.py/production_engine.py -> engineering helpers

Shared-network code exists in shared_network.py but is currently not importable in this baseline because models.py does not define the classes it imports (ImportError: DevelopmentPhase from models).

## 4. Calculation Data Flow

Single-expansion flow:

1. User inputs in app widgets (app.py lines 158-203)
2. Session assumptions edited/restored (app.py lines 205-240; ui_logic.py lines 30-131)
3. PlannerInputs instantiated (app.py lines 251-266)
4. Validation and half-life resolution (diagnostics.py lines 25-53)
5. Conventional and MRT calculations (optimization.py lines 60-297)
6. Financial metrics computed via throughput-based function (optimization.py lines 10-32 -> finance.py lines 4-37)
7. Results rendered directly from plan objects (app.py lines 289-331)
8. Report tables generated from same PlannerReport object (app.py lines 333-455; reporting_engine.py lines 54-166)
9. CSV/Excel exported from comparison_dataframe and excel_bytes (app.py lines 456-468; reporting_engine.py lines 63-166)

No separate recalculation engine is used in the single-expansion report/export layer.

## 5. Conventional Model

Implemented in optimization.conventional (optimization.py lines 60-146):

- Growth factor:
  growth_factor = target / current (line 63)
- Required assets:
  - required scanners = ceil(current_scanners * growth_factor) (line 65)
  - required injection rooms = ceil(current_injection_rooms * growth_factor) (line 66)
  - required uptake rooms = ceil(current_uptake_rooms * growth_factor) (line 67)
  - required usable doses/day = current_usable_doses * growth_factor (line 68)
- Incremental assets:
  - additional scanners = max(0, required - current) (line 70)
  - additional injection rooms (line 71)
  - additional uptake rooms (line 72)
  - additional doses/day (line 73)
- Production increase percent = max(0, (growth_factor - 1) * 100) (line 84)
- Production blocks = ceil(production_increase_pct / 10) (line 87)
- Cyclotron trigger: no existing cyclotron AND additional_doses > 0 (line 86)
- CapEx assembly (lines 89-98)
- Achieved capacity forced equal to target (line 105)
- Reserve forced to zero in returned plan (line 141)
- Revenue throughput forced to target (line 142)

No conventional optimization/candidate search is present.

## 6. MRT Model

Implemented in optimization.mrt (optimization.py lines 149-297):

Decision loops:

- production_increase_pct in range(0, 401, 10) (line 172)
- add_scanners from required minimum to 7 (line 179)
- new_rooms in range(0, 16) (line 188)
- infra_units in range(1, 5) (line 195)

Derived variables:

- connectable_rooms = existing_mrt_connectable_rooms + new_rooms (line 189)
- total rooms = current injection+uptake + connectable_rooms (line 190)
- guideway_segments = infra_units + max(1, connectable_rooms // 4) (line 196)
- endpoints = 2 + connectable_rooms (line 197)
- guideway capacity = endpoints * (8 + 2*infra_units) (line 204)
- achieved = min(production_cap, scanner_cap, room_cap, guideway_cap) (line 206)
- feasibility requires achieved >= target (line 207)

CapEx assembly:

- fixed mrt_infrastructure_capex (line 214)
- guideway segments * segment capex (line 215)
- endpoints * endpoint capex (line 216)
- added scanners * scanner capex (line 217)
- added rooms * additional_room_capex (line 218)
- production blocks * production expansion capex (line 219)
- optional cyclotron purchase+install (lines 220-224)

Selection objective/tiebreak:

- lexicographic rank (line 277):
  1) minimum capex
  2) minimum new_mrt_rooms
  3) minimum infrastructure_units
  4) minimum additional_scanners
  5) maximum retained_activity_pct
  6) maximum reserve_capacity_per_day

Revenue throughput for MRT is demand-capped:

- revenue_throughput = min(achieved, maximum_expected_demand_per_day) (line 234)

## 7. MRT Optimization

For reference scenario, selected candidate from execution:

- production_increase_pct = 60
- additional_scanners = 4
- new_mrt_rooms = 9
- additional_uptake_rooms = 11
- guideway_segments = 5
- endpoints = 13
- infrastructure_units = 3
- achieved = 182
- reserve = 2

Binding constraint is guideway capacity:

- guideway_capacity_patients_per_day = 182.0
- scanner capacity = 183.6
- room capacity = 414.0
- production capacity = 191.39
- achieved = min(...) = 182

Evidence: optimization.py lines 204-207 and runtime ledger output.

## 8. Conventional CapEx Forensic Ledger

Reference scenario exact conventional capex from code: $11,750,000.

Inputs and assumptions:

- growth_factor = 180/100 = 1.8 (line 63)
- additional_scanners = ceil(3*1.8)-3 = 6-3 = 3 (lines 65,70)
- additional rooms = (ceil(6*1.8)-6) + (ceil(6*1.8)-6) = 5 + 5 = 10 (lines 66-72)
- production increase pct = (1.8-1)*100 = 80% (line 84)
- production blocks = ceil(80/10)=8 (line 87)
- cyclotron_required = False (existing cyclotron yes) (line 86)

Component subtotals (lines 89-98, models.py lines 15-31):

- scanners: 3 * $2,500,000 = $7,500,000
- rooms: 10 * $25,000 = $250,000
- production expansion: 8 * $500,000 = $4,000,000
- cyclotron purchase/install: $0

Total: $7,500,000 + $250,000 + $4,000,000 = $11,750,000 (exact).

## 9. MRT CapEx Forensic Ledger

Reference scenario exact MRT capex from code: $24,405,000.

Selected candidate quantities (runtime output + optimization.py lines 213-225):

- fixed backbone: 1 * $6,000,000 = $6,000,000
- guideway segments: 5 * $1,000,000 = $5,000,000
- endpoints: 13 * $10,000 = $130,000
- added scanners: 4 * $2,500,000 = $10,000,000
- added rooms: 11 * $25,000 = $275,000
- production blocks: ceil(60/10)=6 -> 6 * $500,000 = $3,000,000
- cyclotron: $0 (existing cyclotron yes)

Total: 6,000,000 + 5,000,000 + 130,000 + 10,000,000 + 275,000 + 3,000,000 = $24,405,000 (exact).

## 10. Explanation of the $19M+ CapEx Difference

Current code difference is not $19M+ under reference scenario.

Current reproducible difference:

- $24,405,000 - $11,750,000 = $12,655,000

Difference decomposition (current code):

- MRT fixed infrastructure: +$6,000,000
- MRT guideway segments: +$5,000,000
- MRT endpoints: +$130,000
- Scanner delta vs conventional: (4-3)*$2.5M = +$2,500,000
- Room delta vs conventional: (11-10)*$25k = +$25,000
- Production delta vs conventional: (6-8)*$500k = -$1,000,000

Net: 6,000,000 + 5,000,000 + 130,000 + 2,500,000 + 25,000 - 1,000,000 = $12,655,000.

If users observe $28.405M and ~$9.2M, those values do not match the current executable equations for this scenario.

Classification: HIGH severity reporting/baseline mismatch risk.

## 11. Existing-Asset Audit

Single-expansion planner behavior:

- Conventional subtracts existing scanners and rooms before charging additions (optimization.py lines 70-72).
- Conventional doses growth computed from current usable doses (line 68), and production cost is incremental blocks (line 92).
- Conventional does not repurchase cyclotron when has_existing_cyclotron is true (line 86 and lines 94-97).
- MRT scanner cost is incremental add_scanners from current (lines 179-181,217).
- MRT room cost is incremental add_rooms relative to current total rooms (lines 190-192,218).
- MRT still charges endpoints/guideway/infrastructure as modeled additions; no existing endpoint/guideway concept in single-expansion model.

Result: no confirmed repurchase of existing scanners/rooms/cyclotron in single-expansion path.

## 12. Double-Counting Audit

Single-expansion path:

- Confirmed double counting not proven from code alone.
- Possible double-counting/economic overlap risk:
  - fixed $6M MRT infrastructure plus explicit guideway and endpoint costs are all added (optimization.py lines 214-216) with no scope definition in code for what $6M includes.

Shared-network path:

- Additional rooms are charged both construction and connection modification per room in same phase (shared_network.py lines 408-410). This may be intentional or double counting depending on scope definitions.

## 13. MRT Backbone Audit

- Backbone insertion point: models.py line 15 default; charged in optimization.py line 214.
- Code does not define scope/inclusions for this $6M component.
- Simultaneous separate charging of guideway and endpoints occurs in same capex equation (optimization.py lines 215-216).

Classification: economic-model ambiguity (questionable assumption / possible double counting).

## 14. Production Model

Conventional:

- Production growth tied to activity growth factor, not retained activity (optimization.py line 84).
- Blocks = ceil(production_increase_pct / 10) (line 87).
- Cost = blocks * production_expansion_capex_per_10pct (line 92).

MRT:

- production_cap includes retained activity (line 173-177).
- production_increase_pct is optimization variable, not directly derived from growth factor (line 172).
- production blocks from this chosen percentage (line 211,219).

So pathways are independently computed; MRT is not directly assigned conventional blocks.

## 15. Decay / Retained Activity

Decay equation source:

- retention(t, half_life) = 2^(-t/half_life) (engineering.py lines 2-4).

Half-life source:

- from user override or radionuclide lookup (diagnostics.py lines 15-22).

Reference scenario values:

- half-life (F-18): 109.8 min (runtime)
- conventional t=20 -> retained ~88.1389% (runtime; optimization.py line 61)
- MRT t=0.5 -> retained ~99.6849% (runtime; optimization.py lines 150-156)

Retained activity impact:

- Conventional retained is ledger/display only and does not influence conventional production blocks/cost (conventional formula uses growth_factor, lines 84,87,92).
- MRT retained directly scales production_cap and can bind feasibility/cost (lines 173-177,206).

## 16. 5-Minute vs 20-Minute Transport-Time Investigation

Current code default input for conventional transport in app is 20 minutes (app.py line 175).
Current conventional ledger value is taken directly from inputs.current_average_transport_min (optimization.py line 118).

No 5-minute constant exists in current audited modules. Therefore a 5-minute historical ledger likely came from prior code, a different scenario entry, or stale session state from another baseline.

Classification: unable to reproduce in current code; likely external-state mismatch, not current-engine equation.

## 17. Operating-Hours Unit Investigation

- Model default operating_hours_per_day = 18.0 (models.py line 27).
- Capacity formulas multiply by h*60, therefore h is interpreted as hours (engineering.py lines 6-8).
- assumptions_dataframe formats operating_hours_per_day with format_minutes because it is included in minute_keys (reporting_engine.py lines 122-128,132-139).

Conclusion: underlying calculation uses 18 hours/day, but assumptions report label/unit rendering can present it as minutes.

Classification: unit/labeling defect.

## 18. Scanner Capacity

Equation:

- scanner_capacity(n,h,cycle,availability) = n*h*60/cycle*availability/100 (engineering.py lines 5-6).

Reference MRT candidate:

- total_scanners = 7 (3 existing + 4 additional)
- 7*18*60/35*0.85 = 183.6 patients/day

Matches runtime ledger exactly.

MRT transport time does not enter scanner capacity equation.

## 19. Room Capacity

Equation:

- room_capacity(n,h,service) = n*h*60/service (engineering.py lines 7-8).

In single-expansion MRT selected candidate:

- total_rooms = current_total_rooms + connectable_rooms = 12 + (2+9) = 23
- room_capacity = 23*18*60/60 = 414/day

The ~684/day figure corresponds to n=38 rooms under same assumptions; not produced by current reference candidate.

## 20. Cyclotron Model

Single-expansion conventional:

- Trigger: not existing cyclotron and additional_doses_per_day > 0 (optimization.py line 86).

Single-expansion MRT:

- Trigger: not existing cyclotron and production_increase_pct > 0 (line 210).

Cyclotron capex when triggered:

- purchase + installation (optimization.py lines 94-97 and 220-224; defaults models.py lines 16-17).

Under reference scenario with existing cyclotron yes: both pathways charge 0 cyclotron capex.

## 21. Revenue Model

Revenue formula:

- annual_revenue = throughput_patients_per_day * operating_days_per_year * revenue_per_scan (finance.py lines 13-17).

Conventional throughput:

- fixed to target_patients_per_day (optimization.py line 110 and line 142).

MRT throughput:

- min(achieved, maximum_expected_demand_per_day) (optimization.py line 234).

Reference scenario:

- 180 * 300 * 300 = $16,200,000 for both pathways (exact).

Label correctness:

- UI labels this as annual revenue (app.py lines 298-300), matching implemented formula.

## 22. ROI and Payback

Implemented formulas (finance.py):

- annual_net_cash_flow = annual_revenue - annual_incremental_opex (line 18)
- roi_pct = ((annual_net_cash_flow * analysis_years) - capex) / capex * 100 (lines 24-27)
- payback_years = capex / annual_net_cash_flow if positive else inf (line 29)

This ROI is cumulative over analysis_years, not annual percentage return.

Reference scenario reproduces:

- Conventional ROI 1134.04%, payback 0.8103 years
- MRT ROI 457.47%, payback 1.7938 years

Not matching historical 1526.1% / 368.4% / 0.6 / 2.1 in current baseline.

Classification: ROI label ambiguity (implemented cumulative formula shown as "ROI").

## 23. Shared-Network Implementation Status

Status of shared_network.py in current baseline:

- Source file includes substantial multi-phase network economics logic (shared_network.py lines 218 onward).
- But module import currently fails because models.py lacks DevelopmentPhase/NetworkProfile/ServiceGroup/etc imported by shared_network.py.
- Runtime check: ImportError cannot import name DevelopmentPhase from models.

Therefore in this baseline:

- Implemented in source: yes
- Executable/integrated in active app path: no

Feature status for shared-network capability:

- One shared backbone charge logic: IMPLEMENTED in source (line 403), but ledger flag is defective (line 466).
- Multiple service groups/departments/phases: IMPLEMENTED in source structures/loops.
- Incremental endpoints/guideway/vertical transitions/building connections: IMPLEMENTED in source (lines 334-337, 404-407).
- Crossover year computation: IMPLEMENTED in source (lines 480-502).
- Active in current app baseline: NOT IMPLEMENTED (module not importable and not used by app.py).

## 24. Report / Export Consistency

Single-expansion baseline:

- UI metrics use plan object directly (app.py lines 289-331).
- Detailed report tables use same plan/input object (app.py lines 333-455).
- CSV uses comparison_dataframe(report) (app.py lines 456-461, reporting_engine.py lines 63-101).
- Excel uses comparison/assumptions/ledger dataframe writers from same report object (reporting_engine.py lines 160-166).

No independent capex/revenue/roi recalculation found in reporting_engine.

## 25. Test Adequacy

Current tests found:

- test_model.py: functional behavior checks for defaults, assumptions, linear conventional behavior, demand-capped MRT throughput, report columns.
- test_architecture.py: file existence and basic structure checks.

Coverage strengths:

- Conventional reaches target and reserve=0 is tested.
- MRT throughput demand cap is tested.
- Comparison dataframe includes required columns.

Missing/weak coverage:

- No exact capex reconciliation test (component sum equals total).
- No explicit test for guideway as binding constraint at 182 scenario.
- No tests for ROI formula semantics/labeling.
- No test for operating-hours labeling defect in assumptions table.
- No tests for shared_network importability/executability.
- No end-to-end UI/CSV/Excel equality assertions for numeric totals.

## 26. Confirmed Defects

1) Shared-network module import failure
- Class: D IMPLEMENTATION DEFECT
- Severity: Critical
- Evidence: shared_network.py imports missing model classes; runtime ImportError observed.
- Effect: shared-network study non-executable in this baseline.

2) Shared-network ledger backbone flag is always false
- Class: D IMPLEMENTATION DEFECT
- Severity: High
- Evidence: ledger writes "mrt_backbone_charged_this_phase": not backbone_charged after backbone_charged=True assignment (shared_network.py lines 416,466).
- Effect: forensic ledger misreports backbone charge phase.

3) Report assumption unit mislabel for operating_hours_per_day
- Class: G UNIT/LABELING DEFECT
- Severity: Medium
- Evidence: operating_hours_per_day grouped in minute_keys (reporting_engine.py lines 122-128) and formatted via format_minutes (line 138), while engineering treats as hours (engineering.py lines 6-8).
- Effect: misleading assumptions report presentation.

4) Historical observed capex/roi/payback set not reproducible from current code
- Class: J REPORT/BASELINE CONSISTENCY DEFECT
- Severity: High
- Evidence: runtime reproduction differs materially.
- Effect: audit baseline confusion; indicates stale/non-current run or different scenario/code.

## 27. Suspected Double Counting

Possible (not confirmed) in single-expansion model:

- Fixed MRT backbone plus separate guideway/endpoints without defined scope boundaries.
- Class: F POSSIBLE DOUBLE COUNTING
- Severity: Medium
- Evidence: optimization.py lines 214-216 plus no inclusion definition in models/comments.

Possible in shared-network source model:

- Same phase rooms charged as both construction and connection modification (shared_network.py lines 408-410).
- Class: F POSSIBLE DOUBLE COUNTING
- Severity: Medium

## 28. Missing Engineering Relationships

1) Conventional retained activity does not influence conventional production requirement/cost.
- Class: H MISSING ENGINEERING RELATIONSHIP
- Severity: High
- Evidence: conventional production blocks use growth_factor only (optimization.py lines 84,87,92), retained only logged/displayed (lines 125-126).

2) Single-expansion MRT guideway capacity uses simplified endpoint*linear formula with no route distance/throughput queue dynamics.
- Class: C QUESTIONABLE ASSUMPTION / H
- Severity: Medium
- Evidence: guideway_cap equation line 204.

## 29. Missing Economic Relationships

1) ROI labeled generically while formula is multi-year cumulative net cash return.
- Class: I MISSING ECONOMIC RELATIONSHIP (label semantics)
- Severity: Medium
- Evidence: finance.py lines 24-27; UI labels simply "ROI" (app.py lines 312,327; section 8).

2) No explicit decomposition report of capex components in UI/export for forensic reconciliation.
- Class: I
- Severity: Low
- Evidence: output tables provide totals but not explicit componentized arithmetic across all paths.

## 30. Prioritized Recommendations

(Recommendations only; no code changes performed.)

1. Resolve baseline consistency first: add a reproducibility harness that captures scenario + commit hash + exact outputs in one artifact.
2. Fix shared-network importability by aligning models definitions with shared_network imports or isolating feature behind explicit module boundary.
3. Clarify MRT backbone cost scope and avoid potential overlap with explicit guideway/endpoint charges.
4. Correct assumptions report units for operating_hours_per_day (hours, not minutes).
5. Add regression tests for exact capex component reconciliation and for the 182/day guideway-bound MRT case.

## 31. Known Limitations

- This audit is limited to current repository source and executable behavior in this environment.
- Historical values supplied in prompt were treated as observations to verify, not as truth; they do not match current executable baseline.
- Shared-network findings include both source-level review and importability check; runtime scenario execution for shared-network path was not possible due ImportError.

