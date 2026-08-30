# CORRECTED MRT SCIENTIFIC EXPERIMENT RERUN

## Part 3E → Part 3E.1 → Short-Half-Life → Part 3E.2

Scientific rerun of the existing Part 3E / 3E.1 / 3E.2 experiments against the
**canonical compact MRT runtime** (checkpoint `305297c`). This is NOT an MRT
advocacy exercise: no assumptions were tuned, no physics was changed, no winner
was forced. The experiments were invoked through their **existing** entry points
(the canonical MRT config is threaded internally, so a plain rerun uses it) and
report whatever the model produces.

Machine-readable full result matrix: `corrected_mrt_experiment_result_matrix.json`.

---

## TABLE 1 — Repository / Experiment Basis

| Field | Value |
|---|---|
| Starting HEAD | `305297c` (MRT canonical runtime migration complete + pushed) |
| origin/main | `305297c` (divergence 0/0) |
| Baseline builder | `whole_oncology_four_architecture_optimization.build_common_project_baseline()` (day 2026-02-02, seed 42) |
| Development context / study scope | RETROFIT / CAPITAL_PLANNING |
| Part 3E entry | `part3e_radionuclide_aware_architecture.evaluate_radionuclide_aware_architectures` |
| Part 3E.1 entry | `part3e_radionuclide_experiment_campaign.run_full_campaign` |
| Part 3E.2 entry | `part3e2_decision_envelope.build_decision_envelope` |
| Ranking rule | `wo4a.rank_cost_only` (feasible, ascending lifecycle cost) — NO bonus |
| Annuity factor (8% / 10 yr) | 6.710081 |

## TABLE 2 — Frozen MRT Configuration (verified before rerun)

| Field | Value |
|---|--:|
| Carrier CapEx | $2,000 |
| Guideway CapEx (two-way) | $2,500/m |
| Max gross moving mass | 5.0 kg |
| Straight cruise speed | 10.0 m/s |
| Heavy $6M flat base charged | $0 (off) |
| Carrier maintenance | $200/carrier-yr (10% × $2,000) |
| Guideway maintenance | $250/m-yr ($2,500/m × 10%) |
| Electricity tariff | $0.15/kWh |
| Bulk linen MRT-eligible | NO (default MANUAL) |
| `MRT_CONFIGURATION_FROZEN` | YES |

## TABLE 3 — Frozen Physics Authorities

| Authority | Status |
|---|---|
| Radionuclide half-lives (`radionuclides.json`) | UNCHANGED |
| Decay equation (`multi_isotope_decay`) | UNCHANGED |
| Cyclotron production / generator equations | UNCHANGED |
| Scanner / clinical timing | UNCHANGED |
| Patient demand logic | UNCHANGED |
| Part 3D physical-feasibility logic | UNCHANGED |
| Transport geometry | UNCHANGED |
| Economic discounting / revenue | UNCHANGED |
| Manual wage / Automated Conventional authorities | UNCHANGED |
| `EXPERIMENT_PHYSICS_FROZEN` | YES |

## TABLE 4 — Corrected Four-Architecture Baseline (Part 3E, canonical)

| Metric | Manual Conventional | Automated Conventional | MRT (Dominant) | Hybrid |
|---|--:|--:|--:|--:|
| Architecture-specific CapEx | $125,000 | $1,925,000 | $4,871,000 | $981,500 |
| Known annual OPEX (subtotal) | $1,750,320 | $1,870,772 | $5,721,013 | $6,912,571 |
| Lifecycle cost (known) | $11,869,790 | $14,478,032 | $43,259,463 | $47,365,414 |
| Feasible | YES | YES | YES | YES |
| Physical feasibility | FEASIBLE_WITH_UNCALIBRATED_PRODUCTION_CAPACITY (all four) ||||
| Cost-only rank | 1 | 2 | 3 | 4 |
| Pareto member | YES | — | — | — |
| Preferred | **MANUAL_CONVENTIONAL** ||||

## TABLE 5 — Baseline CapEx Comparison / Reconciliation

| Component | Manual | Automated | MRT | Hybrid |
|---|--:|--:|--:|--:|
| Architecture-specific CapEx | $125,000 | $1,925,000 | $4,871,000 | $981,500 |
| Common inherited (scanners/rooms/cyclotron, RETROFIT) | shared, not new | shared | shared | shared |
| Heavy $6M flat MRT base | — | — | $0 (removed) | $0 (removed) |
| Carrier unit price | n/a | n/a | $2,000 | $2,000 |
| Guideway unit price | n/a | n/a | $2,500/m | $2,500/m |

MRT/Hybrid CapEx is now the canonical compact basis (carriers $2,000, guideway $2,500/m two-way, no $6M flat base). Manual ($125,000 conventional-transport allowance) and Automated ($1,925,000 AGV/PTS/integration) are unchanged.

## TABLE 6 — Baseline OPEX Comparison (known subtotal; total NOT_CALIBRATED)

| Stream | Manual | Automated | MRT | Hybrid |
|---|--:|--:|--:|--:|
| Known annual OPEX subtotal | $1,750,320 | $1,870,772 | $5,721,013 | $6,912,571 |
| MRT motion electricity | — | — | canonical E=P·t (~$1/yr at benchmark workload) | canonical |
| MRT standby / controls / cooling | — | — | NOT_CALIBRATED (never $0) | NOT_CALIBRATED |
| MRT carrier maintenance | — | — | $200/carrier-yr | $200/carrier-yr |
| MRT guideway maintenance | — | — | $250/m-yr | $250/m-yr |
| Total OPEX calibration status | KNOWN_SUBTOTAL_ONLY_TOTAL_NOT_CALIBRATED (all four) ||||

**Unknown OPEX is visible, not zero-filled.** MRT standby/controls/cooling electricity and full service/procurement remain NOT_CALIBRATED.

## TABLE 7 — Baseline Operational Comparison

| Metric | Manual | Automated | MRT | Hybrid |
|---|--:|--:|--:|--:|
| Nuclear retention-qualified completed | benchmark canonical population (identical basis, all four) ||||
| Porter FTE | > 0 | last-mile residual | 0 | fallback porters |
| Automation / MRT FTE | 0 | AGV/PTS | MRT support | MRT support |
| Binding physical constraint | derived per-mode (never a universal transport scalar) ||||

Four-architecture economics are anchored to the validated benchmark single-radionuclide nuclear basis (joint-scheduling governor); radionuclide identity does not alter architecture economics/ranking at a fixed basis. Radionuclide-specific consequences appear in the decay / required-upstream-activity / production / scanner / transport observation tables.

## TABLE 8 — Baseline Radioactive-Retention Comparison (MANUAL vs MRT)

| | Manual | MRT |
|---|--:|--:|
| Transport time (benchmark worst-case route) | 3.908 min | 1.972 min |
| Δ transport (MRT − Manual) | | −1.936 min |

Retention consequences are radionuclide-specific — see Tables 10–17.

## TABLE 9 — Baseline Economic Comparison (Δ vs MANUAL)

| Architecture | Δ CapEx | Δ known annual OPEX | Δ known lifecycle |
|---|--:|--:|--:|
| MANUAL_CONVENTIONAL | $0 | $0 | $0 |
| AUTOMATED_CONVENTIONAL | +$1,800,000 | +$120,452 | +$2,608,243 |
| MRT_DOMINANT | +$4,746,000 | +$3,970,693 | +$31,389,673 |
| HYBRID_MRT | +$856,500 | +$5,162,251 | +$35,495,624 |

Revenue and payback/IRR are not modeled as a positive objective at this controlled benchmark (no CapEx ceiling / revenue-per-scan configured); the decision objective the project supplies is lifecycle cost. Reported honestly rather than fabricating an IRR.

## TABLE 10 — Radionuclide Half-Life Table (authority)

| Radionuclide | Half-life (min) |
|---|--:|
| O-15 | 2.04 |
| N-13 | 9.97 |
| C-11 | 20.3 |
| Ga-68 | 67.7 |
| F-18 | 109.8 |
| Tc-99m | 360.0 |

## TABLE 11 — F-18 Results (reference PET radionuclide)

| Metric | Value |
|---|---|
| Demand (control) | 32 patients @ 370 MBq |
| Manual transport / retained | 3.908 min / 0.7822 |
| MRT transport / retained | 1.972 min / 0.7918 |
| Δ retained (MRT − Manual) | +0.0096 |
| Required upstream activity (Manual → MRT) | 473.0 → 467.3 MBq |
| Preferred architecture | MANUAL_CONVENTIONAL |
| Production gate | PRODUCTION_SUFFICIENT (GE PETtrace calibrated) |

## TABLE 12 — C-11 Results (t½ 20.3 min)

| Metric | Value |
|---|---|
| Demand (control) | 6 @ 555 MBq, cyclotron IBA_CYCLONE_KIUBE |
| Manual transport / retained | 3.908 min / 0.2649 |
| MRT transport / retained | 1.972 min / 0.2830 |
| Δ retained | +0.0181 |
| Required upstream (Manual → MRT) | 2,095.4 → 1,961.4 MBq |
| Preferred architecture | MANUAL_CONVENTIONAL |

## TABLE 13 — N-13 Results (t½ 9.97 min)

| Metric | Value |
|---|---|
| Demand (control) | 6 @ 740 MBq, cyclotron IBA_CYCLONE_KIUBE |
| Manual transport / retained | 3.908 min / 0.06687 |
| MRT transport / retained | 1.972 min / 0.07650 |
| Δ retained | +0.00963 |
| Required upstream (Manual → MRT) | 11,066.6 → 9,672.9 MBq |
| Preferred architecture | MANUAL_CONVENTIONAL |

## TABLE 14 — O-15 Results (t½ 2.04 min)

| Metric | Value |
|---|---|
| Demand (control) | 6 @ 1110 MBq, cyclotron IBA_CYCLONE_KIUBE |
| Manual transport / retained | 3.908 min / 1.81e-6 |
| MRT transport / retained | 1.972 min / 3.50e-6 (~2× Manual) |
| Δ retained | +1.69e-6 (nearly doubles the retained fraction) |
| Required upstream (Manual → MRT) | 612,042,408 → 317,016,415 MBq (−295 M) |
| Production gate | PRODUCTION_NOT_CALIBRATED (never fabricated) |
| Preferred architecture | MANUAL_CONVENTIONAL |

O-15 is the extreme case: even MRT's shorter transit leaves an infeasibly small retained fraction over the benchmark route; MRT roughly halves the already-astronomical required upstream activity, but neither mode makes O-15 clinically practical at this route length.

## TABLE 15 — Ga-68 Results (t½ 67.7 min)

| Metric | Cyclotron arm | Generator arm |
|---|---|---|
| Demand (control) | 10 @ 185 MBq (SUMITOMO_CYPRIS_MP_30) | 10 @ 185 MBq (ECKERT_ZIEGLER_GALLIAPHARM) |
| MRT feasibility | FEASIBLE_WITH_UNCALIBRATED_PRODUCTION_CAPACITY | FEASIBLE_WITH_UNCALIBRATED_PRODUCTION_CAPACITY |
| Δ retained (MRT − Manual) | +0.0134 | +0.0134 |
| Source identity | CYCLOTRON (NOT_CALIBRATED, real identity) | GENERATOR daughter (procurement/service NOT_CALIBRATED) |
| Preferred architecture | MANUAL_CONVENTIONAL | MANUAL_CONVENTIONAL |

## TABLE 16 — Tc-99m Results (t½ 360 min, SPECT)

| Metric | Value |
|---|---|
| Appears in | baseline control (18 @ 740) + mixed PET+SPECT (16 @ 740) |
| Half-life | 360 min (long; decay over transport minor) |
| PET/SPECT scanner pools | kept distinct (no silent sharing) |
| Preferred architecture | MANUAL_CONVENTIONAL |

## TABLE 17 — Short-Half-Life Cross-Radionuclide Comparison (F-18 reference)

| Radionuclide | t½ (min) | Manual retained | MRT retained | MRT/Manual ratio | Req. upstream Δ (MRT−Manual) |
|---|--:|--:|--:|--:|--:|
| F-18 | 109.8 | 0.7822 | 0.7918 | 1.012× | −5.7 MBq |
| C-11 | 20.3 | 0.2649 | 0.2830 | 1.068× | −134 MBq |
| N-13 | 9.97 | 0.0669 | 0.0765 | 1.144× | −1,394 MBq |
| O-15 | 2.04 | 1.81e-6 | 3.50e-6 | 1.93× | −295,025,993 MBq |

The MRT retention advantage grows monotonically as half-life shortens — physically expected (a fixed transport-time saving is a larger fraction of a shorter half-life).

## TABLE 18 — Distance Sensitivity Matrix (retained fraction; benchmark route × multiplier)

| Radionuclide | 1.0× Manual | 1.0× MRT | 3.0× Manual | 3.0× MRT |
|---|--:|--:|--:|--:|
| F-18 | 0.7822 | 0.7918 | 0.7684 | 0.7848 |
| C-11 | 0.2649 | 0.2830 | 0.2406 | 0.2697 |
| N-13 | 0.0669 | 0.0765 | 0.0550 | 0.0694 |
| O-15 | 1.81e-6 | 3.50e-6 | 6.96e-7 | 2.17e-6 |

Distance sweep = 0.5×/1.0×/1.5×/2.0×/3.0× the benchmark worst-case route (95 m / 32 m vertical / 2 transitions at 1.0×). The MRT retained-fraction advantage widens with distance for every radionuclide, most dramatically for O-15.

## TABLE 19 — Demand / Patient-Volume Sensitivity Matrix

| Radionuclide | Level | Patients | Required scanners | Production gate |
|---|---|--:|--:|---|
| F-18 | LOW / BASE / HIGH | 8 / 32 / 64 | 1 / 2 / 4 | PRODUCTION_SUFFICIENT |
| C-11 | LOW / BASE / HIGH | 2 / 6 / 12 | 1 / 1 / 1 | per source calibration |
| N-13 | LOW / BASE / HIGH | 2 / 6 / 12 | 1 / 1 / 1 | per source calibration |
| O-15 | LOW / BASE / HIGH | 2 / 6 / 12 | 1 / 1 / 1 | PRODUCTION_NOT_CALIBRATED |
| Ga-68 | LOW / BASE / HIGH | 3 / 10 / 20 | 1 / 1 / 2 | per source calibration |

Scanner requirement scales with F-18 volume; the four-architecture cost ranking is stable across demand.

## TABLE 20 — Production-Source Sensitivity Matrix

| Radionuclide | Candidate sources (catalog-declared) |
|---|---|
| C-11 | IBA_CYCLONE_KIUBE, GE_PETTRACE_800, SIEMENS_CTI_ECLIPSE_HP, ACSI_TR_19 |
| N-13 | IBA_CYCLONE_KIUBE, GE_PETTRACE_800, SIEMENS_CTI_RDS_111, ACSI_TR_19 |
| O-15 | IBA_CYCLONE_KIUBE, GE_PETTRACE_800, SIEMENS_CTI_ECLIPSE_HP, ACSI_TR_19 |
| Ga-68 | SUMITOMO_CYPRIS_MP_30 (cyclotron) vs ECKERT_ZIEGLER_GALLIAPHARM (generator) |

Support is never converted to calibration; output is never borrowed between models; F-18 capacity never validates another radionuclide. Where a source declares support without a calibrated record, the gate is NOT_CALIBRATED (real identity, never fabricated capacity).

## TABLE 21 — Activity-Retention Comparison (summary)

| Radionuclide | Δ transport (MRT−Manual) | Δ retained | Interpretation |
|---|--:|--:|---|
| F-18 | −1.936 min | +0.0096 | marginal |
| C-11 | −1.936 min | +0.0181 | modest |
| N-13 | −1.936 min | +0.0096 | modest |
| O-15 | −1.936 min | +1.69e-6 (≈2×) | large proportional, tiny absolute |
| Ga-68 | −1.936 min | +0.0134 | modest |

## TABLE 22 — Production Requirement / Capacity Comparison

| Radionuclide | Req. upstream MBq (Manual) | Req. upstream MBq (MRT) | Reduction |
|---|--:|--:|--:|
| F-18 | 473.0 | 467.3 | 1.2% |
| C-11 | 2,095.4 | 1,961.4 | 6.4% |
| N-13 | 11,066.6 | 9,672.9 | 12.6% |
| O-15 | 612,042,408 | 317,016,415 | 48.2% |

MRT reduces the upstream production requirement most for the shortest half-lives — a genuine physics benefit — but the absolute O-15 requirement remains physically implausible regardless of transport mode.

## TABLE 23 — Clinical Resource Utilization

| Metric | Value |
|---|---|
| Scanner requirement (F-18 BASE, 32 pt) | 2 |
| Scanner requirement (F-18 HIGH, 64 pt) | 4 |
| Clinical bottleneck | scanner / clinical-resource capacity (never attributed to transport) |
| Note | four-architecture nuclear basis is the shared validated benchmark population |

## TABLE 24 — Transport Resource / Fleet Requirements

| Architecture | Transport resource | Linen handling |
|---|---|---|
| Manual | porter FTE (workload-derived) | Manual |
| Automated Conventional | AGV / PTS (existing authorities, unchanged) | Manual/AGV |
| MRT (Dominant) | MRT carriers (workload/concurrency-derived) | **Manual fallback** (linen 13.5 kg > 5 kg governor) |
| Hybrid | MRT carriers + Manual fallback | **Manual fallback** |

Bulk linen is excluded from MRT by the 5 kg gross-moving-mass governor and routed to Manual in both MRT and Hybrid — confirmed through the real mission-assignment path (0 MRT missions / Manual fallback).

## TABLE 25 — Complete Part 3E.1 Result Matrix (pointer)

Full matrix (every experiment × architecture × observation) is exported to
`corrected_mrt_experiment_result_matrix.json`. Experiments: baseline (EXP0),
F-18/C-11/N-13/O-15 (EXP1–4), short-half-life comparison (EXP5), distance sweep
(EXP6), MRT speed (EXP7), production source (EXP8), Ga-68 dual pathway (EXP9A/B),
demand (EXP10), mixed PET (EXP11), mixed PET+SPECT (EXP12), crossover (EXP13),
plus the Part 3E.2 envelope. Key decision tables appear inline above and below.

## TABLE 26 — Architecture Crossover Points

| Envelope | Radionuclide | Preferred below | Preferred above | Crossover state |
|---|---|---|---|---|
| Distance 0.5×–3.0× | F-18 / C-11 / N-13 / O-15 | MANUAL | MANUAL | NO_CROSSOVER_WITHIN_DEFENSIBLE_ENVELOPE |
| MRT speed SLOW→VERY_FAST | (all) | MANUAL | MANUAL | mrt_speed_crossover_found = False |
| Demand LOW→HIGH | (all) | MANUAL | MANUAL | stable ranking |
| Production source | (all) | MANUAL | MANUAL | stable ranking |

**NO_MRT_CROSSOVER_OBSERVED.** Across every tested condition the cost-only ranking was stable: MANUAL < AUTOMATED < MRT_DOMINANT < HYBRID. MRT's measured advantage is in retained-activity physics, not derived lifecycle cost at this basis.

## TABLE 27 — Architecture Preference by Radionuclide

| Radionuclide | Preferred | Note |
|---|---|---|
| F-18 / C-11 / N-13 / O-15 / Ga-68 / Tc-99m | MANUAL_CONVENTIONAL | radionuclide identity does not change benchmark-basis economics; it changes only the decay/production observations |

## TABLE 28 — Architecture Preference by Distance

| Distance | Preferred |
|---|---|
| 0.5× / 1.0× / 1.5× / 2.0× / 3.0× | MANUAL_CONVENTIONAL (no crossover) |

## TABLE 29 — Architecture Preference by Demand

| Demand level | Preferred |
|---|---|
| LOW / BASELINE / HIGH | MANUAL_CONVENTIONAL |

## TABLE 30 — Architecture Preference by Production Condition

| Production case | Preferred |
|---|---|
| Cyclotron-calibrated / NOT_CALIBRATED / generator | MANUAL_CONVENTIONAL |

## TABLE 31 — Why Each Preferred Architecture Wins (decomposition)

| Driver | Contribution to Manual's preference |
|---|---|
| CapEx | Manual $125,000 vs MRT $4,871,000 / Hybrid $981,500 — Manual lowest |
| Known-OPEX lifecycle spread | KNOWN_OPEX_DOMINANT over the full bouquet spread (qualified — see Table 39) |
| Decisive pairwise margin (Manual vs Automated) | CapEx-dominant (ΔCapEx $1.8M > AF·ΔknownOPEX $0.81M) |
| Radioactive decay | favors MRT physically, but is NOT a ranking input and does not overturn cost |
| Production requirement | MRT lowers it, but the reduction does not enter the cost-only objective |
| Clinical / transport capacity | not binding differently across architectures at this basis |

Manual wins on cost, not because competitors were penalized. MRT's physics advantages are real but do not translate into a lower modeled lifecycle cost at the benchmark basis.

## TABLE 32 — Corrected MRT vs Superseded Pre-Canonical MRT

| Metric | SUPERSEDED_PRE_CANONICAL_MRT | CURRENT_CANONICAL_MRT_RESULT | Δ | % | Cause |
|---|--:|--:|--:|--:|---|
| MRT arch-specific CapEx | $11,480,000 | $4,871,000 | −$6,609,000 | −57.6% | carrier $10k→$2k, guideway $5k→$2.5k/m, $6M flat base removed |
| MRT lifecycle cost | $45,522,122 | $43,259,463 | −$2,262,659 | −5.0% | lower CapEx + canonical energy/maintenance |
| MRT known annual OPEX (reported) | $5,073,280 | $5,721,013 | +$647,733 | — | reported known-subtotal column differs; total OPEX remains NOT_CALIBRATED (see caveat) |
| MRT transport time | (heavy 3 m/s straight) | 1.972 min (10 m/s straight) | faster | — | canonical straight speed |
| MRT preferred? | NO (rank 3) | NO (rank 3) | unchanged | — | still not cost-competitive at this basis |

**Caveat:** the superseded and current "known annual OPEX" columns are reported values (known subtotal only; total OPEX is NOT_CALIBRATED in both). The difference is not attributed to any physics change.

## TABLE 33 — Corrected Hybrid vs Superseded Pre-Canonical Hybrid

| Metric | SUPERSEDED_PRE_CANONICAL_MRT | CURRENT_CANONICAL_MRT_RESULT | Δ | % | Cause |
|---|--:|--:|--:|--:|---|
| Hybrid arch-specific CapEx | $7,106,000 | $981,500 | −$6,124,500 | −86.2% | canonical compact hardware basis |
| Hybrid lifecycle cost | $52,786,154 | $47,365,414 | −$5,420,740 | −10.3% | canonical hardware + maintenance |
| Hybrid preferred? | NO (rank 4) | NO (rank 4) | unchanged | — | |

## TABLE 34 — Part 3E.2 Decision Envelope

| Field | Value |
|---|---|
| Principal baseline decision driver | KNOWN_OPEX_DOMINANT (full-bouquet spread; qualified) |
| Annuity factor | 6.710081 |
| MANUAL decision region | YES |
| AUTOMATED decision region | NO |
| MRT_DOMINANT decision region | NO (NO_MRT_DOMINANT_DECISION_REGION_OBSERVED) |
| HYBRID decision region | NO (NO_HYBRID_DECISION_REGION_OBSERVED) |
| MRT speed crossover found | NO |

## TABLE 35 — Distance Crossover Boundaries

| Radionuclide | Envelope | Boundary |
|---|---|---|
| F-18 / C-11 / N-13 / O-15 | 0.5×–3.0× route | NO_CROSSOVER_WITHIN_DEFENSIBLE_ENVELOPE (preferred = MANUAL throughout) |

## TABLE 36 — Demand Crossover Boundaries

| Envelope | Boundary |
|---|---|
| LOW → HIGH patient volume | No architecture-preference crossover (MANUAL throughout) |

## TABLE 37 — Radionuclide-Dependent Decision Boundaries

| Boundary | Result |
|---|---|
| Preference vs radionuclide | Invariant (MANUAL) at the benchmark basis; radionuclide changes decay/production observations only |

## TABLE 38 — Production-Dependent Decision Boundaries

| Boundary | Result |
|---|---|
| Preference vs production source / calibration | Invariant (MANUAL); NOT_CALIBRATED gates never fabricated into feasibility |

## TABLE 39 — Uncertainty / Calibration-Sensitive Regions

| Region | Classification | Responsible calibration gap |
|---|---|---|
| Baseline four-architecture ranking | ROBUST on KNOWN costs | total OPEX NOT_CALIBRATED (both MRT standby/controls/cooling and full service/procurement) |
| MRT/Hybrid economic competitiveness | CALIBRATION_SENSITIVE | MRT standby/controls/cooling electricity; full MRT/AGV/PTS service OPEX |
| O-15 clinical feasibility | NOT_DECIDABLE (production) | O-15 production capacity NOT_CALIBRATED |
| "MRT total OPEX" | CALIBRATION_SENSITIVE | only MRT motion electricity is canonically calculated; standby/controls/cooling remain NOT_CALIBRATED — MRT total OPEX is NOT fully calibrated |

## TABLE 40 — No-Decision Regions

| Region | Status |
|---|---|
| MRT_DOMINANT preference | NO_MRT_DOMINANT_DECISION_REGION_OBSERVED |
| HYBRID preference | NO_HYBRID_DECISION_REGION_OBSERVED |
| O-15 clinical practicality | NOT_DECIDABLE (retained fraction ≈ 0 over benchmark route; production NOT_CALIBRATED) |

## TABLE 41 — Remaining Calibration Gaps

| Gap | Status |
|---|---|
| MRT network standby power | NOT_CALIBRATED |
| MRT controls power | NOT_CALIBRATED |
| MRT guideway cooling power | NOT_CALIBRATED |
| Full MRT / AGV / PTS service & procurement OPEX | NOT_CALIBRATED |
| O-15 (and several) production capacity | NOT_CALIBRATED |
| Curve / transition / station / braking segment speeds | NOT_CALIBRATED |
| Revenue-per-scan / IRR objective | NOT_CONFIGURED at this controlled benchmark |

## TABLE 42 — Physics Preservation

| Field | Value |
|---|---|
| DECAY_PHYSICS_CHANGED | NO |
| CYCLOTRON_PRODUCTION_PHYSICS_CHANGED | NO |
| GENERATOR_PHYSICS_CHANGED | NO |
| SCANNER_TIMING_CHANGED | NO |
| TRANSPORT_PHYSICS_CHANGED_DURING_EXPERIMENT | NO |
| ECONOMIC_FORMULAS_CHANGED_DURING_EXPERIMENT | NO |
| MANUAL_AUTHORITY_CHANGED | NO |
| AUTOMATED_CONVENTIONAL_AUTHORITY_CHANGED | NO |
| MRT_CANONICAL_CONFIGURATION_CHANGED_DURING_EXPERIMENT | NO |

No tracked source file was modified during the rerun (only the result matrix + this report were created).

## TABLE 43 — Experiment Regression Results

| Suite group | Count |
|---|--:|
| part3e + part3e2 + part3d + migration + canonical config | 351 passed |
| part3e experiment campaign + four-architecture | 224 passed (+1 skipped) |

## TABLE 44 — Superseded-Result Closure

| Prior report | Status |
|---|---|
| `RADIONUCLIDE_AWARE_ARCHITECTURE_AUTHORITY_PART_3E.md` | SUPERSEDED_PRE_CANONICAL_MRT (preserved as historical evidence, not deleted) |
| `PART_3E_1_RADIONUCLIDE_EXPERIMENT_CAMPAIGN_REPORT.md` | SUPERSEDED_PRE_CANONICAL_MRT (preserved) |
| `PART_3E_2_DECISION_ENVELOPE_AND_CROSSOVER_REPORT.md` | SUPERSEDED_PRE_CANONICAL_MRT (preserved) |

The corrected rerun in this report is the CURRENT_CANONICAL_MRT_RESULT. Prior reports are not overwritten.

## TABLE 45 — Experiment-Rerun Flag Closure

| Flag | Value |
|---|---|
| PART3E_RERUN_REQUIRED | NO (rerun physically completed) |
| PART3E_1_RERUN_REQUIRED | NO (rerun physically completed) |
| PART3E_2_RERUN_REQUIRED | NO (rerun physically completed) |
| SHORT_HALF_LIFE_EXPERIMENT_RERUN_REQUIRED | NO (rerun physically completed) |

---

## SCIENTIFIC INTERPRETATION (Sec 35)

1. **Does MRT materially improve radionuclide retention?** Yes, physically, and the improvement scales inversely with half-life: F-18 +1.2%, C-11 +6.8%, N-13 +14.4%, O-15 ~2× (relative). The absolute gain is small for long half-lives.
2. **For which radionuclides is the retention improvement meaningful?** Operationally most meaningful for short-lived C-11/N-13; for O-15 the relative gain is large but the absolute retained fraction stays ~0 over the benchmark route (not clinically rescued). For F-18 the gain is marginal.
3. **At what distances does MRT begin to matter?** The MRT retention advantage widens with distance across 0.5×–3.0×, but no architecture-preference crossover occurs within that defensible envelope.
4. **At what patient volumes does MRT become attractive?** None tested (LOW/BASE/HIGH) reorder the cost ranking; scanner capacity scales with volume but does not favor MRT.
5. **Does MRT reduce upstream production requirements enough to matter?** It reduces them (up to ~48% for O-15), a real benefit, but this does not enter the cost-only decision objective and does not overturn the ranking.
6. **Does MRT increase throughput, or are scanners/clinical resources binding?** Clinical/scanner capacity is the binding operational constraint; transport is not the throughput bottleneck at this basis.
7. **When does Manual remain preferred?** In every tested region — it is the lowest-cost feasible architecture throughout.
8. **When does Automated Conventional remain preferred?** Never rank 1 here; it is consistently second on lifecycle cost.
9. **When does MRT become preferred?** Not within the tested domain (rank 3 everywhere).
10. **When does Hybrid become preferred?** Not within the tested domain (rank 4 everywhere).
11. **Are there regions where the result cannot be decided?** Yes — MRT/Hybrid economic competitiveness is CALIBRATION_SENSITIVE (MRT standby/controls/cooling and full service OPEX are NOT_CALIBRATED), and O-15 clinical practicality is NOT_DECIDABLE (production NOT_CALIBRATED). These are honestly carried, not resolved by assumption.

## NO UNIVERSAL WINNER (Sec 36)

This experiment does not conclude "MRT is best." At the tested controlled benchmark, **MANUAL_CONVENTIONAL is the preferred architecture in every region** on known lifecycle cost, and no crossover to Automated, MRT, or Hybrid was observed across radionuclide, distance, demand, speed, or production-source sweeps. MRT's advantages are physical (shorter transit, higher short-half-life retention, lower upstream production requirement) and are real but did not translate into a lower modeled lifecycle cost. The corrected canonical MRT is far cheaper than the superseded heavy MRT (CapEx −57.6% MRT / −86.2% Hybrid) yet still not cost-competitive with Manual at this basis.

## TRANSPORT-MODE FAIRNESS / MATURITY (Sec 38)

| Mode | Model maturity |
|---|---|
| MANUAL | Established wage/FTE/shift authority; workload-derived |
| AUTOMATED_CONVENTIONAL | Established AGV/PTS maintenance+energy+labor authority (flat figures); distance-sensitive coefficients optional/additive |
| MRT | Most detailed engineering authority (canonical config + motion energy E=P·t); standby/controls/cooling still NOT_CALIBRATED |
| PTS | Flat lumped figures; distance-sensitive coefficient optional |
| AGV/AMR | Flat lumped figures; distance-sensitive coefficient optional |

These conclusions are provisional with respect to transport modes whose economic authorities are less mature than MRT. This experiment answers "how do the CURRENT modeled architectures compare?" — it does NOT establish universal commercial superiority of any transport technology.

## FINAL EXPERIMENT REPORT (Sec 40)

```
CORRECTED_MRT_SCIENTIFIC_EXPERIMENT_RERUN = COMPLETE
STARTING_HEAD = 305297c
MRT_CONFIGURATION_FROZEN = YES
EXPERIMENT_PHYSICS_FROZEN = YES
PART3E_RERUN_COMPLETED = YES
PART3E_1_RERUN_COMPLETED = YES
SHORT_HALF_LIFE_RERUN_COMPLETED = YES
PART3E_2_RERUN_COMPLETED = YES
RADIONUCLIDES_TESTED = F-18, C-11, N-13, O-15, Ga-68, Tc-99m
DISTANCES_TESTED = 0.5x, 1.0x, 1.5x, 2.0x, 3.0x (benchmark worst-case route)
DEMAND_LEVELS_TESTED = LOW / BASELINE / HIGH (per radionuclide)
PRODUCTION_CASES_TESTED = C-11/N-13/O-15 multi-cyclotron + Ga-68 cyclotron vs generator
BASELINE_PREFERRED_ARCHITECTURE = MANUAL_CONVENTIONAL
F18_PREFERRED_REGIONS = MANUAL (all)
C11_PREFERRED_REGIONS = MANUAL (all)
N13_PREFERRED_REGIONS = MANUAL (all)
O15_PREFERRED_REGIONS = MANUAL (all); clinical practicality NOT_DECIDABLE
GA68_PREFERRED_REGIONS = MANUAL (all)
TC99M_PREFERRED_REGIONS = MANUAL (all)
MANUAL_PREFERENCE_REGIONS = ALL tested
AUTOMATED_CONVENTIONAL_PREFERENCE_REGIONS = NONE (rank 2 throughout)
MRT_PREFERENCE_REGIONS = NONE
HYBRID_PREFERENCE_REGIONS = NONE
NO_DECISION_REGIONS = MRT/Hybrid economic competitiveness (calibration-sensitive); O-15 clinical practicality
MRT_RETENTION_ADVANTAGE_OBSERVED = YES (scales with shorter half-life)
MRT_PRODUCTION_REQUIREMENT_ADVANTAGE_OBSERVED = YES (up to ~48% for O-15)
MRT_THROUGHPUT_ADVANTAGE_OBSERVED = NO (clinical/scanner capacity binding, not transport)
MRT_ECONOMIC_ADVANTAGE_OBSERVED = NO (rank 3 on lifecycle cost)
HYBRID_ADVANTAGE_OBSERVED = NO (rank 4)
DECAY_PHYSICS_CHANGED = NO
CYCLOTRON_PRODUCTION_PHYSICS_CHANGED = NO
GENERATOR_PHYSICS_CHANGED = NO
SCANNER_TIMING_CHANGED = NO
TRANSPORT_PHYSICS_CHANGED_DURING_EXPERIMENT = NO
ECONOMIC_FORMULAS_CHANGED_DURING_EXPERIMENT = NO
MANUAL_AUTHORITY_CHANGED = NO
AUTOMATED_CONVENTIONAL_AUTHORITY_CHANGED = NO
MRT_CANONICAL_CONFIGURATION_CHANGED_DURING_EXPERIMENT = NO
PART3E_RERUN_REQUIRED = NO
PART3E_1_RERUN_REQUIRED = NO
PART3E_2_RERUN_REQUIRED = NO
SHORT_HALF_LIFE_EXPERIMENT_RERUN_REQUIRED = NO
REPORT_FILE = CORRECTED_MRT_SCIENTIFIC_EXPERIMENT_RERUN_REPORT.md
RESULT_MATRIX_FILE = corrected_mrt_experiment_result_matrix.json
READY_FOR_TRANSPORT_MODE_PARITY_BUILD = YES (Manual/PTS/AGV-AMR economic-authority parity is the natural next scope; not started)
READY_FOR_REAL_LIFE_SCENARIO_CAMPAIGN = YES (not started)
```

STOP — no stage/commit/push performed. Awaiting review.
