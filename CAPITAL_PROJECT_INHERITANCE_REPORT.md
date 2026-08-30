# CAPITAL-PROJECT INHERITANCE & ECONOMIC SCOPE AUTHORITY — KIRO SUPER-BUILD 3

Establishes the doctrine: **PHYSICAL INHERITANCE ≠ ECONOMIC INHERITANCE**.
Existing physical/operational information is inherited by the digital twin
without re-purchasing or re-constructing the existing facility. The engine
distinguishes WHAT EXISTS from WHAT THE PROJECT MUST PAY FOR.

Entirely additive (3 new modules; zero existing files modified). Does NOT
change MRT canonical physics, Part 3E, equal_budget, or SB1/SB2. No commit.

Machine-readable data: `capital_project_inheritance_data.json`.

## TABLE 1 — Basis
| Field | Value |
|---|---|
| Baseline HEAD | `523db71` (SB2 generalized optimizer) |
| Files changed (tracked) | 0 (additive) |
| Files created | capital_project_inheritance_authority.py, capital_project_inheritance_scenarios.py, test_capital_project_inheritance.py, report, data JSON |
| Checkpoint policy | IMPLEMENT → VERIFY → REPORT → STOP (no commit) |

## TABLE 2 — Capital-Scope Trace (existing owners)
| Concept | Owner | Classification |
|---|---|---|
| Project starting state | `StudyConfiguration.project_starting_state` | LEGACY_PRESERVE (referenced) |
| Development context (RETROFIT/GREENFIELD) | `whole_oncology.DevelopmentContext` | LEGACY_PRESERVE |
| EXPANSION as first-class class | (none) | GENUINE_GAP → added |
| Existing facility identity | `existing_facility_asis_twin` | REUSE (reference) |
| Spatial/BIM asset_status + import provenance | `canonical_spatial_authority` | REUSE |
| Incremental-quantity | `infrastructure_capex._incremental_quantity` | REUSE (pattern) |
| CapEx / OPEX | `infrastructure_capex/opex`, `equipment_opex_authority`, `compute_common_project_*` | REUSE |
| Baseline-vs-incremental OPEX split | (none) | GENUINE_GAP → added |
| Transport resource inventory | `generalized_transport_optimizer.ModeEconomics` | REUSE |

## TABLE 3 — Three Canonical Project Classes (Sec 1-2)
| Class | Inherits existing | New construction costed |
|---|---|---|
| EXISTING_FACILITY_RETROFIT | YES | modifications only |
| EXISTING_FACILITY_EXPANSION | YES | new wing/floor + connections |
| GREENFIELD_NEW_FACILITY | NO | full new scope |

## TABLE 4 — Two Orthogonal Asset Axes (clarification A)
Origin (`AssetBaselineOrigin`: EXISTING_BASELINE / NEW_TO_PROJECT / OUT_OF_BASELINE_SCOPE) answers "did it exist before the project?". Action (`AssetProjectAction`: RETAINED_NO_CHANGE / MODIFY / REPLACE / NEW / REMOVE / OUT_OF_SCOPE) answers "what does the project do?". `AssetClassification(origin, action)` preserves both; `economic_state` derives the single cost-treatment label. NEW_TO_PROJECT + retain/modify/replace/remove is rejected as inconsistent.

## TABLE 5 — Seven Asset Economic States + Decomposition (Sec 8-16)
| State | (origin, action) | Charges full acquisition | Target capacity | Target OPEX |
|---|---|---|---|---|
| INHERITED_EXISTING | (EXISTING_BASELINE, RETAINED_NO_CHANGE) | NO | YES | YES |
| RETAINED_NO_CHANGE | (EXISTING_BASELINE, RETAINED_NO_CHANGE) | NO | YES | YES |
| MODIFY | (EXISTING_BASELINE, MODIFY) | NO (mod only) | YES | YES |
| REPLACE | (EXISTING_BASELINE, REPLACE) | YES (replacement, not original) | YES | YES |
| NEW | (NEW_TO_PROJECT, NEW) | YES | YES | YES |
| REMOVE | (EXISTING_BASELINE, REMOVE) | NO (removal only) | NO | NO |
| OUT_OF_SCOPE | (OUT_OF_BASELINE_SCOPE, OUT_OF_SCOPE) | NO | YES (physical) | NO |

## TABLE 6 — Physical ≠ Economic Inheritance (Sec 16-18)
A BIM/CAD/PDF/image object may be inherited for geometry/route/capacity/constraints without its historical CapEx entering the budget. `bim_object_default_economic_state`: RETROFIT/EXPANSION untouched → INHERITED_EXISTING; intervention → NEW; GREENFIELD → NEW. `bim_object_charges_new_capex` True only for NEW/REPLACE. BIM_OBJECT_PRESENT ≠ BIM_OBJECT_NEW_CAPEX.

## TABLE 7 — Capacity-Delta Authority (Sec 21)
INCREMENTAL_REQUIRED = max(TARGET_REQUIRED − RETAINED_USABLE, 0); acquisition = new + replaced. Unknown unit cost → NOT_CALIBRATED (never $0).

## TABLE 8 — Scanner Delta Control (Sec 22)
2 existing usable, 3 required → retained 2, **new 1, acquisition 1** ($2M). Never 3.

## TABLE 9 — Scanner Replacement Control (Sec 23)
2 existing, 1 replaced, target 3 → retained 1 + replacement 1 + new 1; **acquisition 2**. Never 3.

## TABLE 10 — Cyclotron / Generator Delta (Sec 24-25)
Within existing usable capacity → **0 new**. Shortfall (target 2, existing 1) → 1 new. Not auto-purchased because it is an expansion.

## TABLE 11 — Bed/Room Delta (Sec 26)
Existing 30 + new 20 = target 50; existing 30 NOT charged as new construction.

## TABLE 12 — New-Wing 500 m Control (Sec 27) + Connection Work (clarification E)
Existing hospital inherited ($0, not recharged); new wing $12M; connection work separately identifiable ($1.95M = guideway extension + utility + existing-building connection MODIFY). Total incremental $13.95M ≪ $40M existing. Existing-building connection change is a MODIFY line, never a whole-building re-cost.

## TABLE 13 — Vertical Expansion 4→8 (Sec 28)
Floors 1-4 inherited, 5-8 new. Incremental = 4 × $3M = **$12M**, NOT 8 × $3M = $24M.

## TABLE 14 — Retrofit Control (Sec 29)
Room structure inherited ($0); only shielding + HVAC MODIFY charged = **$370K**. Full $800K structure never re-costed.

## TABLE 15 — Greenfield Control + Over-Inheritance Sentinel (Sec 30 / clarification F)
Greenfield: everything NEW, total $37M, **no zero-cost inheritance**. `audit_greenfield_inheritance` flags any silent INHERITED_EXISTING/RETAINED asset as over-inheritance; a deliberately reused external resource must be explicitly project-supplied (`explicitly_reused_external_ids`).

## TABLE 16 — Incremental CapEx Aggregation (Sec 28)
TOTAL_INCREMENTAL = Σ charged per state. Inherited/retained acquisition value disclosed separately (`inherited_asset_value_excluded_usd`), never hidden. Unknown surfaced, never $0-summed.

## TABLE 17 — OPEX Inheritance (Sec 39)
Baseline / retained / removed / new / modification-delta / replacement-delta / target-total / incremental. Examples verified: new scanner (+$180K incremental, target $580K); replacement $200K→$150K (**−$50K saving**); HVAC modify $100K→$80K (**−$20K saving**); inherited scanner keeps $200K target OPEX (not zeroed by inherited CapEx); unknown baseline → NOT_CALIBRATED (not $0).

## TABLE 18 — Unknown-OPEX Identity (clarification B)
One uncertain asset produces 3 reporting-view labels (baseline/retained/target) for traceability, but **`distinct_unknown_count() == 1`** — the same source (`X:BASELINE`) is counted ONCE economically, never triple-counted.

## TABLE 19 — Material/Equipment Economic Scope (Sec 31-33)
16 material categories + 8 equipment categories, each ON/OFF. Scope OFF excludes PROJECT COST only; never deletes geometry/capacity.

## TABLE 20 — Material-Scope Runtime Consumer (clarification D)
`apply_material_economic_scope`: HVAC ON total $12M; HVAC OFF total $10M (cost excluded), `HVAC-1` remains in `physically_present_but_excluded`. Proven for STRUCTURE/HVAC/EQUIPMENT/TRANSPORT_INFRASTRUCTURE. ECONOMIC_SCOPE_OFF_DELETES_PHYSICAL_OBJECT = NO; ECONOMIC_SCOPE_OFF_REMOVES_PROJECT_COST = YES.

## TABLE 21 — Transport Package Reconciliation (Sec 34-38 / clarification C)
`reconcile_transport_package` reconciles a family's COMPLETE resource package (backbone/blower/controls/switches/stations/carriers/track/guideway/endpoints/vehicles/chargers/integration). Shared existing lines reused ($0) unless UPGRADE required. **A single line (e.g. guideway $750K) is `PARTIAL_PACKAGE`, `is_total_project_capex=False`** — never mislabeled as total. Required package lines defined per family in `REQUIRED_PACKAGE_LINES`.

## TABLE 22 — Transport Double-Purchase Sentinels (clarification C)
| Sentinel | Result |
|---|---|
| PTS_SHARED_BACKBONE_DOUBLE_PURCHASED | NO (reused; only new stations/carriers + blower-upgrade charged) |
| AGV_SHARED_PLATFORM_DOUBLE_PURCHASED | NO (fleet-manager reused; only new light+heavy vehicles) |
| RTHS_EXISTING_TRACK_DOUBLE_PURCHASED | NO (fully-retained track $0; only new vehicle) |
| MRT_EXISTING_GUIDEWAY_DOUBLE_PURCHASED | NO (retained guideway not re-charged) |
| PARTIAL_TRANSPORT_CAPEX_MISLABELED_AS_TOTAL | NO (`is_total_project_capex` gate) |

## TABLE 23 — Runtime Authority Consumer Map
See `consumer_map` in data JSON: project-class / asset-state / capacity-delta / incremental-capex / opex-inheritance / transport-package / material-scope-consumer / expansion / greenfield-sentinel each owned by a `capital_project_inheritance_authority` function.

## TABLE 24 — Preservation
| Field | Value |
|---|---|
| MRT_CANONICAL_CONFIGURATION_CHANGED | NO |
| MRT_RUNTIME_PHYSICS_CHANGED | NO |
| PART3E_CHANGED | NO |
| CORRECTED_EXPERIMENT_REPORT/MATRIX_CHANGED | NO |
| EQUAL_BUDGET_CHANGED | NO |
| SB1/SB2 authorities changed | NO (0 tracked files modified) |

## TABLE 25 — Regression Results
| Suite group | Count |
|---|--:|
| New SB3 tests | 94 passed |
| MRT + SB1 parity + SB2 optimizer | 398 passed |
| infra/equipment OPEX + architecture/hybrid/whole_oncology/study_scope | 330 passed, 1 skipped |
| Part 3E family | 169 passed |
| generator batch | 1 PRE_EXISTING_UNRELATED failure (catalog 4 vs 3) |

`PRE_EXISTING_UNRELATED_BASELINE_FAILURE = YES` — SB3 changed 0 tracked files; touches generator_catalog which SB3 never touched; identical to SB1/SB2 checkpoints.

## TABLE 26 — Locked Arithmetic Controls (clarification G — preserved)
2 existing scanners + 3 required → 1 new. 1 retained + 1 replacement + 1 additional → 2 acquisitions. $200K→$150K → −$50K/yr incremental OPEX. 4 existing + 4 new floors → cost 4 not 8. All still pass.

## TABLE 27 — Known Calibration Gaps
Illustrative unit costs are CONTROLLED_ENGINEERING_ASSUMPTION (not calibrated facility facts); unknown baseline/incremental OPEX and transport unit costs preserved as NOT_CALIBRATED, never $0-filled.

---

## FINAL SUPER-BUILD REPORT

```
KIRO_SUPER_BUILD_3 = COMPLETE
STARTING_HEAD = 523db71
CAPITAL_PROJECT_INHERITANCE_OWNER = capital_project_inheritance_authority.py
THREE_PROJECT_CLASSES_COMPLETE = YES (RETROFIT / EXPANSION / GREENFIELD)
SEVEN_ASSET_ECONOMIC_STATES_COMPLETE = YES
ASSET_ORIGIN_VS_ACTION_SEPARATED = YES (clarification A)
EXISTING_RETAINED_DISTINGUISHABLE = YES
EXISTING_MODIFIED_DISTINGUISHABLE = YES
EXISTING_REPLACED_DISTINGUISHABLE = YES
NEW_ASSET_ORIGIN_AND_ACTION_CONSISTENT = YES
PHYSICAL_INHERITANCE_NOT_ECONOMIC_INHERITANCE = YES
BIM_OBJECT_PRESENT_IMPLIES_NEW_CAPEX = NO
CAPACITY_DELTA_AUTHORITY_COMPLETE = YES
INCREMENTAL_CAPEX_COMPLETE = YES
OPEX_INHERITANCE_COMPLETE = YES   OPEX_SAVINGS_PRESERVED = YES
EXISTING_OPEX_ZEROED_BECAUSE_CAPEX_INHERITED = NO
EXISTING_OPEX_RECHARGED_AS_NEW_PROJECT_OPEX = NO
REMOVED_ASSET_OPEX_RETAINED_IN_TARGET = NO
REPLACEMENT_DISPLACED_OPEX_IGNORED = NO
UNKNOWN_EXISTING_OPEX_ZERO_FILLED = NO   UNKNOWN_INCREMENTAL_OPEX_ZERO_FILLED = NO
ONE_UNKNOWN_SOURCE_CAN_APPEAR_IN_MULTIPLE_REPORTING_VIEWS = YES
ONE_UNKNOWN_SOURCE_COUNTED_MULTIPLE_TIMES_ECONOMICALLY = NO
UNKNOWN_OPEX_DOUBLE_COUNTING_PRESENT = NO
TRANSPORT_RESOURCE_PACKAGE_RECONCILIATION_PRESENT = YES
PTS_SHARED_BACKBONE_DOUBLE_PURCHASED = NO
AGV_SHARED_PLATFORM_DOUBLE_PURCHASED = NO
RTHS_EXISTING_TRACK_DOUBLE_PURCHASED = NO
MRT_EXISTING_GUIDEWAY_DOUBLE_PURCHASED = NO
PARTIAL_TRANSPORT_CAPEX_MISLABELED_AS_TOTAL = NO
ECONOMIC_SCOPE_SETTING_HAS_REAL_RUNTIME_CONSUMER = YES
ECONOMIC_SCOPE_OFF_DELETES_PHYSICAL_OBJECT = NO
ECONOMIC_SCOPE_OFF_DELETES_OPERATIONAL_CAPACITY = NO
ECONOMIC_SCOPE_OFF_REMOVES_PROJECT_COST = YES
EXISTING_BUILDING_RECHARGED = NO   NEW_WING_COSTED = YES
CONNECTION_WORK_IDENTIFIABLE = YES   CONNECTION_WORK_INCREMENTAL_CAPEX_INCLUDED_WHERE_MODELED = YES
EXISTING_BUILDING_CONNECTION_MODIFICATION_MAY_BE_MODIFY = YES
GREENFIELD_EXISTING_BUILDING_INHERITED_AT_ZERO_CAPEX = NO
GREENFIELD_EXISTING_EQUIPMENT_INHERITED_AT_ZERO_CAPEX = NO
GREENFIELD_EXISTING_TRANSPORT_INFRASTRUCTURE_INHERITED_AT_ZERO_CAPEX = NO
GREENFIELD_REQUIRED_NEW_SCOPE_COSTED = YES
NEW_INHERITANCE_TESTS = 94
MRT_CANONICAL_CONFIGURATION_CHANGED = NO   MRT_RUNTIME_PHYSICS_CHANGED = NO
PART3E_CHANGED = NO   CORRECTED_EXPERIMENT_REPORT_CHANGED = NO   CORRECTED_EXPERIMENT_MATRIX_CHANGED = NO
EQUAL_BUDGET_CHANGED = NO
DECAY/CYCLOTRON/GENERATOR/SCANNER/PART_3D physics CHANGED = NO (0 tracked files modified)
PRE_EXISTING_UNRELATED_BASELINE_FAILURE = YES (generator catalog 4 vs 3)
FILES_CREATED = capital_project_inheritance_authority.py, capital_project_inheritance_scenarios.py,
                test_capital_project_inheritance.py, CAPITAL_PROJECT_INHERITANCE_REPORT.md,
                capital_project_inheritance_data.json
FILES_CHANGED = (none — entirely additive)
READY_FOR_SUPER_BUILD_3_CHECKPOINT = YES
```

## Hard Completion Gates

All required gates TRUE: three project classes; seven asset states; origin/action separation (A); physical≠economic + BIM governor; capacity-delta; incremental CapEx; OPEX inheritance with savings + no-silent-zero + NOT_CALIBRATED preserved; unknown-OPEX single-identity (B); transport package reconciliation with no double-purchase and no partial-mislabel (C); material-scope runtime consumer (D); expansion connection work (E); greenfield over-inheritance sentinel (F); locked arithmetic controls preserved (G); MRT/Part 3E/equal_budget/SB1/SB2 unchanged; directly-affected regression PASS (the single failing test is pre-existing and unrelated).

**KIRO_SUPER_BUILD_3 = COMPLETE.** STOP — no stage/commit/push. Work left uncommitted for review; a separate checkpoint prompt will follow. No Super-Build 4, UI/UX, LOCKDOWN, or What-If begun.
