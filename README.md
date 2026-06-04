# MedSID NSAID 2024 reproducibility repository

This repository reconstructs the five deterministic NSAID medicines-safety
state-transition models associated with Camacho et al. (2024), reproduces the
main article outputs available from the public workbook, and provides Python
and R workflows that can run on Linux GitHub Actions runners.

## Current scope

### Python formula-level models

The Python implementation rebuilds the deterministic transition logic from
workbook parameters for:

```text
A: NSAID in older people without gastroprotection
B: NSAID with previous peptic ulcer without gastroprotection
C: NSAID with oral anticoagulant
D: NSAID with heart failure
E: NSAID with chronic kidney disease
```

The validation suite compares reconstructed traces and rewards against workbook
cached values. Differences are limited to floating-point rounding error.

### Main article figures

```text
Figure 1: independently recalculated from Python model traces
Figure 2: PSA aggregation and plotting reconstructed from workbook-saved
          model-level England PSA outputs
Figure 3: independently recalculated five-model exposure-duration sensitivity
```

### Native R runner

The R layer reads versioned CSV contracts exported by the Python formula
engines and runs native R matrix propagation, reward accumulation, discounting,
PSA aggregation and regression validation. It is suitable as a base for later
R Shiny integration.

## Important limitation

The repository does **not yet** implement a fully independent parameter-level
PSA sampler. Figure 2 is reproduced by re-aggregating workbook-saved model-level
England PSA outputs. The code does not independently draw every uncertain
parameter and rerun Models A--E for each simulation.

## Quick start: Python

```bash
python -m pip install -r requirements.txt
python scripts/run_all.py
python scripts/export_r_contracts.py
python scripts/validate_r_contracts.py
python -m pytest -q
```

Or:

```bash
make ci-python
```

## Quick start: R

First regenerate the versioned CSV contracts:

```bash
python scripts/export_r_contracts.py
```

Then run:

```bash
Rscript r/scripts/run_all.R
Rscript r/tests/test_contract_runner.R
```

Or:

```bash
make ci-r
```

The R scripts use base R only.

## GitHub Actions

The repository includes:

```text
.github/workflows/ci.yml
```

It runs two jobs:

```text
python-reproduction
r-reproduction
```

Both jobs upload generated outputs as workflow artifacts.

See:

```text
docs/GITHUB_ACTIONS.md
docs/REPRODUCTION_STATUS_V12.md
```

## Key folders

```text
medsid_repro/             Python formula-level reconstruction
scripts/                  Python workflow and CI helper scripts
r/R/                      Native R contract runner
r/scripts/                R workflow entry points
r/tests/                  R regression tests
r/data/                   Versioned transition/reward contracts
.github/workflows/        GitHub Actions workflow
docs/                     Scientific and engineering notes
sources/                  Public source workbook and source files
outputs/                  Generated Python outputs
```

## Recommended claim for an application or README

> Independently reconstructed and regression-tested all five deterministic
> NSAID medicines-safety state-transition models in Python, reproduced the
> national excess-event and exposure-duration analyses, reconstructed the
> Figure 2 PSA aggregation workflow, and added a Linux-compatible native R
> matrix runner with GitHub Actions continuous integration.

Do not claim that the repository contains a fully independent parameter-level
PSA sampler until that component has been implemented.

## v13: separate Python and R Shiny dynamic dashboards

This repository now contains two separate dynamic interfaces:

```text
dashboard/streamlit_app.py   # Python Streamlit app
r/app/app.R                  # R Shiny app
```

Both interfaces support reactive scenario exploration over:

- selected NSAID models A--E;
- HPE exposure duration;
- local population scale or HPE counts;
- intervention uptake;
- intervention effectiveness;
- implementation cost per approached HPE.

The intervention layer is explicit:

```text
avoided burden = baseline HPE burden × uptake × effectiveness
```

Effectiveness is supplied by the user. The dashboards do not estimate a causal
effect.

### Python dashboard

```bash
python scripts/export_dashboard_contract.py
streamlit run dashboard/streamlit_app.py
```

The Python app provides a fast validated-contract mode and a live formula-engine
mode.

### R Shiny dashboard

```bash
python scripts/export_dashboard_contract.py
Rscript -e 'shiny::runApp("r/app", launch.browser = TRUE)'
```

### GitHub Actions cross-language validation

Every push and pull request runs standard dashboard scenarios in Python and R,
then compares their numeric outputs. CI fails when scaled relative error reaches
`1e-10`.

See:

```text
docs/DYNAMIC_DASHBOARDS.md
docs/DEPLOYMENT_GUIDE.md
```

## v13 article-default Streamlit patch

The Python Streamlit application now starts with:

```text
Analysis view: Article base-case reproduction
Calculation mode: Live Python state-transition models
Models: A--E
Population: England scaling
HPE exposure duration: 10 years
```

The default screen calculates the full hazardous-prescribing burden and
compares the independent deterministic result with the published Table 3 PSA
means. It does not apply intervention uptake, effectiveness or implementation
cost unless the user changes to the separate illustrative intervention view.

Run the article-default validation with:

```bash
python scripts/check_article_base_case.py
```

See:

```text
docs/ARTICLE_BASE_CASE_DASHBOARD.md
```
