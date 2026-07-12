# MRT Pharma™ Outpatient Decision-Support Digital Twin

- Conventional expansion is derived proportionally from the current balanced hospital.
- MRT optimization searches only production increase and batches/day.
- Scanner, injection-room and uptake-room requirements are derived.
- Uptake rooms are capacity constraints, not MRT endpoints.
- MRT endpoints are radiopharmacy, injection rooms, scanners and optional return/disposal.
- MRT production increase remains strictly below the conventional benchmark.
- Both options serve the same target and receive the same target-capped revenue.
- Highest positive NPV determines the winner.

Run:
```bash
pip install -r requirements.txt
streamlit run app.py
```
Validate:
```bash
python validation_scenarios.py
pytest
```
