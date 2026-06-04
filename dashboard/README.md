# Python Streamlit dashboard

Run locally:

```bash
python -m pip install -r requirements.txt
python scripts/export_dashboard_contract.py
streamlit run dashboard/streamlit_app.py
```

For Streamlit Community Cloud, connect the GitHub repository and set the main
file path to:

```text
dashboard/streamlit_app.py
```

The default UI mode uses a versioned dashboard contract for fast updates. The
optional live mode reruns the Python state-transition engines for the chosen
exposure duration.
