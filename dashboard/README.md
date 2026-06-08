# Python Streamlit dashboard

Run locally:

```bash
python -m pip install -r requirements.txt
python scripts/export_dashboard_contract.py
python scripts/export_dashboard_figure2_reference.py
streamlit run dashboard/streamlit_app.py
```

For Streamlit Community Cloud, connect the GitHub repository and set the main
file path to:

```text
dashboard/streamlit_app.py
```

The default UI mode reruns the live Python state-transition engines at the article base case.
The article view also includes a Figure 2-style PSA cost-QALY cloud. The cloud is reaggregated
in Python from the 1,000 cached PSA rows stored in the public workbook. The BMJ article reports
10,000 simulations, so the dashboard labels the plot as a cached-workbook reference rather than
as a new parameter-level PSA run.

The optional fast mode reads a versioned duration grid exported from the same Python engines.
