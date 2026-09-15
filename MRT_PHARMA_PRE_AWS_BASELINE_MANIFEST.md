# MRT Pharma — Pre-AWS Engineering Authority Baseline Manifest

This is the single authoritative pre-AWS baseline manifest for the MRT Pharma
engineering expansion planner. It records the verified state of the repository
at the moment the pre-AWS engineering-authority baseline was closed and tagged.

Do not create competing baseline documents. Update this file in place if the
baseline is ever re-cut.

---

## Baseline identity

| Field | Value |
| --- | --- |
| `baseline_tag` | `mrt-pharma-pre-aws-v1` |
| `baseline_tag_message` | MRT Pharma pre-AWS engineering authority baseline |
| `baseline_commit_sha` | `<BASELINE_COMMIT_SHA>` (the commit that this manifest is part of; recorded at tag time — see Post-commit verification in the checkpoint report) |
| `pre_checkpoint_head` | `1de2c5b0d01e3a69e0c5a744b1d58ae1f3526bd3` |
| `branch` | `main` |
| `date` | 2026-09-15 |

## Product / authority doctrine

| Domain | Status |
| --- | --- |
| `commercial_ui` | `REACT_TYPESCRIPT_ONLY` |
| `streamlit_status` | `LEGACY_INTERNAL_HARNESS` |
| `Bentley` | `GEOMETRY_AUTHORITY` |
| `MRT Pharma engine` | `ENGINEERING_DECISION_AUTHORITY` |
| `OpenUSD/NVIDIA` | `VISUALIZATION_ACCELERATION_ONLY` |
| `GitHub` | `SOURCE_CONTROL_AUTHORITY` |
| `AWS application infrastructure` | `NOT_YET_IMPLEMENTED` |

## Verified regression state

| Suite | Result |
| --- | --- |
| Python regression | `5214 passed / 0 failed / 27 skipped` |
| Frontend regression (Vitest) | `1306 passed / 0 failed` |
| Frontend TypeScript | `PASS` |
| Frontend production build | `PASS` |

The full Python regression above reflects the previously completed full
verification run. This checkpoint did not alter any executable behavior; only
logical staging/commit operations and a local-environment dependency install
(`fastapi`/`uvicorn`/`httpx`, already declared in `requirements.txt`) were
performed. Targeted correction-closure suites were re-run and passed to confirm
the checkpointed files correspond to the verified state.

## Engineering-authority closure

| Invariant | Status |
| --- | --- |
| `legacy production authority closure` | `ZERO_AUTHORITATIVE_EXECUTABLE_PATHS` |
| Uncalibrated production never fabricates installed EOB capacity | HELD |
| Uncalibrated production still reports required EOB activity | HELD |
| Uncalibrated production does not fabricate 10% production-block CapEx | HELD |
| Calibrated physical EOB capacity used exactly as installed | HELD |
| Production-capacity status internally coherent | HELD |
| Decay-optimal uncalibrated multiplier cannot consume `current_usable_doses_per_day` | HELD |
| Multiplier cannot execute in the calibrated branch | HELD |
| MRT carrier fleet sizing + shortage evaluation share physical-occupancy doctrine | HELD |
| Generator catalog count = 4 (3 Tc-99m + 1 Ge-68/Ga-68 GalliaPharm) | HELD |
| GalliaPharm receives no fabricated GalliaPharm-specific procurement price | HELD |

Guard test: `test_production_capacity_invariant_guard.py` statically scans the
authoritative executable modules and asserts zero legacy dose-count /
production-block physical-capacity paths.

## Acceptance / workstream state

| Item | Status |
| --- | --- |
| `manual EVI acceptance` | `PENDING` (where applicable) |
| `AWS foundation` | `NEXT_PARALLEL_PLATFORM_WORKSTREAM` |
| `Build-to-Finish` | `RESUMES_AFTER_BASELINE` |

## Scope note

This is a baseline-closure checkpoint, not a new feature build. No physics,
economics, simulation, optimization, transport, spatial, Bentley, React/EVI, or
lineage behavior was redesigned to obtain this baseline. All pre-existing
Build 1B / EVI / Build 2A work is preserved. No AWS resources were created.
