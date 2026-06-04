#!/usr/bin/env bash
set -euo pipefail
python scripts/export_dashboard_contract.py
python scripts/validate_dashboard_contract.py
python scripts/run_dashboard_scenarios.py
Rscript r/tests/test_dashboard_scenario.R
Rscript r/scripts/run_dashboard_scenarios.R
python scripts/compare_dashboard_outputs.py
