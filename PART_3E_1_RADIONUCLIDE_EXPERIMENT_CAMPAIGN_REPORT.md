# Part 3E.1 — Controlled Radionuclide Architecture Experiment Campaign — Report

Self-contained experiment/analysis report. Every table below is generated
directly from `part3e_radionuclide_experiment_campaign.run_full_campaign()`,
which CONSUMES the committed Part 3E / 3D / 3C / 3B / 3A authorities. No new
physics, decay, production, transport, scanner, or economic engine was built.

**Central question.** Radionuclide + Production Source + Demand + Distance/
Transport Time + Clinical Resources → Architecture Bouquet. The result must
EMERGE from existing physics/economics. No MRT/Hybrid/Conventional bonus, no
short-half-life bonus, no penalty for MRT novelty.

**Engine-basis honesty (critical).** The four-architecture economics are
anchored to the validated benchmark single-radionuclide nuclear basis
(`nuclear_demand_override=None`) because the joint-scheduling governor forbids
forcing a multi-radionuclide aggregate through the single-radionuclide timing
engine. Therefore the *architecture economics/ranking* are stable across a pure
radionuclide-identity change at a fixed basis; the RADIONUCLIDE-SPECIFIC
consequences (decay, required upstream/EOB activity, production calibration,
scanner-modality requirement, transport time) are computed per radionuclide
through the real authorities and reported explicitly. This report states that
distinction rather than fabricating a radionuclide-driven economic delta the
engine does not model.

## TABLE 1 — Experiment Campaign Definition

| Experiment | Title | Radionuclide(s) |
|---|---|---|
| EXP0 | Baseline control (F-18 + Tc-99m) | F-18, Tc-99m |
| EXP1 | F-18 control (reference PET) | F-18 |
| EXP2 | C-11 control | C-11 |
| EXP3 | N-13 control | N-13 |
| EXP4 | O-15 control (very short half-life) | O-15 |
| EXP5 | Short-half-life comparison | F-18, C-11, N-13, O-15 |
| EXP6 | Distance/transport sensitivity | F-18, C-11, N-13, O-15 |
| EXP7 | MRT speed sensitivity | F-18, C-11, N-13, O-15 |
| EXP8 | Production-source sensitivity | C-11, N-13, O-15 |
| EXP9 | Ga-68 dual pathway (cyclotron vs generator) | Ga-68 |
| EXP10 | Patient-demand sensitivity | F-18, C-11, N-13, O-15, Ga-68 |
| EXP11 | Mixed PET | F-18, C-11, N-13, O-15 |
| EXP12 | Mixed PET + SPECT | F-18, Tc-99m, Ga-68 |
| EXP13 | Architecture crossover search | all above |

## TABLE 2 — Canonical Radionuclide Inputs

| Radionuclide | Half-life (min) | Clinical modality | Controlled admin activity (MBq) |
|---|---|---|---|
| F-18 | 109.80 | PET | 370.0 |
| C-11 | 20.30 | PET | 555.0 |
| N-13 | 9.97 | PET | 740.0 |
| O-15 | 2.04 | PET | 1110.0 |
| Ga-68 | 67.70 | PET | 185.0 |
| Tc-99m | 360.00 | SPECT | 740.0 |

## TABLE 3 — Selected Production Sources (per experiment)

| Experiment | Radionuclide | Selected source(s) | Kind |
|---|---|---|---|
| EXP1 | F-18 | GE_PETTRACE_890 (benchmark basis) | CYCLOTRON |
| EXP2 | C-11 | IBA_CYCLONE_KIUBE | CYCLOTRON |
| EXP3 | N-13 | IBA_CYCLONE_KIUBE | CYCLOTRON |
| EXP4 | O-15 | IBA_CYCLONE_KIUBE | CYCLOTRON |
| EXP9A | Ga-68 | SUMITOMO_CYPRIS_MP_30 | CYCLOTRON |
| EXP9B | Ga-68 | ECKERT_ZIEGLER_GALLIAPHARM | GENERATOR (Ge-68→Ga-68) |
| EXP0/baseline | F-18, Tc-99m | benchmark F-18 cyclotron + Mo-99/Tc-99m generator | CYCLOTRON + GENERATOR |

## TABLE 4 — Production Calibration Matrix (radionuclide × candidate cyclotron)

| Radionuclide | Source kind | Catalog model id | Manufacturer | Declares support | Schedulable | Calibrated EOB record | Production calibration status |
|---|---|---|---|---|---|---|---|
| C-11 | CYCLOTRON | IBA_CYCLONE_KIUBE | IBA | True | False | False | not_calibrated |
| C-11 | CYCLOTRON | GE_PETTRACE_800 | GE HealthCare | True | True | False | modeled |
| C-11 | CYCLOTRON | SIEMENS_CTI_ECLIPSE_HP | Siemens/CTI | True | False | False | not_calibrated |
| C-11 | CYCLOTRON | ACSI_TR_19 | ACSI | True | False | False | not_calibrated |
| N-13 | CYCLOTRON | IBA_CYCLONE_KIUBE | IBA | True | False | False | not_calibrated |
| N-13 | CYCLOTRON | GE_PETTRACE_800 | GE HealthCare | True | True | False | modeled |
| N-13 | CYCLOTRON | SIEMENS_CTI_RDS_111 | Siemens/CTI | True | False | False | not_calibrated |
| N-13 | CYCLOTRON | ACSI_TR_19 | ACSI | True | False | False | not_calibrated |
| O-15 | CYCLOTRON | IBA_CYCLONE_KIUBE | IBA | True | False | False | not_calibrated |
| O-15 | CYCLOTRON | GE_PETTRACE_800 | GE HealthCare | True | True | False | modeled |
| O-15 | CYCLOTRON | SIEMENS_CTI_ECLIPSE_HP | Siemens/CTI | True | False | False | not_calibrated |
| O-15 | CYCLOTRON | ACSI_TR_19 | ACSI | True | False | False | not_calibrated |
| F-18 | CYCLOTRON | GE_PETTRACE_890 | GE HealthCare | True | True | True | manufacturer_calibrated |

*Only F-18 on the GE PETtrace calibrated units carries a manufacturer-
calibrated EOB record. Every C-11/N-13/O-15 candidate DECLARES support but is
`modeled` (schedulable) or `not_calibrated` (declared-but-unschedulable) — a
calibrated F-18 record never qualifies another radionuclide, and support is
never converted into calibration.*

## TABLE 5 — Baseline F-18 + Tc-99m Bouquet (Experiment 0)

| Architecture | Feasible | Part 3D status | Qualification | Binding constraint | New-study CapEx | Known annual OPEX | Lifecycle cost | Cost rank | Pareto | Joint-op status |
|---|---|---|---|---|---|---|---|---|---|---|
| MANUAL_CONVENTIONAL | True | FEASIBLE_WITH_UNCALIBRATED_PRODUCTION_CAPACITY | QUALIFIED_WITH_LIMITATIONS | none | $125,000 | $1,750,320 | $11,869,790 | 1 | True | NOT_FULLY_VALIDATED |
| AUTOMATED_CONVENTIONAL | True | FEASIBLE_WITH_UNCALIBRATED_PRODUCTION_CAPACITY | QUALIFIED_WITH_LIMITATIONS | none | $1,925,000 | $1,870,772 | $14,478,032 | 2 | False | NOT_FULLY_VALIDATED |
| MRT_DOMINANT | True | FEASIBLE_WITH_UNCALIBRATED_PRODUCTION_CAPACITY | QUALIFIED_WITH_LIMITATIONS | none | $11,480,000 | $5,073,280 | $45,522,122 | 3 | False | NOT_FULLY_VALIDATED |
| HYBRID_MRT | True | FEASIBLE_WITH_UNCALIBRATED_PRODUCTION_CAPACITY | QUALIFIED_WITH_LIMITATIONS | none | $7,106,000 | $6,807,690 | $52,786,154 | 4 | False | NOT_FULLY_VALIDATED |

## TABLE 6 — F-18 Control Bouquet

| Architecture | Feasible | Part 3D status | Qualification | Binding constraint | New-study CapEx | Known annual OPEX | Lifecycle cost | Cost rank | Pareto | Joint-op status |
|---|---|---|---|---|---|---|---|---|---|---|
| MANUAL_CONVENTIONAL | True | FEASIBLE_WITH_UNCALIBRATED_PRODUCTION_CAPACITY | QUALIFIED_WITH_LIMITATIONS | none | $125,000 | $1,750,320 | $11,869,790 | 1 | True | SINGLE_RADIONUCLIDE_VALIDATED |
| AUTOMATED_CONVENTIONAL | True | FEASIBLE_WITH_UNCALIBRATED_PRODUCTION_CAPACITY | QUALIFIED_WITH_LIMITATIONS | none | $1,925,000 | $1,870,772 | $14,478,032 | 2 | False | SINGLE_RADIONUCLIDE_VALIDATED |
| MRT_DOMINANT | True | FEASIBLE_WITH_UNCALIBRATED_PRODUCTION_CAPACITY | QUALIFIED_WITH_LIMITATIONS | none | $11,480,000 | $5,073,280 | $45,522,122 | 3 | False | SINGLE_RADIONUCLIDE_VALIDATED |
| HYBRID_MRT | True | FEASIBLE_WITH_UNCALIBRATED_PRODUCTION_CAPACITY | QUALIFIED_WITH_LIMITATIONS | none | $7,106,000 | $6,807,690 | $52,786,154 | 4 | False | SINGLE_RADIONUCLIDE_VALIDATED |

Decay observations (F-18):

| Radionuclide | Half-life (min) | Mode | Transport (min) | Elapsed EOB→admin (min) | Retained frac | Admin activity (MBq) | Required upstream EOB (MBq) |
|---|---|---|---|---|---|---|---|
| F-18 | 109.80 | MANUAL | 3.908 | 38.91 | 0.78222 | 370.0 | 473.0 |
| F-18 | 109.80 | MRT | 1.972 | 36.97 | 0.79184 | 370.0 | 467.3 |

## TABLE 7 — C-11 Control Bouquet

| Architecture | Feasible | Part 3D status | Qualification | Binding constraint | New-study CapEx | Known annual OPEX | Lifecycle cost | Cost rank | Pareto | Joint-op status |
|---|---|---|---|---|---|---|---|---|---|---|
| MANUAL_CONVENTIONAL | True | FEASIBLE_WITH_UNCALIBRATED_PRODUCTION_CAPACITY | QUALIFIED_WITH_LIMITATIONS | none | $125,000 | $1,750,320 | $11,869,790 | 1 | True | SINGLE_RADIONUCLIDE_VALIDATED |
| AUTOMATED_CONVENTIONAL | True | FEASIBLE_WITH_UNCALIBRATED_PRODUCTION_CAPACITY | QUALIFIED_WITH_LIMITATIONS | none | $1,925,000 | $1,870,772 | $14,478,032 | 2 | False | SINGLE_RADIONUCLIDE_VALIDATED |
| MRT_DOMINANT | True | FEASIBLE_WITH_UNCALIBRATED_PRODUCTION_CAPACITY | QUALIFIED_WITH_LIMITATIONS | none | $11,480,000 | $5,073,280 | $45,522,122 | 3 | False | SINGLE_RADIONUCLIDE_VALIDATED |
| HYBRID_MRT | True | FEASIBLE_WITH_UNCALIBRATED_PRODUCTION_CAPACITY | QUALIFIED_WITH_LIMITATIONS | none | $7,106,000 | $6,807,690 | $52,786,154 | 4 | False | SINGLE_RADIONUCLIDE_VALIDATED |

Decay observations (C-11):

| Radionuclide | Half-life (min) | Mode | Transport (min) | Elapsed EOB→admin (min) | Retained frac | Admin activity (MBq) | Required upstream EOB (MBq) |
|---|---|---|---|---|---|---|---|
| C-11 | 20.30 | MANUAL | 3.908 | 38.91 | 0.26487 | 555.0 | 2095.4 |
| C-11 | 20.30 | MRT | 1.972 | 36.97 | 0.28297 | 555.0 | 1961.4 |

## TABLE 8 — N-13 Control Bouquet

| Architecture | Feasible | Part 3D status | Qualification | Binding constraint | New-study CapEx | Known annual OPEX | Lifecycle cost | Cost rank | Pareto | Joint-op status |
|---|---|---|---|---|---|---|---|---|---|---|
| MANUAL_CONVENTIONAL | True | FEASIBLE_WITH_UNCALIBRATED_PRODUCTION_CAPACITY | QUALIFIED_WITH_LIMITATIONS | none | $125,000 | $1,750,320 | $11,869,790 | 1 | True | SINGLE_RADIONUCLIDE_VALIDATED |
| AUTOMATED_CONVENTIONAL | True | FEASIBLE_WITH_UNCALIBRATED_PRODUCTION_CAPACITY | QUALIFIED_WITH_LIMITATIONS | none | $1,925,000 | $1,870,772 | $14,478,032 | 2 | False | SINGLE_RADIONUCLIDE_VALIDATED |
| MRT_DOMINANT | True | FEASIBLE_WITH_UNCALIBRATED_PRODUCTION_CAPACITY | QUALIFIED_WITH_LIMITATIONS | none | $11,480,000 | $5,073,280 | $45,522,122 | 3 | False | SINGLE_RADIONUCLIDE_VALIDATED |
| HYBRID_MRT | True | FEASIBLE_WITH_UNCALIBRATED_PRODUCTION_CAPACITY | QUALIFIED_WITH_LIMITATIONS | none | $7,106,000 | $6,807,690 | $52,786,154 | 4 | False | SINGLE_RADIONUCLIDE_VALIDATED |

Decay observations (N-13):

| Radionuclide | Half-life (min) | Mode | Transport (min) | Elapsed EOB→admin (min) | Retained frac | Admin activity (MBq) | Required upstream EOB (MBq) |
|---|---|---|---|---|---|---|---|
| N-13 | 9.97 | MANUAL | 3.908 | 38.91 | 0.06687 | 740.0 | 11066.6 |
| N-13 | 9.97 | MRT | 1.972 | 36.97 | 0.07650 | 740.0 | 9672.9 |

## TABLE 9 — O-15 Control Bouquet

| Architecture | Feasible | Part 3D status | Qualification | Binding constraint | New-study CapEx | Known annual OPEX | Lifecycle cost | Cost rank | Pareto | Joint-op status |
|---|---|---|---|---|---|---|---|---|---|---|
| MANUAL_CONVENTIONAL | True | FEASIBLE_WITH_UNCALIBRATED_PRODUCTION_CAPACITY | QUALIFIED_WITH_LIMITATIONS | none | $125,000 | $1,750,320 | $11,869,790 | 1 | True | SINGLE_RADIONUCLIDE_VALIDATED |
| AUTOMATED_CONVENTIONAL | True | FEASIBLE_WITH_UNCALIBRATED_PRODUCTION_CAPACITY | QUALIFIED_WITH_LIMITATIONS | none | $1,925,000 | $1,870,772 | $14,478,032 | 2 | False | SINGLE_RADIONUCLIDE_VALIDATED |
| MRT_DOMINANT | True | FEASIBLE_WITH_UNCALIBRATED_PRODUCTION_CAPACITY | QUALIFIED_WITH_LIMITATIONS | none | $11,480,000 | $5,073,280 | $45,522,122 | 3 | False | SINGLE_RADIONUCLIDE_VALIDATED |
| HYBRID_MRT | True | FEASIBLE_WITH_UNCALIBRATED_PRODUCTION_CAPACITY | QUALIFIED_WITH_LIMITATIONS | none | $7,106,000 | $6,807,690 | $52,786,154 | 4 | False | SINGLE_RADIONUCLIDE_VALIDATED |

Decay observations (O-15):

| Radionuclide | Half-life (min) | Mode | Transport (min) | Elapsed EOB→admin (min) | Retained frac | Admin activity (MBq) | Required upstream EOB (MBq) |
|---|---|---|---|---|---|---|---|
| O-15 | 2.04 | MANUAL | 3.908 | 38.91 | 0.00000 | 1110.0 | 6.120e+08 |
| O-15 | 2.04 | MRT | 1.972 | 36.97 | 0.00000 | 1110.0 | 3.170e+08 |

## TABLE 10 — Short-Half-Life Comparative Physics (Experiment 5)

| Radionuclide | Half-life (min) | Mode | Transport (min) | Elapsed EOB→admin (min) | Retained frac | Admin activity (MBq) | Required upstream EOB (MBq) |
|---|---|---|---|---|---|---|---|
| F-18 | 109.80 | MANUAL | 3.908 | 38.91 | 0.78222 | 370.0 | 473.0 |
| F-18 | 109.80 | MRT | 1.972 | 36.97 | 0.79184 | 370.0 | 467.3 |
| C-11 | 20.30 | MANUAL | 3.908 | 38.91 | 0.26487 | 555.0 | 2095.4 |
| C-11 | 20.30 | MRT | 1.972 | 36.97 | 0.28297 | 555.0 | 1961.4 |
| N-13 | 9.97 | MANUAL | 3.908 | 38.91 | 0.06687 | 740.0 | 11066.6 |
| N-13 | 9.97 | MRT | 1.972 | 36.97 | 0.07650 | 740.0 | 9672.9 |
| O-15 | 2.04 | MANUAL | 3.908 | 38.91 | 0.00000 | 1110.0 | 6.120e+08 |
| O-15 | 2.04 | MRT | 1.972 | 36.97 | 0.00000 | 1110.0 | 3.170e+08 |

*Held constant: benchmark worst-case route (95 m, 32 m vertical, 2 transitions),
controlled EOB→release=30 min and admin-after-arrival=5 min. As half-life
shortens, retained fraction collapses and required upstream EOB activity
explodes — OBSERVED, never rewarded. MRT's shorter route retains more than
manual for every radionuclide.*

## TABLE 11 — Distance Sensitivity: F-18 (Experiment 6)

| Multiplier | Distance (m) | Vertical (m) | Transitions | Manual transport (min) | MRT transport (min) | R (manual) | R (MRT) | Req upstream EOB manual (MBq) | Req upstream EOB MRT (MBq) |
|---|---|---|---|---|---|---|---|---|---|
| x0.5 | 47.5 | 16.0 | 2 | 3.204 | 1.619 | 0.78570 | 0.79360 | 470.9 | 466.2 |
| x1.0 | 95.0 | 32.0 | 2 | 3.908 | 1.972 | 0.78222 | 0.79184 | 473.0 | 467.3 |
| x1.5 | 142.5 | 48.0 | 2 | 4.612 | 2.325 | 0.77875 | 0.79008 | 475.1 | 468.3 |
| x2.0 | 190.0 | 64.0 | 2 | 5.317 | 2.678 | 0.77529 | 0.78832 | 477.2 | 469.4 |
| x3.0 | 285.0 | 96.0 | 2 | 6.725 | 3.383 | 0.76843 | 0.78482 | 481.5 | 471.4 |

## TABLE 12 — Distance Sensitivity: C-11 (Experiment 6)

| Multiplier | Distance (m) | Vertical (m) | Transitions | Manual transport (min) | MRT transport (min) | R (manual) | R (MRT) | Req upstream EOB manual (MBq) | Req upstream EOB MRT (MBq) |
|---|---|---|---|---|---|---|---|---|---|
| x0.5 | 47.5 | 16.0 | 2 | 3.204 | 1.619 | 0.27131 | 0.28640 | 2045.6 | 1937.9 |
| x1.0 | 95.0 | 32.0 | 2 | 3.908 | 1.972 | 0.26487 | 0.28297 | 2095.4 | 1961.4 |
| x1.5 | 142.5 | 48.0 | 2 | 4.612 | 2.325 | 0.25857 | 0.27958 | 2146.4 | 1985.1 |
| x2.0 | 190.0 | 64.0 | 2 | 5.317 | 2.678 | 0.25243 | 0.27623 | 2198.6 | 2009.2 |
| x3.0 | 285.0 | 96.0 | 2 | 6.725 | 3.383 | 0.24058 | 0.26966 | 2306.9 | 2058.2 |

## TABLE 13 — Distance Sensitivity: N-13 (Experiment 6)

| Multiplier | Distance (m) | Vertical (m) | Transitions | Manual transport (min) | MRT transport (min) | R (manual) | R (MRT) | Req upstream EOB manual (MBq) | Req upstream EOB MRT (MBq) |
|---|---|---|---|---|---|---|---|---|---|
| x0.5 | 47.5 | 16.0 | 2 | 3.204 | 1.619 | 0.07022 | 0.07840 | 10537.9 | 9438.5 |
| x1.0 | 95.0 | 32.0 | 2 | 3.908 | 1.972 | 0.06687 | 0.07650 | 11066.6 | 9672.9 |
| x1.5 | 142.5 | 48.0 | 2 | 4.612 | 2.325 | 0.06367 | 0.07465 | 11621.8 | 9913.0 |
| x2.0 | 190.0 | 64.0 | 2 | 5.317 | 2.678 | 0.06063 | 0.07284 | 12205.0 | 10159.2 |
| x3.0 | 285.0 | 96.0 | 2 | 6.725 | 3.383 | 0.05498 | 0.06935 | 13460.4 | 10669.9 |

## TABLE 14 — Distance Sensitivity: O-15 (Experiment 6)

| Multiplier | Distance (m) | Vertical (m) | Transitions | Manual transport (min) | MRT transport (min) | R (manual) | R (MRT) | Req upstream EOB manual (MBq) | Req upstream EOB MRT (MBq) |
|---|---|---|---|---|---|---|---|---|---|
| x0.5 | 47.5 | 16.0 | 2 | 3.204 | 1.619 | 0.00000 | 0.00000 | 4.818e+08 | 2.812e+08 |
| x1.0 | 95.0 | 32.0 | 2 | 3.908 | 1.972 | 0.00000 | 0.00000 | 6.120e+08 | 3.170e+08 |
| x1.5 | 142.5 | 48.0 | 2 | 4.612 | 2.325 | 0.00000 | 0.00000 | 7.775e+08 | 3.574e+08 |
| x2.0 | 190.0 | 64.0 | 2 | 5.317 | 2.678 | 0.00000 | 0.00000 | 9.876e+08 | 4.029e+08 |
| x3.0 | 285.0 | 96.0 | 2 | 6.725 | 3.383 | 0.00000 | 0.00000 | 1.594e+09 | 5.120e+08 |

*1.0× is the REAL benchmark worst-case release-origin→room route; multipliers
are CONTROLLED_EXPERIMENTAL_ASSUMPTIONs. Transport time recomputed via the real
spatial transport-time authority; decay via the real decay authority (single
interval, no double-count).*

## TABLE 15 — MRT Speed Sensitivity (Experiment 7)

| Radionuclide | Speed label | H speed (m/s) | V speed (m/s) | Basis | MRT transport (min) | Retained frac |
|---|---|---|---|---|---|---|
| F-18 | SLOW | 1.5 | 0.75 | CONTROLLED_EXPERIMENTAL_ASSUMPTION | 2.678 | 0.78832 |
| F-18 | BASELINE | 3.0 | 1.5 | CONTROLLED_ENGINEERING_ASSUMPTION | 1.972 | 0.79184 |
| F-18 | FAST | 6.0 | 3.0 | CONTROLLED_EXPERIMENTAL_ASSUMPTION | 1.619 | 0.79360 |
| F-18 | VERY_FAST | 9.0 | 4.5 | CONTROLLED_EXPERIMENTAL_ASSUMPTION | 1.502 | 0.79419 |
| C-11 | SLOW | 1.5 | 0.75 | CONTROLLED_EXPERIMENTAL_ASSUMPTION | 2.678 | 0.27623 |
| C-11 | BASELINE | 3.0 | 1.5 | CONTROLLED_ENGINEERING_ASSUMPTION | 1.972 | 0.28297 |
| C-11 | FAST | 6.0 | 3.0 | CONTROLLED_EXPERIMENTAL_ASSUMPTION | 1.619 | 0.28640 |
| C-11 | VERY_FAST | 9.0 | 4.5 | CONTROLLED_EXPERIMENTAL_ASSUMPTION | 1.502 | 0.28755 |
| N-13 | SLOW | 1.5 | 0.75 | CONTROLLED_EXPERIMENTAL_ASSUMPTION | 2.678 | 0.07284 |
| N-13 | BASELINE | 3.0 | 1.5 | CONTROLLED_ENGINEERING_ASSUMPTION | 1.972 | 0.07650 |
| N-13 | FAST | 6.0 | 3.0 | CONTROLLED_EXPERIMENTAL_ASSUMPTION | 1.619 | 0.07840 |
| N-13 | VERY_FAST | 9.0 | 4.5 | CONTROLLED_EXPERIMENTAL_ASSUMPTION | 1.502 | 0.07905 |
| O-15 | SLOW | 1.5 | 0.75 | CONTROLLED_EXPERIMENTAL_ASSUMPTION | 2.678 | 0.00000 |
| O-15 | BASELINE | 3.0 | 1.5 | CONTROLLED_ENGINEERING_ASSUMPTION | 1.972 | 0.00000 |
| O-15 | FAST | 6.0 | 3.0 | CONTROLLED_EXPERIMENTAL_ASSUMPTION | 1.619 | 0.00000 |
| O-15 | VERY_FAST | 9.0 | 4.5 | CONTROLLED_EXPERIMENTAL_ASSUMPTION | 1.502 | 0.00000 |

*Faster carrier → shorter route time → higher retention for C-11/N-13/F-18,
but O-15 stays clinically negligible at every speed: faster is NOT automatically
better. BASELINE is the canonical PlannerAssumptions speed; others are
CONTROLLED_EXPERIMENTAL_ASSUMPTIONs.*

## TABLE 16 — Cyclotron Source Sensitivity (Experiment 8)

| Radionuclide | Source kind | Catalog model id | Manufacturer | Declares support | Schedulable | Calibrated EOB record | Production calibration status |
|---|---|---|---|---|---|---|---|
| C-11 | CYCLOTRON | IBA_CYCLONE_KIUBE | IBA | True | False | False | not_calibrated |
| C-11 | CYCLOTRON | GE_PETTRACE_800 | GE HealthCare | True | True | False | modeled |
| C-11 | CYCLOTRON | SIEMENS_CTI_ECLIPSE_HP | Siemens/CTI | True | False | False | not_calibrated |
| C-11 | CYCLOTRON | ACSI_TR_19 | ACSI | True | False | False | not_calibrated |
| N-13 | CYCLOTRON | IBA_CYCLONE_KIUBE | IBA | True | False | False | not_calibrated |
| N-13 | CYCLOTRON | GE_PETTRACE_800 | GE HealthCare | True | True | False | modeled |
| N-13 | CYCLOTRON | SIEMENS_CTI_RDS_111 | Siemens/CTI | True | False | False | not_calibrated |
| N-13 | CYCLOTRON | ACSI_TR_19 | ACSI | True | False | False | not_calibrated |
| O-15 | CYCLOTRON | IBA_CYCLONE_KIUBE | IBA | True | False | False | not_calibrated |
| O-15 | CYCLOTRON | GE_PETTRACE_800 | GE HealthCare | True | True | False | modeled |
| O-15 | CYCLOTRON | SIEMENS_CTI_ECLIPSE_HP | Siemens/CTI | True | False | False | not_calibrated |
| O-15 | CYCLOTRON | ACSI_TR_19 | ACSI | True | False | False | not_calibrated |

*For the SAME radionuclide, calibration status differs by MODEL — the
production verdict is equipment-driven, not radionuclide-driven. Output is
never borrowed between models.*

## TABLE 17 — Ga-68 Cyclotron vs Generator (Experiment 9)

### Cyclotron arm (SUMITOMO_CYPRIS_MP_30)

| Architecture | Feasible | Part 3D status | Qualification | Binding constraint | New-study CapEx | Known annual OPEX | Lifecycle cost | Cost rank | Pareto | Joint-op status |
|---|---|---|---|---|---|---|---|---|---|---|
| MANUAL_CONVENTIONAL | True | FEASIBLE_WITH_UNCALIBRATED_PRODUCTION_CAPACITY | QUALIFIED_WITH_LIMITATIONS | none | $125,000 | $1,750,320 | $11,869,790 | 1 | True | SINGLE_RADIONUCLIDE_VALIDATED |
| AUTOMATED_CONVENTIONAL | True | FEASIBLE_WITH_UNCALIBRATED_PRODUCTION_CAPACITY | QUALIFIED_WITH_LIMITATIONS | none | $1,925,000 | $1,870,772 | $14,478,032 | 2 | False | SINGLE_RADIONUCLIDE_VALIDATED |
| MRT_DOMINANT | True | FEASIBLE_WITH_UNCALIBRATED_PRODUCTION_CAPACITY | QUALIFIED_WITH_LIMITATIONS | none | $11,480,000 | $5,073,280 | $45,522,122 | 3 | False | SINGLE_RADIONUCLIDE_VALIDATED |
| HYBRID_MRT | True | FEASIBLE_WITH_UNCALIBRATED_PRODUCTION_CAPACITY | QUALIFIED_WITH_LIMITATIONS | none | $7,106,000 | $6,807,690 | $52,786,154 | 4 | False | SINGLE_RADIONUCLIDE_VALIDATED |

### Generator arm (ECKERT_ZIEGLER_GALLIAPHARM, Ge-68→Ga-68)

| Architecture | Feasible | Part 3D status | Qualification | Binding constraint | New-study CapEx | Known annual OPEX | Lifecycle cost | Cost rank | Pareto | Joint-op status |
|---|---|---|---|---|---|---|---|---|---|---|
| MANUAL_CONVENTIONAL | True | FEASIBLE_WITH_UNCALIBRATED_PRODUCTION_CAPACITY | QUALIFIED_WITH_LIMITATIONS | none | $125,000 | $1,750,320 | $11,869,790 | 1 | True | SINGLE_RADIONUCLIDE_VALIDATED |
| AUTOMATED_CONVENTIONAL | True | FEASIBLE_WITH_UNCALIBRATED_PRODUCTION_CAPACITY | QUALIFIED_WITH_LIMITATIONS | none | $1,925,000 | $1,870,772 | $14,478,032 | 2 | False | SINGLE_RADIONUCLIDE_VALIDATED |
| MRT_DOMINANT | True | FEASIBLE_WITH_UNCALIBRATED_PRODUCTION_CAPACITY | QUALIFIED_WITH_LIMITATIONS | none | $11,480,000 | $5,073,280 | $45,522,122 | 3 | False | SINGLE_RADIONUCLIDE_VALIDATED |
| HYBRID_MRT | True | FEASIBLE_WITH_UNCALIBRATED_PRODUCTION_CAPACITY | QUALIFIED_WITH_LIMITATIONS | none | $7,106,000 | $6,807,690 | $52,786,154 | 4 | False | SINGLE_RADIONUCLIDE_VALIDATED |

| Radionuclide | Source kind | Catalog model id | Manufacturer | Declares support | Schedulable | Calibrated EOB record | Production calibration status |
|---|---|---|---|---|---|---|---|
| Ga-68 | CYCLOTRON | SUMITOMO_CYPRIS_MP_30 | Sumitomo Heavy Industries | True | False | False | not_calibrated |
| Ga-68 | GENERATOR | ECKERT_ZIEGLER_GALLIAPHARM | Eckert & Ziegler | True | False | False | not_calibrated |

## TABLE 18 — Patient-Demand Sensitivity (Experiment 10)

| Radionuclide | Demand level | Patient count | Admin activity (MBq) | Total prescribed (MBq) | Required scanners | Production gate | Stream status |
|---|---|---|---|---|---|---|---|
| F-18 | LOW | 8 | 370.0 | 2960.0 | 1 | PRODUCTION_SUFFICIENT | RESOLVED_ADMISSIBLE |
| F-18 | BASELINE | 32 | 370.0 | 11840.0 | 2 | PRODUCTION_SUFFICIENT | RESOLVED_ADMISSIBLE |
| F-18 | HIGH | 64 | 370.0 | 23680.0 | 4 | PRODUCTION_SUFFICIENT | RESOLVED_ADMISSIBLE |
| C-11 | LOW | 2 | 555.0 | 1110.0 | 1 | PRODUCTION_NOT_CALIBRATED | RESOLVED_WITH_UNCALIBRATED_PRODUCTION |
| C-11 | BASELINE | 6 | 555.0 | 3330.0 | 1 | PRODUCTION_NOT_CALIBRATED | RESOLVED_WITH_UNCALIBRATED_PRODUCTION |
| C-11 | HIGH | 12 | 555.0 | 6660.0 | 1 | PRODUCTION_NOT_CALIBRATED | RESOLVED_WITH_UNCALIBRATED_PRODUCTION |
| N-13 | LOW | 2 | 740.0 | 1480.0 | 1 | PRODUCTION_NOT_CALIBRATED | RESOLVED_WITH_UNCALIBRATED_PRODUCTION |
| N-13 | BASELINE | 6 | 740.0 | 4440.0 | 1 | PRODUCTION_NOT_CALIBRATED | RESOLVED_WITH_UNCALIBRATED_PRODUCTION |
| N-13 | HIGH | 12 | 740.0 | 8880.0 | 1 | PRODUCTION_NOT_CALIBRATED | RESOLVED_WITH_UNCALIBRATED_PRODUCTION |
| O-15 | LOW | 2 | 1110.0 | 2220.0 | 1 | PRODUCTION_NOT_CALIBRATED | RESOLVED_WITH_UNCALIBRATED_PRODUCTION |
| O-15 | BASELINE | 6 | 1110.0 | 6660.0 | 1 | PRODUCTION_NOT_CALIBRATED | RESOLVED_WITH_UNCALIBRATED_PRODUCTION |
| O-15 | HIGH | 12 | 1110.0 | 13320.0 | 1 | PRODUCTION_NOT_CALIBRATED | RESOLVED_WITH_UNCALIBRATED_PRODUCTION |
| Ga-68 | LOW | 3 | 185.0 | 555.0 | 1 | PRODUCTION_NOT_CALIBRATED | RESOLVED_WITH_UNCALIBRATED_PRODUCTION |
| Ga-68 | BASELINE | 10 | 185.0 | 1850.0 | 1 | PRODUCTION_NOT_CALIBRATED | RESOLVED_WITH_UNCALIBRATED_PRODUCTION |
| Ga-68 | HIGH | 20 | 185.0 | 3700.0 | 1 | PRODUCTION_NOT_CALIBRATED | RESOLVED_WITH_UNCALIBRATED_PRODUCTION |

*Explicit counts (no prevalence invented). Scanner requirement scales with
demand; production gate preserves PRODUCTION_SUFFICIENT (calibrated F-18) vs
PRODUCTION_NOT_CALIBRATED (O-15/Ga-68) — never zero-filled.*

## TABLE 19 — Mixed PET Scenario (Experiment 11)

| Architecture | Feasible | Part 3D status | Qualification | Binding constraint | New-study CapEx | Known annual OPEX | Lifecycle cost | Cost rank | Pareto | Joint-op status |
|---|---|---|---|---|---|---|---|---|---|---|
| MANUAL_CONVENTIONAL | True | FEASIBLE_WITH_UNCALIBRATED_PRODUCTION_CAPACITY | QUALIFIED_WITH_LIMITATIONS | none | $125,000 | $1,750,320 | $11,869,790 | 1 | True | NOT_FULLY_VALIDATED |
| AUTOMATED_CONVENTIONAL | True | FEASIBLE_WITH_UNCALIBRATED_PRODUCTION_CAPACITY | QUALIFIED_WITH_LIMITATIONS | none | $1,925,000 | $1,870,772 | $14,478,032 | 2 | False | NOT_FULLY_VALIDATED |
| MRT_DOMINANT | True | FEASIBLE_WITH_UNCALIBRATED_PRODUCTION_CAPACITY | QUALIFIED_WITH_LIMITATIONS | none | $11,480,000 | $5,073,280 | $45,522,122 | 3 | False | NOT_FULLY_VALIDATED |
| HYBRID_MRT | True | FEASIBLE_WITH_UNCALIBRATED_PRODUCTION_CAPACITY | QUALIFIED_WITH_LIMITATIONS | none | $7,106,000 | $6,807,690 | $52,786,154 | 4 | False | NOT_FULLY_VALIDATED |

PET patients=35, SPECT patients=0, required PET scanners=4, required SPECT scanners=0.

Scheduling disclosure: TRUE_JOINT_MULTI_RADIONUCLIDE_SCHEDULING=NO, MULTI_RADIONUCLIDE_PHASE1_AGGREGATION=YES, JOINT_OPERATIONAL_FEASIBILITY_STATUS=NOT_FULLY_VALIDATED.

## TABLE 20 — Mixed PET + SPECT Scenario (Experiment 12)

| Architecture | Feasible | Part 3D status | Qualification | Binding constraint | New-study CapEx | Known annual OPEX | Lifecycle cost | Cost rank | Pareto | Joint-op status |
|---|---|---|---|---|---|---|---|---|---|---|
| MANUAL_CONVENTIONAL | True | FEASIBLE_WITH_UNCALIBRATED_PRODUCTION_CAPACITY | QUALIFIED_WITH_LIMITATIONS | none | $125,000 | $1,750,320 | $11,869,790 | 1 | True | NOT_FULLY_VALIDATED |
| AUTOMATED_CONVENTIONAL | True | FEASIBLE_WITH_UNCALIBRATED_PRODUCTION_CAPACITY | QUALIFIED_WITH_LIMITATIONS | none | $1,925,000 | $1,870,772 | $14,478,032 | 2 | False | NOT_FULLY_VALIDATED |
| MRT_DOMINANT | True | FEASIBLE_WITH_UNCALIBRATED_PRODUCTION_CAPACITY | QUALIFIED_WITH_LIMITATIONS | none | $11,480,000 | $5,073,280 | $45,522,122 | 3 | False | NOT_FULLY_VALIDATED |
| HYBRID_MRT | True | FEASIBLE_WITH_UNCALIBRATED_PRODUCTION_CAPACITY | QUALIFIED_WITH_LIMITATIONS | none | $7,106,000 | $6,807,690 | $52,786,154 | 4 | False | NOT_FULLY_VALIDATED |

PET patients=30, SPECT patients=16, required PET scanners=3, required SPECT scanners=1 (distinct pools; total=4).

## TABLE 21 — Architecture Bouquet by Experiment (feasibility)

| Experiment | MANUAL CONVENTIONAL | AUTOMATED CONVENTIONAL | MRT DOMINANT | HYBRID MRT |
|---|---|---|---|---|
| EXP0 | True | True | True | True |
| EXP1 | True | True | True | True |
| EXP2 | True | True | True | True |
| EXP3 | True | True | True | True |
| EXP4 | True | True | True | True |
| EXP6_F18 | True | True | True | True |
| EXP6_C11 | True | True | True | True |
| EXP6_N13 | True | True | True | True |
| EXP6_O15 | True | True | True | True |
| EXP9A | True | True | True | True |
| EXP9B | True | True | True | True |
| EXP11 | True | True | True | True |
| EXP12 | True | True | True | True |

## TABLE 22 — Architecture Ranking by Experiment (cost-only)

| Experiment | Ranked order (cheapest → dearest) |
|---|---|
| EXP0 | MANUAL_CONVENTIONAL < AUTOMATED_CONVENTIONAL < MRT_DOMINANT < HYBRID_MRT |
| EXP1 | MANUAL_CONVENTIONAL < AUTOMATED_CONVENTIONAL < MRT_DOMINANT < HYBRID_MRT |
| EXP2 | MANUAL_CONVENTIONAL < AUTOMATED_CONVENTIONAL < MRT_DOMINANT < HYBRID_MRT |
| EXP3 | MANUAL_CONVENTIONAL < AUTOMATED_CONVENTIONAL < MRT_DOMINANT < HYBRID_MRT |
| EXP4 | MANUAL_CONVENTIONAL < AUTOMATED_CONVENTIONAL < MRT_DOMINANT < HYBRID_MRT |
| EXP6_F18 | MANUAL_CONVENTIONAL < AUTOMATED_CONVENTIONAL < MRT_DOMINANT < HYBRID_MRT |
| EXP6_C11 | MANUAL_CONVENTIONAL < AUTOMATED_CONVENTIONAL < MRT_DOMINANT < HYBRID_MRT |
| EXP6_N13 | MANUAL_CONVENTIONAL < AUTOMATED_CONVENTIONAL < MRT_DOMINANT < HYBRID_MRT |
| EXP6_O15 | MANUAL_CONVENTIONAL < AUTOMATED_CONVENTIONAL < MRT_DOMINANT < HYBRID_MRT |
| EXP9A | MANUAL_CONVENTIONAL < AUTOMATED_CONVENTIONAL < MRT_DOMINANT < HYBRID_MRT |
| EXP9B | MANUAL_CONVENTIONAL < AUTOMATED_CONVENTIONAL < MRT_DOMINANT < HYBRID_MRT |
| EXP11 | MANUAL_CONVENTIONAL < AUTOMATED_CONVENTIONAL < MRT_DOMINANT < HYBRID_MRT |
| EXP12 | MANUAL_CONVENTIONAL < AUTOMATED_CONVENTIONAL < MRT_DOMINANT < HYBRID_MRT |

## TABLE 23 — Pareto Membership by Experiment

| Experiment | Pareto front |
|---|---|
| EXP0 | MANUAL_CONVENTIONAL |
| EXP1 | MANUAL_CONVENTIONAL |
| EXP2 | MANUAL_CONVENTIONAL |
| EXP3 | MANUAL_CONVENTIONAL |
| EXP4 | MANUAL_CONVENTIONAL |
| EXP6_F18 | MANUAL_CONVENTIONAL |
| EXP6_C11 | MANUAL_CONVENTIONAL |
| EXP6_N13 | MANUAL_CONVENTIONAL |
| EXP6_O15 | MANUAL_CONVENTIONAL |
| EXP9A | MANUAL_CONVENTIONAL |
| EXP9B | MANUAL_CONVENTIONAL |
| EXP11 | MANUAL_CONVENTIONAL |
| EXP12 | MANUAL_CONVENTIONAL |

## TABLE 24 — Physical Feasibility by Experiment (Part 3D status)

| Experiment | MANUAL CONVENTIONAL | AUTOMATED CONVENTIONAL | MRT DOMINANT | HYBRID MRT |
|---|---|---|---|---|
| EXP0 | FEASIBLE_WITH_UNCALIBRATED_PRODUCTION_CAPACITY | FEASIBLE_WITH_UNCALIBRATED_PRODUCTION_CAPACITY | FEASIBLE_WITH_UNCALIBRATED_PRODUCTION_CAPACITY | FEASIBLE_WITH_UNCALIBRATED_PRODUCTION_CAPACITY |
| EXP1 | FEASIBLE_WITH_UNCALIBRATED_PRODUCTION_CAPACITY | FEASIBLE_WITH_UNCALIBRATED_PRODUCTION_CAPACITY | FEASIBLE_WITH_UNCALIBRATED_PRODUCTION_CAPACITY | FEASIBLE_WITH_UNCALIBRATED_PRODUCTION_CAPACITY |
| EXP2 | FEASIBLE_WITH_UNCALIBRATED_PRODUCTION_CAPACITY | FEASIBLE_WITH_UNCALIBRATED_PRODUCTION_CAPACITY | FEASIBLE_WITH_UNCALIBRATED_PRODUCTION_CAPACITY | FEASIBLE_WITH_UNCALIBRATED_PRODUCTION_CAPACITY |
| EXP3 | FEASIBLE_WITH_UNCALIBRATED_PRODUCTION_CAPACITY | FEASIBLE_WITH_UNCALIBRATED_PRODUCTION_CAPACITY | FEASIBLE_WITH_UNCALIBRATED_PRODUCTION_CAPACITY | FEASIBLE_WITH_UNCALIBRATED_PRODUCTION_CAPACITY |
| EXP4 | FEASIBLE_WITH_UNCALIBRATED_PRODUCTION_CAPACITY | FEASIBLE_WITH_UNCALIBRATED_PRODUCTION_CAPACITY | FEASIBLE_WITH_UNCALIBRATED_PRODUCTION_CAPACITY | FEASIBLE_WITH_UNCALIBRATED_PRODUCTION_CAPACITY |
| EXP6_F18 | FEASIBLE_WITH_UNCALIBRATED_PRODUCTION_CAPACITY | FEASIBLE_WITH_UNCALIBRATED_PRODUCTION_CAPACITY | FEASIBLE_WITH_UNCALIBRATED_PRODUCTION_CAPACITY | FEASIBLE_WITH_UNCALIBRATED_PRODUCTION_CAPACITY |
| EXP6_C11 | FEASIBLE_WITH_UNCALIBRATED_PRODUCTION_CAPACITY | FEASIBLE_WITH_UNCALIBRATED_PRODUCTION_CAPACITY | FEASIBLE_WITH_UNCALIBRATED_PRODUCTION_CAPACITY | FEASIBLE_WITH_UNCALIBRATED_PRODUCTION_CAPACITY |
| EXP6_N13 | FEASIBLE_WITH_UNCALIBRATED_PRODUCTION_CAPACITY | FEASIBLE_WITH_UNCALIBRATED_PRODUCTION_CAPACITY | FEASIBLE_WITH_UNCALIBRATED_PRODUCTION_CAPACITY | FEASIBLE_WITH_UNCALIBRATED_PRODUCTION_CAPACITY |
| EXP6_O15 | FEASIBLE_WITH_UNCALIBRATED_PRODUCTION_CAPACITY | FEASIBLE_WITH_UNCALIBRATED_PRODUCTION_CAPACITY | FEASIBLE_WITH_UNCALIBRATED_PRODUCTION_CAPACITY | FEASIBLE_WITH_UNCALIBRATED_PRODUCTION_CAPACITY |
| EXP9A | FEASIBLE_WITH_UNCALIBRATED_PRODUCTION_CAPACITY | FEASIBLE_WITH_UNCALIBRATED_PRODUCTION_CAPACITY | FEASIBLE_WITH_UNCALIBRATED_PRODUCTION_CAPACITY | FEASIBLE_WITH_UNCALIBRATED_PRODUCTION_CAPACITY |
| EXP9B | FEASIBLE_WITH_UNCALIBRATED_PRODUCTION_CAPACITY | FEASIBLE_WITH_UNCALIBRATED_PRODUCTION_CAPACITY | FEASIBLE_WITH_UNCALIBRATED_PRODUCTION_CAPACITY | FEASIBLE_WITH_UNCALIBRATED_PRODUCTION_CAPACITY |
| EXP11 | FEASIBLE_WITH_UNCALIBRATED_PRODUCTION_CAPACITY | FEASIBLE_WITH_UNCALIBRATED_PRODUCTION_CAPACITY | FEASIBLE_WITH_UNCALIBRATED_PRODUCTION_CAPACITY | FEASIBLE_WITH_UNCALIBRATED_PRODUCTION_CAPACITY |
| EXP12 | FEASIBLE_WITH_UNCALIBRATED_PRODUCTION_CAPACITY | FEASIBLE_WITH_UNCALIBRATED_PRODUCTION_CAPACITY | FEASIBLE_WITH_UNCALIBRATED_PRODUCTION_CAPACITY | FEASIBLE_WITH_UNCALIBRATED_PRODUCTION_CAPACITY |

## TABLE 25 — Known CapEx Comparison (baseline basis)

| Architecture | New-study CapEx | Total comparable project CapEx |
|---|---|---|
| MANUAL_CONVENTIONAL | $125,000 | $125,000 |
| AUTOMATED_CONVENTIONAL | $1,925,000 | $1,925,000 |
| MRT_DOMINANT | $11,480,000 | $11,480,000 |
| HYBRID_MRT | $7,106,000 | $7,106,000 |

## TABLE 26 — Known OPEX Subtotal Comparison (baseline basis)

| Architecture | Known annual OPEX | True total annual OPEX |
|---|---|---|
| MANUAL_CONVENTIONAL | $1,750,320 | $6,771,800 |
| AUTOMATED_CONVENTIONAL | $1,870,772 | $6,892,252 |
| MRT_DOMINANT | $5,073,280 | $5,073,280 |
| HYBRID_MRT | $6,807,690 | $6,807,690 |

## TABLE 27 — Total OPEX Calibration Status

| Architecture | Total OPEX calibration status |
|---|---|
| MANUAL_CONVENTIONAL | KNOWN_SUBTOTAL_ONLY_TOTAL_NOT_CALIBRATED |
| AUTOMATED_CONVENTIONAL | KNOWN_SUBTOTAL_ONLY_TOTAL_NOT_CALIBRATED |
| MRT_DOMINANT | KNOWN_SUBTOTAL_ONLY_TOTAL_NOT_CALIBRATED |
| HYBRID_MRT | KNOWN_SUBTOTAL_ONLY_TOTAL_NOT_CALIBRATED |

*Every architecture's total OPEX is a KNOWN SUBTOTAL only; service/
procurement/energy remain NOT_CALIBRATED (never zero-filled). Ranking is
cost-only over the derived lifecycle cost and relies on the known subtotal.*

## TABLE 28 — Decay / Retained-Activity Comparison (worst-case route)

| Radionuclide | Half-life (min) | Mode | Transport (min) | Elapsed EOB→admin (min) | Retained frac | Admin activity (MBq) | Required upstream EOB (MBq) |
|---|---|---|---|---|---|---|---|
| F-18 | 109.80 | MANUAL | 3.908 | 38.91 | 0.78222 | 370.0 | 473.0 |
| F-18 | 109.80 | MRT | 1.972 | 36.97 | 0.79184 | 370.0 | 467.3 |
| C-11 | 20.30 | MANUAL | 3.908 | 38.91 | 0.26487 | 555.0 | 2095.4 |
| C-11 | 20.30 | MRT | 1.972 | 36.97 | 0.28297 | 555.0 | 1961.4 |
| N-13 | 9.97 | MANUAL | 3.908 | 38.91 | 0.06687 | 740.0 | 11066.6 |
| N-13 | 9.97 | MRT | 1.972 | 36.97 | 0.07650 | 740.0 | 9672.9 |
| O-15 | 2.04 | MANUAL | 3.908 | 38.91 | 0.00000 | 1110.0 | 6.120e+08 |
| O-15 | 2.04 | MRT | 1.972 | 36.97 | 0.00000 | 1110.0 | 3.170e+08 |

## TABLE 29 — Required Upstream Activity Comparison

| Radionuclide | Mode | Retained frac | Admin activity (MBq) | Required upstream EOB (MBq) |
|---|---|---|---|---|
| F-18 | MANUAL | 0.78222 | 370.0 | 473.0 |
| F-18 | MRT | 0.79184 | 370.0 | 467.3 |
| C-11 | MANUAL | 0.26487 | 555.0 | 2095.4 |
| C-11 | MRT | 0.28297 | 555.0 | 1961.4 |
| N-13 | MANUAL | 0.06687 | 740.0 | 11066.6 |
| N-13 | MRT | 0.07650 | 740.0 | 9672.9 |
| O-15 | MANUAL | 0.00000 | 1110.0 | 6.120e+08 |
| O-15 | MRT | 0.00000 | 1110.0 | 3.170e+08 |

## TABLE 30 — Scanner Requirement Comparison (demand sensitivity)

| Radionuclide | Demand level | Patient count | Modality | Required scanners |
|---|---|---|---|---|
| F-18 | LOW | 8 | PET | 1 |
| F-18 | BASELINE | 32 | PET | 2 |
| F-18 | HIGH | 64 | PET | 4 |
| C-11 | LOW | 2 | PET | 1 |
| C-11 | BASELINE | 6 | PET | 1 |
| C-11 | HIGH | 12 | PET | 1 |
| N-13 | LOW | 2 | PET | 1 |
| N-13 | BASELINE | 6 | PET | 1 |
| N-13 | HIGH | 12 | PET | 1 |
| O-15 | LOW | 2 | PET | 1 |
| O-15 | BASELINE | 6 | PET | 1 |
| O-15 | HIGH | 12 | PET | 1 |
| Ga-68 | LOW | 3 | PET | 1 |
| Ga-68 | BASELINE | 10 | PET | 1 |
| Ga-68 | HIGH | 20 | PET | 1 |

## TABLE 31 — Production Requirement Comparison (per radionuclide)

| Radionuclide | Demand level | Total prescribed (MBq) | Production gate | Stream status |
|---|---|---|---|---|
| F-18 | LOW | 2960.0 | PRODUCTION_SUFFICIENT | RESOLVED_ADMISSIBLE |
| F-18 | BASELINE | 11840.0 | PRODUCTION_SUFFICIENT | RESOLVED_ADMISSIBLE |
| F-18 | HIGH | 23680.0 | PRODUCTION_SUFFICIENT | RESOLVED_ADMISSIBLE |
| C-11 | LOW | 1110.0 | PRODUCTION_NOT_CALIBRATED | RESOLVED_WITH_UNCALIBRATED_PRODUCTION |
| C-11 | BASELINE | 3330.0 | PRODUCTION_NOT_CALIBRATED | RESOLVED_WITH_UNCALIBRATED_PRODUCTION |
| C-11 | HIGH | 6660.0 | PRODUCTION_NOT_CALIBRATED | RESOLVED_WITH_UNCALIBRATED_PRODUCTION |
| N-13 | LOW | 1480.0 | PRODUCTION_NOT_CALIBRATED | RESOLVED_WITH_UNCALIBRATED_PRODUCTION |
| N-13 | BASELINE | 4440.0 | PRODUCTION_NOT_CALIBRATED | RESOLVED_WITH_UNCALIBRATED_PRODUCTION |
| N-13 | HIGH | 8880.0 | PRODUCTION_NOT_CALIBRATED | RESOLVED_WITH_UNCALIBRATED_PRODUCTION |
| O-15 | LOW | 2220.0 | PRODUCTION_NOT_CALIBRATED | RESOLVED_WITH_UNCALIBRATED_PRODUCTION |
| O-15 | BASELINE | 6660.0 | PRODUCTION_NOT_CALIBRATED | RESOLVED_WITH_UNCALIBRATED_PRODUCTION |
| O-15 | HIGH | 13320.0 | PRODUCTION_NOT_CALIBRATED | RESOLVED_WITH_UNCALIBRATED_PRODUCTION |
| Ga-68 | LOW | 555.0 | PRODUCTION_NOT_CALIBRATED | RESOLVED_WITH_UNCALIBRATED_PRODUCTION |
| Ga-68 | BASELINE | 1850.0 | PRODUCTION_NOT_CALIBRATED | RESOLVED_WITH_UNCALIBRATED_PRODUCTION |
| Ga-68 | HIGH | 3700.0 | PRODUCTION_NOT_CALIBRATED | RESOLVED_WITH_UNCALIBRATED_PRODUCTION |

## TABLE 32 — Short-Half-Life Architecture Crossover Search

| Experiment | Cost-only rank-1 | Ranked order |
|---|---|---|
| EXP1 | MANUAL_CONVENTIONAL | MANUAL_CONVENTIONAL < AUTOMATED_CONVENTIONAL < MRT_DOMINANT < HYBRID_MRT |
| EXP2 | MANUAL_CONVENTIONAL | MANUAL_CONVENTIONAL < AUTOMATED_CONVENTIONAL < MRT_DOMINANT < HYBRID_MRT |
| EXP3 | MANUAL_CONVENTIONAL | MANUAL_CONVENTIONAL < AUTOMATED_CONVENTIONAL < MRT_DOMINANT < HYBRID_MRT |
| EXP4 | MANUAL_CONVENTIONAL | MANUAL_CONVENTIONAL < AUTOMATED_CONVENTIONAL < MRT_DOMINANT < HYBRID_MRT |

*No architecture-family crossover across the short-half-life controls at the
benchmark basis.*

## TABLE 33 — MRT Crossover Search

| Field | Value |
|---|---|
| Experiments examined | EXP0, EXP1, EXP2, EXP3, EXP4, EXP9A, EXP9B, EXP11, EXP12 |
| Stable ranking order | MANUAL_CONVENTIONAL < AUTOMATED_CONVENTIONAL < MRT_DOMINANT < HYBRID_MRT |
| Manual always cost-rank 1 | True |
| MRT ever Pareto member | False |
| Hybrid ever Pareto member | False |
| MRT crossover observed | False |
| Hybrid crossover observed | False |

**Conclusion:** NO_MRT_CROSSOVER_OBSERVED: across every tested radionuclide/source/demand condition the cost-only ranking was stable (MANUAL_CONVENTIONAL < AUTOMATED_CONVENTIONAL < MRT_DOMINANT < HYBRID_MRT) at the validated benchmark basis. MRT's measured advantage is in retained-activity physics (shorter route time), NOT in the derived lifecycle cost at this basis -- reported honestly, not forced.

## TABLE 34 — Ga-68 Pathway Consequences

| Pathway | Source identity | Production source type | Production gate | Stream status |
|---|---|---|---|---|
| Cyclotron | CYPRIS MP-30 | CYCLOTRON | PRODUCTION_NOT_CALIBRATED | RESOLVED_WITH_UNCALIBRATED_PRODUCTION |
| Generator | ECKERT_ZIEGLER_GALLIAPHARM | GENERATOR | PRODUCTION_NOT_CALIBRATED | RESOLVED_WITH_UNCALIBRATED_PRODUCTION |

*The generator pathway removes the cyclotron production leg (on-site elution),
changing the transport problem; its procurement/service economics remain
NOT_CALIBRATED (never zero-filled). Neither pathway fabricates capacity.*

## TABLE 35 — Mixed-Scenario Scheduling Disclosure

| Scenario | True joint scheduling | Phase-1 aggregation | Joint-op feasibility | Shared-resource conflict validation | Stream count |
|---|---|---|---|---|---|
| MIXED_PET_F18_C11_N13_O15 | NO | YES | NOT_FULLY_VALIDATED | NOT_VALIDATED | 4 |
| MIXED_PET_SPECT_F18_TC99M_GA68 | NO | YES | NOT_FULLY_VALIDATED | NOT_VALIDATED | 3 |

## TABLE 36 — Patient Export Preview (Mixed PET + SPECT)

| Radionuclide | Clinical modality | Patient count | Admin activity (MBq) | Required scanners | Scanner modality | Production source | Production gate | Stream status |
|---|---|---|---|---|---|---|---|---|
| F-18 | PET | 24 | 370.0 | 2 | PET | CYCLOTRON/PETtrace 890 | PRODUCTION_SUFFICIENT | RESOLVED_ADMISSIBLE |
| Tc-99m | SPECT | 16 | 740.0 | 1 | SPECT | GENERATOR/CURIUM_TECHNELITE | PRODUCTION_NOT_CALIBRATED | RESOLVED_WITH_UNCALIBRATED_PRODUCTION |
| Ga-68 | PET | 6 | 185.0 | 1 | PET | GENERATOR/ECKERT_ZIEGLER_GALLIAPHARM | PRODUCTION_NOT_CALIBRATED | RESOLVED_WITH_UNCALIBRATED_PRODUCTION |

## TABLE 37 — Forward Appointment Export Preview

The patient/appointment export seam (`export_patient_appointment_rows`) is a
stable typed projection of the per-radionuclide resolutions, suitable for a
downstream scheduler/calendar. It re-runs NO engine. The Mixed PET rows below
illustrate the forward-planning payload:

| Scenario | Radionuclide | Modality | Patient count | Required scanners | Production source |
|---|---|---|---|---|---|
| MIXED_PET_F18_C11_N13_O15 | F-18 | PET | 20 | 1 | CYCLOTRON/PETtrace 890 |
| MIXED_PET_F18_C11_N13_O15 | C-11 | PET | 5 | 1 | CYCLOTRON/Cyclone KIUBE |
| MIXED_PET_F18_C11_N13_O15 | N-13 | PET | 5 | 1 | CYCLOTRON/Cyclone KIUBE |
| MIXED_PET_F18_C11_N13_O15 | O-15 | PET | 5 | 1 | CYCLOTRON/Cyclone KIUBE |

## TABLE 38 — Financial Export Preview (Mixed PET + SPECT)

| Architecture | Feasible | New-study CapEx | Annual OPEX | Lifecycle cost | True total annual OPEX | Total comparable CapEx |
|---|---|---|---|---|---|---|
| MANUAL_CONVENTIONAL | True | $125,000 | $1,750,320 | $11,869,790 | $6,771,800 | $125,000 |
| AUTOMATED_CONVENTIONAL | True | $1,925,000 | $1,870,772 | $14,478,032 | $6,892,252 | $1,925,000 |
| MRT_DOMINANT | True | $11,480,000 | $5,073,280 | $45,522,122 | $5,073,280 | $11,480,000 |
| HYBRID_MRT | True | $7,106,000 | $6,807,690 | $52,786,154 | $6,807,690 | $7,106,000 |

*These read-models are suitable for future downloadable CSV/XLSX/report
exports (UI download not built here).*

## TABLE 39 — Known vs Unknown Economics

| Dimension | Status |
|---|---|
| New-study CapEx | KNOWN (derived per architecture) |
| Architecture-specific / common CapEx split | KNOWN (Build 2R decomposition) |
| Known annual OPEX subtotal | KNOWN (derived) |
| Cyclotron energy / consumable / service OPEX | NOT_CALIBRATED (never zero-filled) |
| Generator procurement / service OPEX | NOT_CALIBRATED (never zero-filled) |
| Scanner energy / service OPEX | NOT_CALIBRATED (never zero-filled) |
| Total annual OPEX | KNOWN_SUBTOTAL_ONLY_TOTAL_NOT_CALIBRATED |
| Lifecycle cost (ranking basis) | derived from known subtotal — NOT a fully calibrated lifecycle total |

## TABLE 40 — Remaining Calibration Gaps

| Gap | Status |
|---|---|
| C-11/N-13/O-15/Ga-68 production EOB yields | NOT_CALIBRATED (declared/modeled only) |
| Ge-68→Ga-68 generator procurement economics | NOT_CALIBRATED |
| Alternative MRT carrier speeds | CONTROLLED_EXPERIMENTAL_ASSUMPTION |
| Model-specific scanner selection | DEFERRED (CLASS_AND_MODALITY only) |
| True joint multi-radionuclide scheduling | NOT IMPLEMENTED (Phase-1 aggregation only) |

## TABLE 41 — Experimental Limitations

| # | Limitation |
|---|---|
| 1 | ENGINE_BASIS: four-architecture economics are anchored to the validated benchmark single-radionuclide nuclear basis (joint-scheduling governor); radionuclide identity does NOT alter architecture economics/ranking at a fixed basis -- radionuclide-specific consequences appear in the decay / required-upstream-activity / production-calibration / scanner / transport observations. |
| 2 | ECONOMICS: total OPEX is a KNOWN SUBTOTAL only; service/procurement/energy remain NOT_CALIBRATED (never zero-filled). Ranking is cost-only over the derived lifecycle cost. |
| 3 | SCHEDULING: MIXED scenario: each radionuclide stream is resolved INDEPENDENTLY (source/activity/decay/scanner/production). The detailed physical timing engine is single-radionuclide, so integrated operational feasibility is NOT validated -- individual-stream feasibility does NOT imply joint feasibility. |
| 4 | SCHEDULING: TRUE_JOINT_MULTI_RADIONUCLIDE_SCHEDULING=NO; mixed scenarios are a Phase-1 AGGREGATION, JOINT_OPERATIONAL_FEASIBILITY_STATUS may be NOT_FULLY_VALIDATED. |
| 5 | SCANNER: optimization is at CLASS_AND_MODALITY (modality x quantity); model-specific scanner selection is DEFERRED (readiness doc PART_3E_SCANNER_MODEL_SELECTION_READY=NO). |
| 6 | PREVALENCE: the demand mix is ALWAYS an explicit input; no radionuclide prevalence is invented (portfolio multi_radionuclide_weighting_authority=NOT_MODELED preserved). |
| 7 | PART_3D: the canonical four-architecture bouquet derives feasibility via derive_physical_feasibility; the separate evaluate_light_mrt_dominant hardcoded feasible=True is NOT in this bouquet. |

## TABLE 42 — Final Architecture Bouquet Summary

| Architecture | Feasible (baseline) | Cost-only rank (baseline) | Pareto (baseline) | Ever cost-rank-1 across campaign | Ever Pareto across campaign |
|---|---|---|---|---|---|
| MANUAL_CONVENTIONAL | True | 1 | True | True | True |
| AUTOMATED_CONVENTIONAL | True | 2 | False | False | False |
| MRT_DOMINANT | True | 3 | False | False | False |
| HYBRID_MRT | True | 4 | False | False | False |

## Interpretation (mandatory rules honored)

- The campaign encodes NO architecture bonus. Ranking is cost-only over the
  derived lifecycle cost; at the validated benchmark basis the conventional
  families rank ahead of the MRT families (Manual < Automated < MRT_Dominant <
  Hybrid) for every tested condition.
- MRT's measurable advantage is PHYSICAL, not economic at this basis: its
  shorter route time retains more activity (e.g. C-11 retained 0.283 via MRT
  vs 0.265 via manual on the worst-case route) and lowers required upstream
  EOB activity. This is reported as a physics consequence, never converted
  into an unearned economic win.
- Short half-life is OBSERVED, never rewarded: O-15 (2.04 min) collapses to
  ~0 retained regardless of transport mode or MRT speed; it is not forced
  feasible-with-advantage.
- Production is radionuclide- and equipment-specific: a calibrated F-18 record
  never qualifies C-11/N-13/O-15/Ga-68; support is never converted to
  calibration; output is never borrowed between models.
- **NO_MRT_CROSSOVER_OBSERVED** over the tested range — reported honestly.
- Unknown economics are never treated as zero; total OPEX is a known subtotal
  only; joint multi-radionuclide scheduling is never claimed.

