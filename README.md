# MRT Pharma™ Digital Twin V2.2 — Architecture-Complete Deployment-Safe Build

## Critical fix

The root `app.py` now contains the actual Streamlit application. It no longer contains only:

```python
from ui.streamlit_app import *
```

## Deploy

1. Extract this ZIP.
2. Upload all extracted files and folders to the root of the GitHub repository.
3. Set the Streamlit main file path to `app.py`.

The repository root must visibly contain `app.py`, `requirements.txt`, `domain`, `engines`, `ui`, `entities`, and `data`.

## Run locally

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Test

```bash
pytest -q
python deployment/verify_repository.py
```
