# MRT Pharma Engineering Expansion Planner

This repository contains an engineering planning product for evaluating two expansion strategies:

- Conventional linear expansion
- MRT-enabled expansion with constrained optimization

This product is intentionally scoped for engineering expansion planning and reporting. It is not the Digital Twin research platform.

## Product workflow

1. Project
2. Current Facility
3. Expansion Goal
4. Compare Options
5. Results

## Inputs (simplified)

- Project name
- Current patients/day
- Target patients/day
- Current scanners
- Current injection rooms
- Current uptake rooms
- Existing cyclotron (yes/no)
- Current usable doses/day
- Current average transport time
- Estimated MRT delivery time (seconds, default 30)
- Existing MRT-connectable rooms
- Representative radionuclide or representative half-life

## Assumptions

Engineering assumptions start with standards from `models.py` (`PlannerAssumptions`) and can be adjusted in the collapsed "Customize assumptions" panel.

## Calculations

- Conventional path is deterministic and linear from the current operating fingerprint.
- MRT path uses constrained optimization to find the minimum feasible CapEx candidate, with tie-breakers:
  - minimum new rooms
  - minimum infrastructure
  - minimum scanners
  - maximum retained activity
  - maximum reserve capacity

## Run locally

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Tests

```bash
pytest -q
python verify_repository.py
python -m compileall .
```
