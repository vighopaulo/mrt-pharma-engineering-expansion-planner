# Part 3E.2 — Decision Envelope, Architecture Crossover & Decision-Critical Calibration Report

**Authority module:** `part3e2_decision_envelope.py` (READ-ONLY analytical orchestration layer)
**Focused test file:** `test_part3e2_decision_envelope.py`
**Starting HEAD:** `93bf687` · branch `main` · working tree clean · divergence 0/0

Part 3E.2 answers a single question:

> **What must physically or economically change before the preferred architecture changes?**

It CONSUMES the committed Part 3E.1 experiment campaign, the Part 3E scenario/bouquet orchestration, the Part 3D four-architecture feasibility/economics, and the canonical decay / transport / production / Equipment-OPEX authorities. It introduces **no** new physics, economic, production, scanner, or scheduling engine; it applies **no** MRT/Hybrid/Conventional/short-half-life bonus; it never zero-fills a NOT_CALIBRATED cost, never fabricates a crossover or a probability distribution, and never fabricates an appointment date. `DECISION_ENVELOPE_INPUT_TRACE = COMPLETE`.

The single arithmetic identity Part 3E.2 relies on is the canonical engine's own lifecycle relation, verified exactly against all four derived `ArchitectureResult`s:

```
lifecycle_cost = new_study_capex + AF · annual_opex        AF = Σ_{y=1..10} 1/(1.08)^y = 6.710081
```

This is the SAME discounted operating-horizon factor `apply_study_scope` applies (8 % discount rate, 10-year horizon); it is reused for read-only break-even threshold math, never as a second economic engine.

---

## TABLE 1 — Part 3E.2 Analysis Definition

| Item | Value |
|---|---|
| Central question | What must physically/economically change before the preferred architecture changes? |
| Scope | READ-ONLY analytical orchestration; no engine built |
| Consumed authorities | Part 3E.1 campaign, Part 3E orchestration, Part 3D economics/feasibility, decay, transport, production, Equipment OPEX |
| Architecture neutrality | No MRT/Hybrid/Conventional/short-half-life bonus |
| Ranking / Pareto | Canonical `wo4a.rank_cost_only` / `wo4a.compute_pareto_front` |
| Economics | KNOWN subtotal only; total OPEX NOT_CALIBRATED |
| Break-even | Read-only threshold over the canonical lifecycle identity |
| Joint scheduler | NOT built (`TRUE_JOINT_MULTI_RADIONUCLIDE_SCHEDULING = NO`) |
| Annuity factor (AF) | 6.710081 (8 %/10 yr) |
| `PHYSICALLY_RECOGNIZED_RADIONUCLIDE_COUNT` (canonical universe) | **15** — consumed from the Clinical Radionuclide Completeness authority (`discover_physically_recognized_radionuclides()`): At-211, C-11, Cu-64, F-18, Ga-68, Ge-68, I-123, I-124, In-111, Mo-99, N-13, O-15, Tc-99m, Tl-201, Zr-89 |
| `PART3E2_RADIONUCLIDES_ANALYZED_COUNT` (experimental subset) | **6** — F-18, C-11, N-13, O-15, Ga-68, Tc-99m |
| Universe vs subset | The analyzed subset is a strict SUBSET of the physical universe. The campaign is **not** expanded to make the analyzed count equal the universe; the two counts are reported separately. A prior draft reported "6 tested" as if it were the physical universe — that conflation is corrected here. |

## TABLE 2 — Part 3E.1 Result Baseline (F-18 + Tc-99m, benchmark)

| Architecture | New study CapEx ($) | Known annual OPEX ($) | True-total annual OPEX ($) | Known lifecycle cost ($) | Cost-only rank | Pareto | Physical status |
|---|--:|--:|--:|--:|:--:|:--:|---|
| MANUAL_CONVENTIONAL | 125,000 | 1,750,320 | 6,771,800 | 11,869,790 | 1 | ✔ | FEASIBLE_WITH_UNCALIBRATED_PRODUCTION_CAPACITY |
| AUTOMATED_CONVENTIONAL | 1,925,000 | 1,870,772 | 6,892,252 | 14,478,032 | 2 | — | FEASIBLE_WITH_UNCALIBRATED_PRODUCTION_CAPACITY |
| MRT_DOMINANT | 11,480,000 | 5,073,280 | 5,073,280 | 45,522,122 | 3 | — | FEASIBLE_WITH_UNCALIBRATED_PRODUCTION_CAPACITY |
| HYBRID_MRT | 7,106,000 | 6,807,690 | 6,807,690 | 52,786,154 | 4 | — | FEASIBLE_WITH_UNCALIBRATED_PRODUCTION_CAPACITY |

Ranking: MANUAL < AUTOMATED < MRT_DOMINANT < HYBRID. Only MANUAL is on the Pareto front.

## TABLE 3 — Architecture Cost Decomposition (Δ vs MANUAL_CONVENTIONAL)

| Architecture | ΔNew study CapEx ($) | ΔKnown annual OPEX ($) | ΔKnown lifecycle cost ($) | ΔTotal-comparable project CapEx ($) | Status |
|---|--:|--:|--:|--:|---|
| MANUAL_CONVENTIONAL | 0 | 0 | 0 | 0 | KNOWN_COST_DELTA_ONLY_TOTAL_OPEX_NOT_CALIBRATED |
| AUTOMATED_CONVENTIONAL | 1,800,000 | 120,452 | 2,608,243 | 1,800,000 | KNOWN_COST_DELTA_ONLY_TOTAL_OPEX_NOT_CALIBRATED |
| MRT_DOMINANT | 11,355,000 | 3,322,960 | 33,652,332 | 11,355,000 | KNOWN_COST_DELTA_ONLY_TOTAL_OPEX_NOT_CALIBRATED |
| HYBRID_MRT | 6,981,000 | 5,057,370 | 40,916,364 | 6,981,000 | KNOWN_COST_DELTA_ONLY_TOTAL_OPEX_NOT_CALIBRATED |

There is **no** ΔTotal-OPEX column, because total OPEX is NOT_CALIBRATED.

## TABLE 4 — Architecture Known-OPEX Decomposition (Δ vs MANUAL)

| Architecture | ΔKnown annual OPEX ($) | ΔTrue-total annual OPEX ($) | Lifecycle-equivalent of ΔKnown OPEX (× AF) ($) | Note |
|---|--:|--:|--:|---|
| AUTOMATED_CONVENTIONAL | 120,452 | 120,452 | 808,243 | small recurring delta |
| MRT_DOMINANT | 3,322,960 | −1,698,520 | 22,297,332 | true-total OPEX LOWER than Manual, but known subtotal higher |
| HYBRID_MRT | 5,057,370 | 35,890 | 33,935,364 | largest known-OPEX delta |

The MRT_DOMINANT true-total annual OPEX is **lower** than Manual (−$1.70 M), yet its known annual OPEX subtotal is higher; the two are reported distinctly and never conflated.

## TABLE 3A — Known-Lifecycle Decomposition per Pair (audit of KNOWN_OPEX_DOMINANT)

Canonical identity: `ΔLifecycleKnown = ΔCapEx + AF · ΔKnownAnnualOPEX`, with **AF = 6.710081** (8 %/10-yr operating horizon). Each row reconciles exactly.

| Pair (vs MANUAL) | ΔCapEx ($) | ΔKnown annual OPEX ($/yr) | Discount / annuity factor | Discounted known-OPEX contribution AF·ΔOPEX ($) | Known lifecycle gap ($) | Dominant discounted term |
|---|--:|--:|--:|--:|--:|---|
| MANUAL vs AUTOMATED_CONVENTIONAL | 1,800,000 | 120,452 | 6.710081 | 808,243 | 2,608,243 | **CapEx** (1.80 M > 0.81 M) |
| MANUAL vs HYBRID_MRT | 6,981,000 | 5,057,370 | 6.710081 | 33,935,364 | 40,916,364 | Known-OPEX (33.94 M > 6.98 M) |
| MANUAL vs MRT_DOMINANT | 11,355,000 | 3,322,960 | 6.710081 | 22,297,332 | 33,652,332 | Known-OPEX (22.30 M > 11.36 M) |

**Reading of KNOWN_OPEX_DOMINANT (reconciled):** the label means the known-OPEX lifecycle contribution dominates the currently-modeled **known** lifecycle-cost difference **across the bouquet** (and for the two far-from-margin MRT-family challengers). It does **not** mean:
- that true total OPEX is known — total OPEX remains **NOT_CALIBRATED**; nor
- that OPEX governs the **decisive** decision margin. At the binding preferred→second-best pair (**Manual vs Automated**) the dominant discounted term is **CapEx** ($1.80 M > $0.81 M). The decision boundary is CapEx-led even though the full-bouquet spread is known-OPEX-led.

## TABLE 5 — Architecture Physical-Effect Decomposition (MRT vs MANUAL, benchmark worst-case route 95 m / 32 m vertical / 2 transitions)

| Radionuclide | Half-life (min) | Manual transport (min) | MRT transport (min) | ΔTransport (min) | Manual retained | MRT retained | ΔRetained | Manual req. upstream (MBq) | MRT req. upstream (MBq) | ΔReq. upstream (MBq) |
|---|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|
| F-18 | 109.8 | 3.91 | 1.97 | −1.94 | 0.7822 | 0.7918 | +0.0096 | 473.0 | 467.3 | −5.7 |
| C-11 | 20.3 | 3.91 | 1.97 | −1.94 | 0.2649 | 0.2830 | +0.0181 | 2,095.4 | 1,961.4 | −134.0 |
| N-13 | 9.97 | 3.91 | 1.97 | −1.94 | 0.0669 | 0.0765 | +0.0096 | 11,066.6 | 9,672.9 | −1,393.7 |
| O-15 | 2.04 | 3.91 | 1.97 | −1.94 | ~0.0000 | ~0.0000 | ~0.0000 | 6.12e8 | 3.17e8 | −2.95e8 |
| Ga-68 | 67.7 | 3.91 | 1.97 | −1.94 | 0.6714 | 0.6849 | +0.0134 | 275.5 | 270.1 | −5.4 |

MRT's shorter route time improves retained activity for every radionuclide (a physical benefit), but this is an OBSERVATION — it does not enter the ranking.

## TABLE 6 — F-18 Decision Drivers

| Field | Value |
|---|---|
| Experiment | EXP1 (F18_CONTROL) |
| Preferred architecture | MANUAL_CONVENTIONAL |
| Second-best | AUTOMATED_CONVENTIONAL |
| CapEx spread ($) | 11,355,000 |
| Known-OPEX spread ($) | 5,057,370 |
| Lifecycle-equiv known-OPEX spread ($, × AF) | 33,935,364 |
| Principal driver | KNOWN_OPEX_DOMINANT (QUALIFIED — see note) |
| Evidence | lifecycle-equivalent known-OPEX **spread** ($33.9 M, across all four architectures) exceeds the CapEx spread ($11.4 M); known OPEX governs the full-bouquet **known** lifecycle spread |
| Qualification | `KNOWN_OPEX_DOMINANT` is a statement about the currently-modeled **known** lifecycle **spread** across the four architectures. It does **not** mean total OPEX is known (total OPEX is NOT_CALIBRATED), and it does **not** govern the **decisive** preferred→second-best margin. At the binding Manual vs Automated margin the dominant discounted term is actually **CapEx** (ΔCapEx $1,800,000 vs AF·ΔknownOPEX $808,243). See TABLE 3A. |

## TABLE 7 — C-11 Decision Drivers

| Field | Value |
|---|---|
| Experiment | EXP2 (C11_CONTROL) |
| Preferred architecture | MANUAL_CONVENTIONAL |
| Principal driver | KNOWN_OPEX_DOMINANT |
| C-11 physical note | shortest-but-one half-life (20.3 min); high required-upstream activity; does not alter the benchmark-basis economics |

## TABLE 8 — N-13 Decision Drivers

| Field | Value |
|---|---|
| Experiment | EXP3 (N13_CONTROL) |
| Preferred architecture | MANUAL_CONVENTIONAL |
| Principal driver | KNOWN_OPEX_DOMINANT |
| N-13 physical note | half-life 9.97 min; required-upstream activity ~11,067 MBq (manual); severe decay sensitivity OBSERVED, not rewarded |

## TABLE 9 — O-15 Decision Drivers

| Field | Value |
|---|---|
| Experiment | EXP4 (O15_CONTROL) |
| Preferred architecture | MANUAL_CONVENTIONAL |
| Principal driver | KNOWN_OPEX_DOMINANT |
| O-15 physical note | half-life 2.04 min; retained fraction ≈ 0 over the benchmark route; required-upstream activity is astronomically large (feasibility observation, never a forced win) |

## TABLE 10 — Ga-68 Cyclotron Decision Drivers

| Field | Value |
|---|---|
| Experiment | EXP9A (GA68_CYCLOTRON, SUMITOMO_CYPRIS_MP_30) |
| Preferred architecture | MANUAL_CONVENTIONAL |
| Principal driver | KNOWN_OPEX_DOMINANT |
| Production | CYCLOTRON, SUMITOMO CYPRIS MP-30, declares Ga-68 but NOT_CALIBRATED (real identity, no fabricated EOB) |

## TABLE 11 — Ga-68 Generator Decision Drivers

| Field | Value |
|---|---|
| Experiment | EXP9B (GA68_GENERATOR, ECKERT_ZIEGLER_GALLIAPHARM) |
| Preferred architecture | MANUAL_CONVENTIONAL |
| Principal driver | KNOWN_OPEX_DOMINANT |
| Production | GENERATOR, Ge-68/Ga-68 daughter, procurement/service economics NOT_CALIBRATED (never zero) |

## TABLE 12 — Distance Decision Envelope (transport time + retained activity through canonical authorities; ranking = benchmark basis)

| Radionuclide | Mult. | Distance (m) | Manual t (min) | MRT t (min) | Manual retained | MRT retained | Manual req. upstream (MBq) | MRT req. upstream (MBq) | Preferred |
|---|--:|--:|--:|--:|--:|--:|--:|--:|---|
| F-18 | 0.5× | 47.5 | 3.20 | 1.62 | 0.7857 | 0.7936 | 471 | 466 | MANUAL |
| F-18 | 1.0× | 95.0 | 3.91 | 1.97 | 0.7822 | 0.7918 | 473 | 467 | MANUAL |
| F-18 | 1.5× | 142.5 | 4.61 | 2.33 | 0.7787 | 0.7901 | 475 | 468 | MANUAL |
| F-18 | 2.0× | 190.0 | 5.32 | 2.68 | 0.7753 | 0.7883 | 477 | 469 | MANUAL |
| F-18 | 3.0× | 285.0 | 6.72 | 3.38 | 0.7684 | 0.7848 | 481 | 471 | MANUAL |
| C-11 | 0.5× | 47.5 | 3.20 | 1.62 | 0.2713 | 0.2864 | 2,046 | 1,938 | MANUAL |
| C-11 | 1.0× | 95.0 | 3.91 | 1.97 | 0.2649 | 0.2830 | 2,095 | 1,961 | MANUAL |
| C-11 | 3.0× | 285.0 | 6.72 | 3.38 | 0.2406 | 0.2697 | 2,307 | 2,058 | MANUAL |
| N-13 | 1.0× | 95.0 | 3.91 | 1.97 | 0.0669 | 0.0765 | 11,067 | 9,673 | MANUAL |
| N-13 | 3.0× | 285.0 | 6.72 | 3.38 | 0.0550 | 0.0694 | 13,460 | 10,670 | MANUAL |
| O-15 | 1.0× | 95.0 | 3.91 | 1.97 | ~0 | ~0 | 6.12e8 | 3.17e8 | MANUAL |
| O-15 | 3.0× | 285.0 | 6.72 | 3.38 | ~0 | ~0 | 1.59e9 | 5.12e8 | MANUAL |

`DISTANCE_ENVELOPE_TESTED = 0.5×–3.0× of the benchmark worst-case route (5 controlled multipliers).`

## TABLE 13 — Patient-Volume Decision Envelope (explicit counts; analytical requirement vs validated schedule)

| Radionuclide | Level | Patients | Req. scanners | Production gate | Stream status | Detailed scheduling |
|---|---|--:|--:|---|---|---|
| F-18 | LOW | 8 | 1 | PRODUCTION_SUFFICIENT | RESOLVED_ADMISSIBLE | NOT_FULLY_VALIDATED |
| F-18 | BASELINE | 32 | 2 | PRODUCTION_SUFFICIENT | RESOLVED_ADMISSIBLE | VALIDATED_OPERATING_SCHEDULE |
| F-18 | HIGH | 64 | 4 | PRODUCTION_SUFFICIENT | RESOLVED_ADMISSIBLE | NOT_FULLY_VALIDATED |
| C-11 | LOW/BASE/HIGH | 2/6/12 | 1 | PRODUCTION_NOT_CALIBRATED | RESOLVED_WITH_UNCALIBRATED_PRODUCTION | BASELINE validated; LOW/HIGH NOT_FULLY_VALIDATED |
| N-13 | LOW/BASE/HIGH | 2/6/12 | 1 | PRODUCTION_NOT_CALIBRATED | RESOLVED_WITH_UNCALIBRATED_PRODUCTION | BASELINE validated; LOW/HIGH NOT_FULLY_VALIDATED |
| O-15 | LOW/BASE/HIGH | 2/6/12 | 1 | PRODUCTION_NOT_CALIBRATED | RESOLVED_WITH_UNCALIBRATED_PRODUCTION | BASELINE validated; LOW/HIGH NOT_FULLY_VALIDATED |
| Ga-68 | LOW/BASE/HIGH | 3/10/20 | 1 | PRODUCTION_NOT_CALIBRATED | RESOLVED_WITH_UNCALIBRATED_PRODUCTION | BASELINE validated; LOW/HIGH NOT_FULLY_VALIDATED |

`PATIENT_VOLUME_ENVELOPE_TESTED = explicit LOW/BASELINE/HIGH per radionuclide.` ANALYTICAL_REQUIREMENT is kept distinct from VALIDATED_OPERATING_SCHEDULE; demand beyond the canonical engine subset is never forced through the scheduler.

## TABLE 14 — MRT-Speed Decision Envelope (CONTROLLED_EXPERIMENTAL_ASSUMPTION speeds; ranking = benchmark basis)

| Radionuclide | Label | H speed (m/s) | V speed (m/s) | MRT transport (min) | MRT retained | Req. upstream (MBq) | Preferred |
|---|---|--:|--:|--:|--:|--:|---|
| F-18 | SLOW | 1.5 | 0.75 | 2.678 | 0.7883 | 469 | MANUAL |
| F-18 | BASELINE | 3.0 | 1.5 | 1.972 | 0.7918 | 467 | MANUAL |
| F-18 | FAST | 6.0 | 3.0 | 1.619 | 0.7936 | 466 | MANUAL |
| F-18 | VERY_FAST | 9.0 | 4.5 | 1.502 | 0.7942 | 466 | MANUAL |
| C-11 | SLOW→VERY_FAST | 1.5→9.0 | 0.75→4.5 | 2.678→1.502 | 0.2762→0.2875 | 2,009→1,930 | MANUAL |
| N-13 | SLOW→VERY_FAST | 1.5→9.0 | 0.75→4.5 | 2.678→1.502 | 0.0728→0.0790 | 10,159→9,362 | MANUAL |
| O-15 | SLOW→VERY_FAST | 1.5→9.0 | 0.75→4.5 | 2.678→1.502 | ~0 | 4.03e8→2.70e8 | MANUAL |

`MRT_SPEED_ENVELOPE_TESTED = SLOW / BASELINE / FAST / VERY_FAST (CONTROLLED).` `MRT_SPEED_CROSSOVER_FOUND = NO.` Speed changes physics (transport time, retained activity), not the benchmark-basis architecture ranking.

## TABLE 15 — Radionuclide / Half-Life Comparison (fixed benchmark route)

| Radionuclide | Half-life (min) | Manual retained | MRT retained | Manual req. upstream (MBq) | MRT req. upstream (MBq) | Preferred | Correlates with ranking? |
|---|--:|--:|--:|--:|--:|---|:--:|
| F-18 | 109.8 | 0.7822 | 0.7918 | 473.0 | 467.3 | MANUAL | No |
| C-11 | 20.3 | 0.2649 | 0.2830 | 2,095.4 | 1,961.4 | MANUAL | No |
| N-13 | 9.97 | 0.0669 | 0.0765 | 11,066.6 | 9,672.9 | MANUAL | No |
| O-15 | 2.04 | ~0.0000 | ~0.0000 | 6.12e8 | 3.17e8 | MANUAL | No |

Architecture outcome correlates with **economics** (CapEx + known OPEX), **not** with half-life. `SHORTER_HALF_LIFE_CAUSES_MRT_TO_WIN` is **NOT** supported by the tested ranking.

## TABLE 16 — Production-Source Decision Envelope (real catalog identity; support ≠ calibration; F-18 output never borrowed)

| Radionuclide | Source | Model | Manufacturer | Declares | Schedulable | Calibrated EOB record | Calibration status | Gate status |
|---|---|---|---|:--:|:--:|:--:|---|---|
| F-18 | CYCLOTRON | GE_PETTRACE_890 | GE HealthCare | ✔ | ✔ | ✔ | manufacturer_calibrated | PRODUCTION_SUFFICIENT |
| C-11 | CYCLOTRON | IBA_CYCLONE_KIUBE | IBA | ✔ | — | — | not_calibrated | PRODUCTION_NOT_CALIBRATED |
| C-11 | CYCLOTRON | GE_PETTRACE_800 | GE HealthCare | ✔ | ✔ | — | modeled | PRODUCTION_NOT_CALIBRATED |
| C-11 | CYCLOTRON | SIEMENS_CTI_ECLIPSE_HP | Siemens/CTI | ✔ | — | — | not_calibrated | PRODUCTION_NOT_CALIBRATED |
| N-13 | CYCLOTRON | IBA_CYCLONE_KIUBE | IBA | ✔ | — | — | not_calibrated | PRODUCTION_NOT_CALIBRATED |
| N-13 | CYCLOTRON | SIEMENS_CTI_RDS_111 | Siemens/CTI | ✔ | — | — | not_calibrated | PRODUCTION_NOT_CALIBRATED |
| N-13 | CYCLOTRON | ACSI_TR_19 | ACSI | ✔ | — | — | not_calibrated | PRODUCTION_NOT_CALIBRATED |
| O-15 | CYCLOTRON | IBA_CYCLONE_KIUBE | IBA | ✔ | — | — | not_calibrated | PRODUCTION_NOT_CALIBRATED |
| O-15 | CYCLOTRON | SIEMENS_CTI_ECLIPSE_HP | Siemens/CTI | ✔ | — | — | not_calibrated | PRODUCTION_NOT_CALIBRATED |
| O-15 | CYCLOTRON | ACSI_TR_19 | ACSI | ✔ | — | — | not_calibrated | PRODUCTION_NOT_CALIBRATED |
| Ga-68 | CYCLOTRON | SUMITOMO_CYPRIS_MP_30 | Sumitomo Heavy Industries | ✔ | — | — | not_calibrated | PRODUCTION_NOT_CALIBRATED |
| Ga-68 | GENERATOR | ECKERT_ZIEGLER_GALLIAPHARM | Eckert & Ziegler | ✔ | — | — | not_calibrated | PRODUCTION_NOT_CALIBRATED |

`PRODUCTION_SOURCES_TESTED = F-18 (calibrated) + 3 C-11 candidates + 3 N-13 + 3 O-15 + Ga-68 cyclotron + Ga-68 generator.` A calibrated F-18 record qualifies **only** F-18.

## TABLE 17 — Architecture Crossover Brackets

| Envelope | Radionuclide | Lower | Upper | Preferred below | Preferred above | State |
|---|---|---|---|---|---|---|
| DISTANCE | F-18 | 0.5× | 3.0× | MANUAL | MANUAL | NO_CROSSOVER_WITHIN_DEFENSIBLE_ENVELOPE |
| DISTANCE | C-11 | 0.5× | 3.0× | MANUAL | MANUAL | NO_CROSSOVER_WITHIN_DEFENSIBLE_ENVELOPE |
| DISTANCE | N-13 | 0.5× | 3.0× | MANUAL | MANUAL | NO_CROSSOVER_WITHIN_DEFENSIBLE_ENVELOPE |
| DISTANCE | O-15 | 0.5× | 3.0× | MANUAL | MANUAL | NO_CROSSOVER_WITHIN_DEFENSIBLE_ENVELOPE |
| MRT_SPEED | all | SLOW | VERY_FAST | MANUAL | MANUAL | NO_CROSSOVER_OBSERVED |

No crossover was fabricated. A crossover bracket requires an observed change in the preferred architecture between tested points; none occurred.

## TABLE 18 — Manual vs Automated Thresholds

| Field | Value |
|---|---|
| Reference (lower lifecycle) | MANUAL_CONVENTIONAL ($11,869,790) |
| Challenger | AUTOMATED_CONVENTIONAL ($14,478,032) |
| Known lifecycle gap ($) | 2,608,243 |
| Required CapEx reduction for break-even ($) | 2,608,243 |
| Required annual known-OPEX savings for break-even ($/yr) | 388,705 |
| Full-OPEX break-even | FULL_OPEX_BREAK_EVEN_NOT_CALCULABLE |

## TABLE 19 — Manual vs Hybrid Thresholds

| Field | Value |
|---|---|
| Reference | MANUAL_CONVENTIONAL ($11,869,790) |
| Challenger | HYBRID_MRT ($52,786,154) |
| Known lifecycle gap ($) | 40,916,364 |
| Required CapEx reduction for break-even ($) | 40,916,364 |
| Required annual known-OPEX savings for break-even ($/yr) | 6,097,745 |
| Full-OPEX break-even | FULL_OPEX_BREAK_EVEN_NOT_CALCULABLE |

## TABLE 20 — Manual vs MRT-Dominant Thresholds

| Field | Value |
|---|---|
| Reference | MANUAL_CONVENTIONAL ($11,869,790) |
| Challenger | MRT_DOMINANT ($45,522,122) |
| Known lifecycle gap ($) | 33,652,332 |
| Required CapEx reduction for break-even ($) | 33,652,332 |
| Required annual known-OPEX savings for break-even ($/yr) | 5,015,190 |
| Full-OPEX break-even | FULL_OPEX_BREAK_EVEN_NOT_CALCULABLE |

## TABLE 21 — Automated vs Hybrid Thresholds

| Field | Value |
|---|---|
| Reference | AUTOMATED_CONVENTIONAL ($14,478,032) |
| Challenger | HYBRID_MRT ($52,786,154) |
| Known lifecycle gap ($) | 38,308,122 |
| Required CapEx reduction for break-even ($) | 38,308,122 |
| Required annual known-OPEX savings for break-even ($/yr) | 5,709,040 |
| Full-OPEX break-even | FULL_OPEX_BREAK_EVEN_NOT_CALCULABLE |

## TABLE 22 — Automated vs MRT-Dominant Thresholds

| Field | Value |
|---|---|
| Reference | AUTOMATED_CONVENTIONAL ($14,478,032) |
| Challenger | MRT_DOMINANT ($45,522,122) |
| Known lifecycle gap ($) | 31,044,089 |
| Required CapEx reduction for break-even ($) | 31,044,089 |
| Required annual known-OPEX savings for break-even ($/yr) | 4,626,485 |
| Full-OPEX break-even | FULL_OPEX_BREAK_EVEN_NOT_CALCULABLE |

## TABLE 23 — Hybrid vs MRT-Dominant Thresholds

| Field | Value |
|---|---|
| Reference (lower lifecycle) | MRT_DOMINANT ($45,522,122) |
| Challenger | HYBRID_MRT ($52,786,154) |
| Known lifecycle gap ($) | 7,264,032 |
| Required CapEx reduction for break-even ($) | 7,264,032 |
| Required annual known-OPEX savings for break-even ($/yr) | 1,082,555 |
| Full-OPEX break-even | FULL_OPEX_BREAK_EVEN_NOT_CALCULABLE |

## TABLE 24 — CapEx Break-Even Thresholds (read-only)

| Challenger | Reference | Known lifecycle gap ($) | Max incremental CapEx the reference could absorb ($) | Basis |
|---|---|--:|--:|---|
| AUTOMATED | MANUAL | 2,608,243 | 2,608,243 | CANONICAL_LIFECYCLE_IDENTITY_KNOWN_OPEX_ONLY |
| MRT_DOMINANT | MANUAL | 33,652,332 | 33,652,332 | CANONICAL_LIFECYCLE_IDENTITY_KNOWN_OPEX_ONLY |
| HYBRID | MANUAL | 40,916,364 | 40,916,364 | CANONICAL_LIFECYCLE_IDENTITY_KNOWN_OPEX_ONLY |
| MRT_DOMINANT | AUTOMATED | 31,044,089 | 31,044,089 | CANONICAL_LIFECYCLE_IDENTITY_KNOWN_OPEX_ONLY |
| HYBRID | AUTOMATED | 38,308,122 | 38,308,122 | CANONICAL_LIFECYCLE_IDENTITY_KNOWN_OPEX_ONLY |
| HYBRID | MRT_DOMINANT | 7,264,032 | 7,264,032 | CANONICAL_LIFECYCLE_IDENTITY_KNOWN_OPEX_ONLY |

This is a diagnostic threshold; canonical architecture CapEx is unchanged.

## TABLE 25 — Known-OPEX Break-Even Thresholds (read-only)

| Challenger | Reference | Required annual known-OPEX savings for break-even ($/yr) |
|---|---|--:|
| AUTOMATED | MANUAL | 388,705 |
| MRT_DOMINANT | MANUAL | 5,015,190 |
| HYBRID | MANUAL | 6,097,745 |
| MRT_DOMINANT | AUTOMATED | 4,626,485 |
| HYBRID | AUTOMATED | 5,709,040 |
| HYBRID | MRT_DOMINANT | 1,082,555 |

`= known lifecycle gap / AF (6.710081)`. Uncalibrated components are never treated as zero.

## TABLE 26 — Full-OPEX Calibration Limitations

| Item | Status |
|---|---|
| Total annual OPEX | NOT_CALIBRATED |
| Full-OPEX break-even | FULL_OPEX_BREAK_EVEN_NOT_CALCULABLE |
| Reason | scanner/cyclotron/generator/MRT service/energy/procurement unit costs NOT_CALIBRATED (never zero-filled) |
| Known subtotal | reported and used for all break-even math |

## TABLE 27 — Decision-Critical Calibration Priorities

| Gap | Category | Current status | Classification |
|---|---|---|---|
| production_output_c11 | PRODUCTION | NOT_CALIBRATED | POTENTIALLY_DECISION_CRITICAL |
| production_output_n13 | PRODUCTION | NOT_CALIBRATED | POTENTIALLY_DECISION_CRITICAL |
| production_output_o15 | PRODUCTION | NOT_CALIBRATED | POTENTIALLY_DECISION_CRITICAL |
| production_output_ga68 | PRODUCTION | NOT_CALIBRATED | POTENTIALLY_DECISION_CRITICAL |
| mrt_maintenance | MRT | NOT_CALIBRATED | UNLIKELY_TO_CHANGE_CURRENT_DECISION |
| mrt_energy | MRT | NOT_CALIBRATED | UNLIKELY_TO_CHANGE_CURRENT_DECISION |
| scanner_power_energy | SCANNER | NOT_CALIBRATED | UNLIKELY_TO_CHANGE_CURRENT_DECISION |
| scanner_service | SCANNER | NOT_CALIBRATED | UNLIKELY_TO_CHANGE_CURRENT_DECISION |
| scanner_setup_turnover | SCANNER | NOT_CALIBRATED | UNLIKELY_TO_CHANGE_CURRENT_DECISION |
| cyclotron_facility_power | CYCLOTRON | NOT_CALIBRATED | UNLIKELY_TO_CHANGE_CURRENT_DECISION |
| cyclotron_consumables | CYCLOTRON | NOT_CALIBRATED | UNLIKELY_TO_CHANGE_CURRENT_DECISION |
| cyclotron_service | CYCLOTRON | NOT_CALIBRATED | UNLIKELY_TO_CHANGE_CURRENT_DECISION |
| generator_procurement | GENERATOR | NOT_CALIBRATED | UNLIKELY_TO_CHANGE_CURRENT_DECISION |
| generator_service | GENERATOR | NOT_CALIBRATED | UNLIKELY_TO_CHANGE_CURRENT_DECISION |
| porter_staffing_rate | STAFFING | CONTROLLED_ASSUMPTION | UNLIKELY_TO_CHANGE_CURRENT_DECISION |

Rationale (reconciled — each `UNLIKELY_TO_CHANGE` is backed by a deterministic argument, never "unknown ⇒ unimportant"):
- **MRT maintenance / MRT energy** fall **only** on higher-lifecycle challengers (MRT-family), so any *positive* value can only WIDEN the gap against Manual, never close it. Directionally proven regardless of magnitude.
- **Scanner / cyclotron / generator** costs live in the **common project ledger**, which is numerically **identical** for Manual and the second-best Automated ($4,681,480/yr for both). They therefore cancel **exactly** in the Manual-vs-Automated pairwise gap — a verified equality, not an approximation.
- **Porter staffing rate** does **not** cancel: Manual carries 33 porter FTE vs Automated 34 porter FTE. It is nonetheless `UNLIKELY_TO_CHANGE` on a **deterministic threshold**: Automated uses ≥ Manual porter FTE *and* carries +$1.8 M CapEx, so any positive porter wage keeps Manual at least as cheap — no positive rate can flip the ranking. (The prior "common / cancels" rationale for porter was factually wrong and is corrected.)
- **Production output** (C-11/N-13/O-15/Ga-68) is a WORKLOAD/feasibility dimension — a plausible value cannot re-order the cost-only ranking but could change per-radionuclide ADMISSIBILITY, hence **POTENTIALLY_DECISION_CRITICAL**; kept NOT_CALIBRATED, never fabricated.

No gap is labelled `UNLIKELY_TO_CHANGE` merely because its current known subtotal is zero or absent; each such label rests on an exact cancellation or a proven directional bound. Where no deterministic bound exists, the classification is `POTENTIALLY_DECISION_CRITICAL` or `NOT_ASSESSABLE` rather than `UNLIKELY_TO_CHANGE`.

## TABLE 28 — Production Calibration Priorities

| Radionuclide | Best available source | Calibration | Decision effect |
|---|---|---|---|
| F-18 | GE PETtrace 890 | manufacturer_calibrated | admissible + PRODUCTION_SUFFICIENT |
| C-11 | GE PETtrace 800 (modeled) / others not_calibrated | NOT_CALIBRATED | admissible with uncalibrated production |
| N-13 | IBA/Siemens/ACSI | NOT_CALIBRATED | admissible with uncalibrated production |
| O-15 | IBA/Siemens/ACSI | NOT_CALIBRATED | admissible with uncalibrated production |
| Ga-68 (cyc) | SUMITOMO CYPRIS MP-30 | NOT_CALIBRATED | admissible with uncalibrated production |
| Ga-68 (gen) | Ge-68/Ga-68 generator | NOT_CALIBRATED | admissible with uncalibrated production |

Production output remains NOT_CALIBRATED where quantitative evidence is absent — never closed aspirationally.

## TABLE 29 — Scanner Calibration Priorities

| Gap | Status | Classification | Note |
|---|---|---|---|
| scanner active/standby power | NOT_CALIBRATED | UNLIKELY_TO_CHANGE_CURRENT_DECISION | common to all four; cancels in pairwise gap |
| scanner service/maintenance price | NOT_CALIBRATED | UNLIKELY_TO_CHANGE_CURRENT_DECISION | common to all four |
| scanner setup / turnover | NOT_CALIBRATED | UNLIKELY_TO_CHANGE_CURRENT_DECISION | affects throughput/feasibility, not ranking |

## TABLE 30 — Generator Calibration Priorities

| Gap | Status | Classification | Note |
|---|---|---|---|
| generator procurement price | NOT_CALIBRATED | UNLIKELY_TO_CHANGE_CURRENT_DECISION | replacement schedule derivable in units; dollars NOT_CALIBRATED |
| generator service | NOT_CALIBRATED | UNLIKELY_TO_CHANGE_CURRENT_DECISION | not fabricated |

## TABLE 31 — MRT Calibration Priorities

| Gap | Status | Classification | Note |
|---|---|---|---|
| MRT maintenance | NOT_CALIBRATED | UNLIKELY_TO_CHANGE_CURRENT_DECISION | falls only on MRT-family challengers; can only widen the gap vs Manual |
| MRT energy | NOT_CALIBRATED | UNLIKELY_TO_CHANGE_CURRENT_DECISION | disclosed lower bound only; total NOT_CALIBRATED |

## TABLE 32 — Ranking Robustness

| Field | Value |
|---|---|
| Preferred | MANUAL_CONVENTIONAL |
| Second-best | AUTOMATED_CONVENTIONAL |
| Known lifecycle gap ($) | 2,608,243 |
| Required annual known-OPEX swing to reorder ($/yr) | 388,705 |
| Required CapEx swing to reorder ($) | 2,608,243 |
| Robustness | DECISION_SENSITIVE |

Robustness is reported on **known** economics (total OPEX remains NOT_CALIBRATED). The preferred→second gap ($2.61 M) is ~0.22× the preferred architecture's own lifecycle, below the 0.25× robust threshold — a plausible NOT_CALIBRATED swing could reorder Manual vs Automated (but not the far larger gaps to MRT/Hybrid).

## TABLE 33 — Short-Half-Life Decision Envelope

| Radionuclide | Half-life (min) | MRT retained (benchmark) | Req. upstream MRT (MBq) | Distance crossover | Speed crossover | Volume crossover | Decision region |
|---|--:|--:|--:|---|---|---|---|
| C-11 | 20.3 | 0.2830 | 1,961 | NO_CROSSOVER_WITHIN_DEFENSIBLE_ENVELOPE | NO | NO (ranking stable) | MANUAL preferred |
| N-13 | 9.97 | 0.0765 | 9,673 | NO_CROSSOVER_WITHIN_DEFENSIBLE_ENVELOPE | NO | NO | MANUAL preferred |
| O-15 | 2.04 | ~0.0000 | 3.17e8 | NO_CROSSOVER_WITHIN_DEFENSIBLE_ENVELOPE | NO | NO | MANUAL preferred |

C-11/N-13/O-15 are treated individually (never collapsed into one "short half-life" result).

## TABLE 34 — C-11 Interpretation

| Field | Value |
|---|---|
| Half-life | 20.3 min |
| Transport-time consequence | MRT saves ~1.94 min vs Manual on the benchmark route |
| Retained fraction (manual / MRT) | 0.2649 / 0.2830 |
| Required upstream (manual / MRT) | 2,095 / 1,961 MBq |
| Production sources | IBA_CYCLONE_KIUBE (not_calibrated), GE_PETTRACE_800 (modeled), SIEMENS_CTI_ECLIPSE_HP (not_calibrated) |
| Production calibration | NOT_CALIBRATED |
| Scanner modality | PET |
| Architecture ranking | MANUAL < AUTOMATED < MRT < HYBRID |
| Distance / speed / volume crossover | none |
| Decision region | MANUAL preferred |

## TABLE 35 — N-13 Interpretation

| Field | Value |
|---|---|
| Half-life | 9.97 min |
| Transport-time consequence | MRT saves ~1.94 min |
| Retained fraction (manual / MRT) | 0.0669 / 0.0765 |
| Required upstream (manual / MRT) | 11,067 / 9,673 MBq |
| Production sources | IBA_CYCLONE_KIUBE, SIEMENS_CTI_RDS_111, ACSI_TR_19 (all not_calibrated) |
| Production calibration | NOT_CALIBRATED |
| Scanner modality | PET |
| Architecture ranking | MANUAL < AUTOMATED < MRT < HYBRID |
| Distance / speed / volume crossover | none |
| Decision region | MANUAL preferred |

## TABLE 36 — O-15 Interpretation

| Field | Value |
|---|---|
| Half-life | 2.04 min |
| Transport-time consequence | MRT saves ~1.94 min; extreme decay sensitivity |
| Retained fraction (manual / MRT) | ~0.0000 / ~0.0000 |
| Required upstream (manual / MRT) | 6.12e8 / 3.17e8 MBq (feasibility observation) |
| Production sources | IBA_CYCLONE_KIUBE, SIEMENS_CTI_ECLIPSE_HP, ACSI_TR_19 (all not_calibrated) |
| Production calibration | NOT_CALIBRATED |
| Scanner modality | PET |
| Architecture ranking | MANUAL < AUTOMATED < MRT < HYBRID |
| Distance / speed / volume crossover | none |
| Decision region | MANUAL preferred (no forced feasibility despite decay) |

## TABLE 37 — Ga-68 Cyclotron vs Generator

| Dimension | Cyclotron (SUMITOMO CYPRIS MP-30) | Generator (Ge-68/Ga-68 GALLIAPHARM) |
|---|---|---|
| Production burden | on-site bombardment; declares Ga-68, NOT_CALIBRATED | on-site elution; no cyclotron production leg |
| Decay burden | half-life 67.7 min; retained 0.6849 (MRT) | same isotope decay physics |
| Transport burden | radiopharmacy → clinic route | shorter (on-site elution) |
| Known OPEX | benchmark-basis (uncalibrated MRT/production components) | procurement/service NOT_CALIBRATED |
| Unknown OPEX | production output NOT_CALIBRATED | generator procurement/service NOT_CALIBRATED |
| Architecture ranking | MANUAL preferred | MANUAL preferred |
| Pathway | `GA68_CYCLOTRON_PATHWAY = YES` | `GA68_GENERATOR_PATHWAY = YES` |

`GA68_PATHWAYS_DISTINCT = YES`. Generator economics remain NOT_CALIBRATED where physically absent.

## TABLE 38 — Mixed PET Scheduling Risk

| Field | Value |
|---|---|
| Scenario | F-18 + C-11 + N-13 + O-15 (explicit counts) |
| True joint scheduling | NO |
| Joint operational feasibility | NOT_FULLY_VALIDATED |
| Shared-resource risk | cyclotron production windows + PET scanner pool + uptake/injection + transport shared across PET radionuclides |
| Decision effect | ranking is CapEx/known-OPEX dominant and stable; scheduling affects operating feasibility, not the architecture ranking |

## TABLE 39 — Mixed PET+SPECT Scheduling Risk

| Field | Value |
|---|---|
| Scenario | F-18 (PET) + Tc-99m (SPECT) + Ga-68 (PET) |
| True joint scheduling | NO |
| Joint operational feasibility | NOT_FULLY_VALIDATED |
| Shared-resource risk | PET pool + distinct SPECT pool (Tc-99m) + shared transport/uptake/injection |
| Scanner pools | PET and SPECT kept DISTINCT (no silent sharing) |
| Decision effect | ranking stable; scheduling is an operating-feasibility deliverable |

## TABLE 40 — Joint-Scheduler Decision Gate

| Field | Value |
|---|---|
| TRUE_JOINT_MULTI_RADIONUCLIDE_SCHEDULING | NO |
| Mixed-PET joint feasibility | NOT_FULLY_VALIDATED |
| Mixed-PET+SPECT joint feasibility | NOT_FULLY_VALIDATED |
| Decision importance (for architecture selection) | LOW |
| Recommendation | DEFER for architecture selection; ranking CapEx/known-OPEX dominant and stable across all tested mixes. The scheduler remains required to promote mixed scenarios from Phase-1 AGGREGATION to a VALIDATED_OPERATING_SCHEDULE (an operating-feasibility deliverable, not an architecture-decision blocker). |
| Unresolved shared-resource interactions | cyclotron production windows; PET scanner pool; SPECT scanner pool; uptake rooms + injection; transport resources |

## TABLE 41 — Architecture Decision Regions

| Region | Radionuclide | Preferred | 2nd-best | Known cost gap ($) | Physical state | Robustness | Driver |
|---|---|---|---|--:|---|---|---|
| EXP1 F-18 | F-18 | MANUAL | AUTOMATED | 2,608,243 | FEASIBLE_WITH_UNCALIBRATED_PRODUCTION_CAPACITY | DECISION_SENSITIVE | KNOWN_OPEX_DOMINANT |
| EXP2 C-11 | C-11 | MANUAL | AUTOMATED | 2,608,243 | FEASIBLE_WITH_UNCALIBRATED_PRODUCTION_CAPACITY | DECISION_SENSITIVE | KNOWN_OPEX_DOMINANT |
| EXP3 N-13 | N-13 | MANUAL | AUTOMATED | 2,608,243 | FEASIBLE_WITH_UNCALIBRATED_PRODUCTION_CAPACITY | DECISION_SENSITIVE | KNOWN_OPEX_DOMINANT |
| EXP4 O-15 | O-15 | MANUAL | AUTOMATED | 2,608,243 | FEASIBLE_WITH_UNCALIBRATED_PRODUCTION_CAPACITY | DECISION_SENSITIVE | KNOWN_OPEX_DOMINANT |
| EXP9A Ga-68 cyc | Ga-68 | MANUAL | AUTOMATED | 2,608,243 | FEASIBLE_WITH_UNCALIBRATED_PRODUCTION_CAPACITY | DECISION_SENSITIVE | KNOWN_OPEX_DOMINANT |
| EXP9B Ga-68 gen | Ga-68 | MANUAL | AUTOMATED | 2,608,243 | FEASIBLE_WITH_UNCALIBRATED_PRODUCTION_CAPACITY | DECISION_SENSITIVE | KNOWN_OPEX_DOMINANT |

## TABLE 42 — MRT-Dominant Decision Region

| Field | Value |
|---|---|
| MRT_DOMINANT decision region | NO_MRT_DOMINANT_DECISION_REGION_OBSERVED |
| Reason | across every tested radionuclide/source/distance/speed/volume/mix, MRT_DOMINANT never became cost-only rank 1 at the benchmark basis |
| Threshold to reach rank 1 vs Manual | shed $33.65 M lifecycle (or $5.02 M/yr known-OPEX savings) |

## TABLE 43 — Hybrid MRT Decision Region

| Field | Value |
|---|---|
| HYBRID_MRT decision region | NO_HYBRID_DECISION_REGION_OBSERVED |
| Reason | HYBRID_MRT is rank 4 across every tested condition |
| Threshold to reach rank 1 vs Manual | shed $40.92 M lifecycle (or $6.10 M/yr known-OPEX savings) |

## TABLE 44 — No-Crossover Conditions

| Envelope | Condition | Result |
|---|---|---|
| Distance | 0.5×–3.0× benchmark route | NO_CROSSOVER_WITHIN_DEFENSIBLE_ENVELOPE |
| MRT speed | SLOW–VERY_FAST (controlled) | NO_CROSSOVER_OBSERVED |
| Patient volume | LOW–HIGH explicit counts | NO_CROSSOVER (ranking stable) |
| Radionuclide/half-life | F-18/C-11/N-13/O-15/Ga-68 | NO_CROSSOVER |
| Production source | calibrated vs modeled vs not_calibrated | NO_CROSSOVER |

## TABLE 45 — Decision-Envelope Summary by Radionuclide

| Radionuclide | Preferred | Production calibration | Decision region |
|---|---|---|---|
| F-18 | MANUAL | manufacturer_calibrated | MANUAL preferred |
| C-11 | MANUAL | NOT_CALIBRATED | MANUAL preferred |
| N-13 | MANUAL | NOT_CALIBRATED | MANUAL preferred |
| O-15 | MANUAL | NOT_CALIBRATED | MANUAL preferred |
| Ga-68 (cyc) | MANUAL | NOT_CALIBRATED | MANUAL preferred |
| Ga-68 (gen) | MANUAL | NOT_CALIBRATED | MANUAL preferred |

## TABLE 46 — Decision-Envelope Summary by Distance

| Distance multiplier | Preferred | Crossover |
|---|---|---|
| 0.5× | MANUAL | none |
| 1.0× | MANUAL | none |
| 1.5× | MANUAL | none |
| 2.0× | MANUAL | none |
| 3.0× | MANUAL | none |

## TABLE 47 — Decision-Envelope Summary by Patient Volume

| Level | Preferred | Detailed scheduling |
|---|---|---|
| LOW | MANUAL | NOT_FULLY_VALIDATED |
| BASELINE | MANUAL | VALIDATED_OPERATING_SCHEDULE |
| HIGH | MANUAL | NOT_FULLY_VALIDATED |

## TABLE 48 — Decision-Envelope Summary by Production Source

| Source type | Calibration | Preferred | Effect |
|---|---|---|---|
| CYCLOTRON (F-18 GE) | manufacturer_calibrated | MANUAL | PRODUCTION_SUFFICIENT |
| CYCLOTRON (C-11/N-13/O-15/Ga-68) | NOT_CALIBRATED | MANUAL | admissible w/ uncalibrated production |
| GENERATOR (Ga-68) | NOT_CALIBRATED | MANUAL | admissible w/ uncalibrated production |

## TABLE 49 — Decision-Envelope Summary by MRT Speed

| Speed | Preferred | Crossover |
|---|---|---|
| SLOW (1.5/0.75) | MANUAL | none |
| BASELINE (3.0/1.5) | MANUAL | none |
| FAST (6.0/3.0) | MANUAL | none |
| VERY_FAST (9.0/4.5) | MANUAL | none |

## TABLE 50 — Principal Decision Driver by Experiment

| Experiment | Scenario | Preferred | Principal driver |
|---|---|---|---|
| EXP0 | BASELINE_F18_TC99M | MANUAL | KNOWN_OPEX_DOMINANT |
| EXP1 | F18_CONTROL | MANUAL | KNOWN_OPEX_DOMINANT |
| EXP2 | C11_CONTROL | MANUAL | KNOWN_OPEX_DOMINANT |
| EXP3 | N13_CONTROL | MANUAL | KNOWN_OPEX_DOMINANT |
| EXP4 | O15_CONTROL | MANUAL | KNOWN_OPEX_DOMINANT |
| EXP6_* | DISTANCE_* | MANUAL | KNOWN_OPEX_DOMINANT |
| EXP9A | GA68_CYCLOTRON | MANUAL | KNOWN_OPEX_DOMINANT |
| EXP9B | GA68_GENERATOR | MANUAL | KNOWN_OPEX_DOMINANT |
| EXP11 | MIXED_PET | MANUAL | KNOWN_OPEX_DOMINANT |
| EXP12 | MIXED_PET_SPECT | MANUAL | KNOWN_OPEX_DOMINANT |

## TABLE 51 — Known vs Unknown Economic Drivers

| Component | Known / Unknown | In ranking? |
|---|---|---|
| New study CapEx | KNOWN | yes |
| Known annual OPEX subtotal | KNOWN | yes (via lifecycle) |
| Total annual OPEX | NOT_CALIBRATED | no (never zero-filled) |
| MRT maintenance/energy | NOT_CALIBRATED | no |
| Scanner/cyclotron/generator service/energy | NOT_CALIBRATED | no |
| Production output (C-11/N-13/O-15/Ga-68) | NOT_CALIBRATED | feasibility only |

## TABLE 52 — Calibration Value Required to Change Ranking

| Comparison | Value required to reorder |
|---|---|
| Manual → Automated | $388,705/yr known-OPEX swing (or $2.61 M CapEx) |
| Manual → MRT_DOMINANT | $5.02 M/yr known-OPEX savings (or $33.65 M CapEx) |
| Manual → HYBRID | $6.10 M/yr known-OPEX savings (or $40.92 M CapEx) |

Deterministic thresholds — not confidence intervals, not probabilities.

## TABLE 53 — Decision Robustness Classification

| Pair | Gap ($) | Classification |
|---|--:|---|
| Manual vs Automated | 2,608,243 | DECISION_SENSITIVE (gap < 0.25× preferred lifecycle) |
| Manual vs MRT_DOMINANT | 33,652,332 | ROBUST on known economics |
| Manual vs HYBRID | 40,916,364 | ROBUST on known economics |

The overall preferred-vs-second robustness is DECISION_SENSITIVE (Manual vs Automated is the closest pair).

## TABLE 54 — Joint-Scheduling Limitation Impact

| Dimension | Impact on architecture selection |
|---|---|
| Cyclotron production windows | none on ranking (CapEx/OPEX dominant); affects validated throughput |
| PET scanner pool | none on ranking |
| SPECT scanner pool | none on ranking |
| Uptake/injection | none on ranking |
| Transport | none on ranking |
| Overall importance | LOW (architecture selection); required for VALIDATED operating schedule |

## TABLE 55 — Patient Export Preview (baseline scenario)

| Scenario | Radionuclide | Modality | Patients | Source | Production gate |
|---|---|---|--:|---|---|
| BASELINE_F18_TC99M | F-18 | PET | 32 | PETtrace 890 | PRODUCTION_SUFFICIENT |
| BASELINE_F18_TC99M | Tc-99m | SPECT | 18 | CURIUM_TECHNELITE | PRODUCTION_NOT_CALIBRATED |

## TABLE 56 — Forward Appointment Export Preview

| Scenario | Radionuclide | Patients | Modality | Source identity | Appointment date | Forward-plan status |
|---|---|--:|---|---|---|---|
| BASELINE_F18_TC99M | F-18 | 32 | PET | PETtrace 890 | NOT_MODELED | ANALYTICAL_REQUIREMENT_NOT_A_VALIDATED_SCHEDULE |
| BASELINE_F18_TC99M | Tc-99m | 18 | SPECT | CURIUM_TECHNELITE | NOT_MODELED | ANALYTICAL_REQUIREMENT_NOT_A_VALIDATED_SCHEDULE |
| MIXED_PET_SPECT | F-18 | 24 | PET | PETtrace 890 | NOT_MODELED | ANALYTICAL_REQUIREMENT_NOT_A_VALIDATED_SCHEDULE |
| MIXED_PET_SPECT | Tc-99m | 16 | SPECT | CURIUM_TECHNELITE | NOT_MODELED | ANALYTICAL_REQUIREMENT_NOT_A_VALIDATED_SCHEDULE |
| MIXED_PET_SPECT | Ga-68 | 6 | PET | ECKERT_ZIEGLER_GALLIAPHARM | NOT_MODELED | ANALYTICAL_REQUIREMENT_NOT_A_VALIDATED_SCHEDULE |

No upstream scheduling authority supplies a real appointment date; the date is explicitly NOT_MODELED (never fabricated).

## TABLE 57 — Financial Export Preview (baseline scenario)

| Architecture | New study CapEx ($) | Known annual OPEX ($) | Lifecycle cost ($) | True-total annual OPEX ($) | Total-comparable project CapEx ($) |
|---|--:|--:|--:|--:|--:|
| MANUAL_CONVENTIONAL | 125,000 | 1,750,320 | 11,869,790 | 6,771,800 | 125,000 |
| AUTOMATED_CONVENTIONAL | 1,925,000 | 1,870,772 | 14,478,032 | 6,892,252 | 1,925,000 |
| MRT_DOMINANT | 11,480,000 | 5,073,280 | 45,522,122 | 5,073,280 | 11,480,000 |
| HYBRID_MRT | 7,106,000 | 6,807,690 | 52,786,154 | 6,807,690 | 7,106,000 |

## TABLE 58 — Simulation Performance Measurements (wall-clock; excludes pytest/collection/git/report time)

| Measurement | Wall-clock (s) |
|---|--:|
| A. Single Part 3E scenario | 0.61 |
| B. Four-architecture bouquet | 0.58 |
| C. Distance sensitivity sweep | 0.64 |
| D. Patient-volume sensitivity sweep | 8.88 |
| E. Production-source comparison | ~0.00 |
| F. Full Part 3E.2 campaign | 17.32 |

`SIMULATION_EXECUTION_TIME` is measured here; `REGRESSION_TEST_TIME` is measured separately (see final report). No optimization performed — baseline only.

## TABLE 59 — Remaining Decision-Critical Gaps

| Gap | Status | Why still open |
|---|---|---|
| Production output C-11/N-13/O-15/Ga-68 | NOT_CALIBRATED | no quantitative EOB evidence for these pairs |
| Total annual OPEX | NOT_CALIBRATED | scanner/cyclotron/generator/MRT service/energy/procurement unit costs absent |
| True joint multi-radionuclide scheduling | NOT_FULLY_VALIDATED | scheduler not built (out of scope); mixed scenarios remain Phase-1 AGGREGATION |
| Forward appointment dates | NOT_MODELED | no calendar/scheduling authority supplies dates |

None closed aspirationally.

## TABLE 60 — Final Part 3E.2 Decision Envelope

| Field | Value |
|---|---|
| Preferred architecture (all tested conditions) | MANUAL_CONVENTIONAL |
| Second-best | AUTOMATED_CONVENTIONAL |
| Principal baseline driver | KNOWN_OPEX_DOMINANT (QUALIFIED — full-bouquet known spread; decisive Manual-vs-Automated margin is CapEx-led; total OPEX NOT_CALIBRATED) |
| `PHYSICALLY_RECOGNIZED_RADIONUCLIDE_COUNT` | 15 (canonical universe) |
| `PART3E2_RADIONUCLIDES_ANALYZED_COUNT` | 6 (F-18, C-11, N-13, O-15, Ga-68, Tc-99m — strict subset) |
| MRT-dominant decision region | NO_MRT_DOMINANT_DECISION_REGION_OBSERVED |
| Hybrid decision region | NO_HYBRID_DECISION_REGION_OBSERVED |
| Manual decision region | YES |
| Automated decision region | NO |
| Distance crossover | NONE within 0.5×–3.0× |
| MRT-speed crossover | NONE (SLOW–VERY_FAST) |
| Patient-volume crossover | NONE |
| Production-source crossover | NONE |
| Ranking robustness | DECISION_SENSITIVE (Manual vs Automated) |
| Joint-scheduler importance | LOW (architecture selection) |
| Total OPEX | NOT_CALIBRATED |
| Full-OPEX break-even | NOT_CALCULABLE (`FULL_OPEX_BREAK_EVEN_AVAILABLE = NO`) |

## TABLE 60A — Existing-Facility AS-IS Twin Readiness (clarified)

`READY_FOR_EXISTING_FACILITY_AS_IS_TWIN` must **not** be read as "the AS-IS facility twin has been built." It has not. The following states are the physical repository truth at HEAD `93bf687`:

| Field | Value |
|---|---|
| `EXISTING_FACILITY_AS_IS_TWIN_IMPLEMENTED` | **NO** |
| `FACILITY_INGESTION_IMPLEMENTED` | **NO** |
| `BIM/CAD/PDF/IMAGE_RECONSTRUCTION_IMPLEMENTED` | **NO** (only a `SYNTHETIC_TEST_BIM` proof model exists via `ifc_hospital_proof_model_generator.py` for Bentley/iTwin integration proof — it is not an ingested real facility) |
| `LIVE_HOSPITAL_OPERATIONAL_STATE_INGESTION_IMPLEMENTED` | **NO** |
| `READY_TO_BEGIN_EXISTING_FACILITY_AS_IS_TWIN_BUILD` | **YES** — the canonical spatial authority + synthetic IFC/iTwin proof seam provide a defensible starting point; the AS-IS twin build is **not** started here. |

Part 3E.2 does not begin the AS-IS twin build.

---

# Report Narrative (Section 33)

## A. Why Part 3E.1 rankings were stable

The four-architecture economics are anchored to the benchmark facility's validated single-radionuclide nuclear basis (the joint-scheduling governor forbids forcing a multi-radionuclide aggregate through the single-radionuclide engine). At that fixed basis the architecture economics do not vary with radionuclide identity, distance, or MRT speed. The lifecycle ranking is therefore governed by two known quantities: new study CapEx and the known annual OPEX subtotal. Manual carries the smallest of both, so it is preferred everywhere; MRT-family architectures carry large CapEx (guideway/endpoints/carriers) and — for MRT_DOMINANT and HYBRID — higher known OPEX subtotals, so they rank 3 and 4. The radionuclide-specific consequences (decay, required upstream activity, production calibration, scanner modality, transport time) are computed per radionuclide and reported as OBSERVATIONS; they do not enter the ranking.

## B. Architecture cost/effect decomposition

Against Manual: Automated adds $1.8 M CapEx and $120 k/yr known OPEX (Δlifecycle $2.61 M); MRT_DOMINANT adds $11.36 M CapEx and $3.32 M/yr known OPEX (Δlifecycle $33.65 M) yet has a *lower* true-total annual OPEX (−$1.70 M); HYBRID adds $6.98 M CapEx and $5.06 M/yr known OPEX (Δlifecycle $40.92 M). Physically, MRT's shorter route time improves retained activity for every radionuclide (e.g. F-18 0.7822→0.7918), reducing required upstream activity — a real benefit that the CapEx/known-OPEX-dominated ranking does not monetize at the benchmark basis.

## C. Distance decision envelope

Over 0.5×–3.0× of the benchmark worst-case route, MRT transport time stays roughly half of Manual and retained fractions shift only slightly; the preferred architecture is Manual at every tested point. `F18/C11/N13/O15_DISTANCE_CROSSOVER_STATUS = NO_CROSSOVER_WITHIN_DEFENSIBLE_DISTANCE_ENVELOPE`.

## D. Patient-volume decision envelope

Explicit LOW/BASELINE/HIGH counts change scanner and production requirements but not the architecture ranking. BASELINE counts are validated by the single-radionuclide engine; LOW/HIGH counts beyond the canonical subset are reported as ANALYTICAL_REQUIREMENT with DETAILED_SCHEDULING_NOT_FULLY_VALIDATED (never forced through the scheduler).

## E. MRT-speed envelope

Speed (SLOW→VERY_FAST) is a CONTROLLED_EXPERIMENTAL_ASSUMPTION. Faster MRT reduces transport time (F-18 2.68→1.50 min) and marginally raises retained activity, but does not change the benchmark-basis ranking. `MRT_SPEED_CROSSOVER_FOUND = NO`.

## F. Production-source envelope

Each radionuclide resolves its own compatible source and calibration status. Only F-18 (GE PETtrace 890) is manufacturer_calibrated; C-11/N-13/O-15/Ga-68 are NOT_CALIBRATED on every candidate source; the Ga-68 cyclotron (SUMITOMO CYPRIS MP-30) and generator (GALLIAPHARM) pathways are distinct and both NOT_CALIBRATED. A calibrated F-18 record never qualifies another radionuclide.

## G. Short-half-life findings

C-11, N-13, O-15 are treated individually. Shorter half-life sharply raises required upstream activity (N-13 ~11,067 MBq; O-15 astronomically large), but does not cause an MRT win — the ranking is economic, not decay-driven.

## H. Ga-68 pathway findings

`GA68_CYCLOTRON_PATHWAY = YES`, `GA68_GENERATOR_PATHWAY = YES`, `GA68_PATHWAYS_DISTINCT = YES`. The generator removes the cyclotron production leg but its procurement/service economics remain NOT_CALIBRATED. Neither pathway changes the preferred architecture.

## I. Break-even thresholds

Read-only, from the canonical lifecycle identity. To make MRT_DOMINANT tie Manual would require shedding $33.65 M lifecycle (≈ $5.02 M/yr known-OPEX savings); HYBRID $40.92 M (≈ $6.10 M/yr). Full-OPEX break-even is NOT_CALCULABLE because total OPEX is NOT_CALIBRATED.

## J. Decision-critical calibration priorities

Production output gaps (C-11/N-13/O-15/Ga-68) are POTENTIALLY_DECISION_CRITICAL — a workload/feasibility (admissibility) dimension, not a cost-ranking one. MRT maintenance/energy are UNLIKELY_TO_CHANGE_CURRENT_DECISION (they fall only on higher-lifecycle challengers and can only widen the gap against Manual). Scanner/cyclotron/generator costs sit in the common project ledger, which is numerically identical for Manual and Automated ($4,681,480/yr each), so they cancel exactly in the pairwise gap. Porter labor does **not** cancel (Manual 33 FTE vs Automated 34 FTE), but is still UNLIKELY_TO_CHANGE on a deterministic threshold: Automated uses ≥ Manual porter FTE and carries +$1.8 M CapEx, so no positive porter wage can flip the ranking. Every UNLIKELY_TO_CHANGE label rests on an exact cancellation or a proven directional bound — never on the absence of a known value.

## K. Joint-scheduler decision gate

`JOINT_SCHEDULER_DECISION_IMPORTANCE = LOW` for architecture selection (ranking is CapEx/known-OPEX dominant and stable). Recommendation: DEFER the joint scheduler for the architecture decision; it remains required to promote mixed scenarios from Phase-1 AGGREGATION to a VALIDATED_OPERATING_SCHEDULE.

## L. Simulation-performance baseline

Single scenario ~0.6 s; four-architecture bouquet ~0.6 s; distance sweep ~0.6 s; patient-volume sweep ~8.9 s; production-source comparison ~0 s; full campaign ~17.3 s. This is USER SIMULATION latency, distinct from regression-test time. No optimization performed.

## M. Remaining gaps

Production output for C-11/N-13/O-15/Ga-68 and total OPEX remain NOT_CALIBRATED; true joint multi-radionuclide scheduling remains NOT_FULLY_VALIDATED; forward appointment dates remain NOT_MODELED. None closed aspirationally.

## O. Physical radionuclide universe vs analyzed subset (reconciled)

The canonical **physical universe** is 15 radionuclides, consumed directly from the Clinical Radionuclide Completeness authority (`discover_physically_recognized_radionuclides()`): At-211, C-11, Cu-64, F-18, Ga-68, Ge-68, I-123, I-124, In-111, Mo-99, N-13, O-15, Tc-99m, Tl-201, Zr-89. Part 3E.2 **analyzed** a strict subset of 6 — F-18 (calibrated control), C-11/N-13/O-15 (short-half-life), Ga-68 (cyclotron and generator pathways), and Tc-99m (mixed PET+SPECT / joint-scheduler gate / forward export). A prior draft reported "6 tested" as though it were the physical universe; the two are now reported separately. The experiment campaign was **not** widened merely to make the analyzed count reach 15 — the remaining nine physically-recognized radionuclides are catalogued in the completeness authority but were outside the Part 3E.1 decision-envelope campaign.

## P. Existing-facility AS-IS twin readiness (reconciled)

`READY_FOR_EXISTING_FACILITY_AS_IS_TWIN` is a **readiness-to-begin** signal, not a completed capability. `EXISTING_FACILITY_AS_IS_TWIN_IMPLEMENTED = NO`, `FACILITY_INGESTION_IMPLEMENTED = NO`, `BIM/CAD/PDF/IMAGE_RECONSTRUCTION_IMPLEMENTED = NO` (only a `SYNTHETIC_TEST_BIM` Bentley/iTwin proof model exists — not an ingested real facility), and `LIVE_HOSPITAL_OPERATIONAL_STATE_INGESTION_IMPLEMENTED = NO`. `READY_TO_BEGIN_EXISTING_FACILITY_AS_IS_TWIN_BUILD = YES`. Part 3E.2 does not start that build.

## N. Exact physical git state

Recorded in the final report block (Section 33 of the driving prompt), produced at the end of the run via `git status --short`, `git diff --stat`, and `git diff --name-only`.
