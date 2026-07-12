# MRT Pharma™ Decision-Support Digital Twin

A planning digital twin comparing two ways to grow a hospital's oncology-imaging capacity to the same target patient volume:

1. **Conventional Expansion** — one-batch centralized benchmark with automatically derived production upgrade, scanners, injection rooms and uptake rooms.
2. **MRT Pharma Hybrid** — two-stage optimization that first minimizes required production increase, then maximizes NPV at that minimum by selecting batches/day, MRT-enabled inpatient rooms and limited additional dedicated rooms.

## Model rules

- Both architectures must serve the same target demand.
- Revenue is capped at that target; reserve capacity is reported but not monetized.
- MRT production expansion cannot exceed the conventional benchmark.
- Faster MRT transport affects retained radioactive activity through physical decay.
- Existing injection and uptake rooms remain available under MRT.
- MRT-enabled inpatient rooms serve as administration and uptake locations for the same inpatient without being counted as two physical rooms.
- Scanner sizing is identical for both architectures.
- Either option can win, or neither may be feasible.

## Files

- `model.py` — calculation and optimization engine.
- `app.py` — Streamlit interface.
- `test_model.py` — three validation scenarios.
- `tests/test_model.py` — pytest-compatible copy of the validation scenarios.
- `.streamlit/config.toml` — Streamlit theme.

## Run

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Validate

```bash
python3 test_model.py
```
