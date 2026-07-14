# Streamlit Cloud Deployment Checklist

1. Extract the ZIP.
2. Upload the **contents of the extracted folder** to the GitHub repository root.
3. Confirm the repository root visibly contains `app.py`, `requirements.txt`, `domain/`, `engines/`, `ui/`, `entities/`, and `data/`.
4. Do not upload only the ZIP.
5. Set the Streamlit main file path to `app.py`.
6. Reboot the Streamlit app after the GitHub commit completes.

The root `app.py` now contains the actual Streamlit UI. It no longer starts with `from ui.streamlit_app import *`.
