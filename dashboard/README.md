# Python Streamlit dashboard

Run locally:

```bash
python -m pip install -r requirements.txt
python scripts/export_dashboard_contract.py
python scripts/check_article_base_case.py
streamlit run dashboard/streamlit_app.py
```

For Streamlit Community Cloud, connect the GitHub repository and set the main
file path to:

```text
dashboard/streamlit_app.py
```

## Default screen

The default screen is **Article base-case reproduction** with **Live Python
state-transition models** selected. It reruns Models A--E from the public
workbook using the BMJ 2024 base-case settings:

```text
all five HPE models
England population scaling
10-year model horizon
10-year maximum HPE exposure duration unless an adverse event stops exposure
English NHS perspective
2020-21 costs
3.5% annual discounting for costs and QALYs
additive-effects assumption
```

The page compares the live deterministic result with the published Table 3 PSA
means. These values should not be forced to match exactly: the live point is a
deterministic reconstruction, while Table 3 reports means from a probabilistic
sensitivity analysis (PSA).

## Optional screen

The separate **Illustrative intervention scenario** screen retains the v13
user-defined layer:

```text
avoided burden = baseline HPE burden × uptake × effectiveness
```

The intervention effectiveness and implementation cost inputs are not estimated
by the BMJ 2024 article.
