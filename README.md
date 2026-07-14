# MRT Pharma™ Decision-Support Digital Twin V2.1

This build is governed by `constitution/CONSTITUTION.md` and separates the domain, engineering, finance, optimization, decision, diagnostics, state-management, and UI layers.

## Key V2.1 fixes

- Greenfield mode stores the Expansion baseline, forces all current values to zero, and restores the baseline when returning to Expansion.
- All current Greenfield fields remain disabled.
- Model inputs are constructed with named arguments.
- Conventional and MRT batch schedules are optimized independently.
- Batch OpEx uses `max(0, future_batches - current_batches)`.
- CSV and multi-sheet Excel exports are included.

## Run

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Test

```bash
pytest -q
```
