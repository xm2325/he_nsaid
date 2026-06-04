# Native R contract runner

This directory contains an R implementation that can run in GitHub Actions
without Excel, LibreOffice, VBA, or proprietary software.

## What the R code does

The R runner performs native matrix-based state-transition calculations for all
five deterministic NSAID models and independently repeats the Figure 2 PSA
aggregation step. It reads versioned CSV contracts from `r/data/`:

```text
initial_state_contract.csv
transition_contract.csv
reward_contract.csv
summary_reference.csv
trace_reference.csv
psa_model_level_england.csv
psa_total_reference.csv
```

The contracts are generated from the Python formula engines with:

```bash
python scripts/export_r_contracts.py
```

Then run the R workflow:

```bash
Rscript r/scripts/run_all.R
Rscript r/tests/test_contract_runner.R
```

## Scientific scope

The Python layer contains the formula-level deterministic reconstruction of
Models A--E. The R layer is a second, dependency-light implementation of:

- transition-matrix propagation;
- life-year, QALY and cost accumulation;
- discounting;
- deterministic cross-language regression validation;
- Figure 2 PSA aggregation and plotting.

The R layer consumes explicit transition and reward contracts rather than
re-parsing the workbook formulas. This makes it suitable for Linux GitHub
Actions runners and later R Shiny integration.

The repository still does **not** implement a fully independent parameter-level
PSA sampler. The Figure 2 PSA workflow re-aggregates workbook-saved model-level
England PSA outputs.
