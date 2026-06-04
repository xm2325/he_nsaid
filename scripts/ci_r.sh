#!/usr/bin/env bash
set -euo pipefail
python scripts/export_r_contracts.py
Rscript r/scripts/run_all.R
Rscript r/tests/test_contract_runner.R
