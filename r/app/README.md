# R Shiny dashboard

Run locally from the repository root:

```bash
python scripts/export_dashboard_contract.py
Rscript -e 'shiny::runApp("r/app", launch.browser = TRUE)'
```

The app directory is self-contained for deployment to shinyapps.io because the
versioned dashboard contract is copied into `r/app/data/`.

The reactive inputs include model selection, HPE exposure duration, local
population scale, intervention uptake, intervention effectiveness and
implementation cost.
