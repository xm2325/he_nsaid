#!/usr/bin/env bash
set -euo pipefail
python -m pip install -r requirements.txt
python scripts/run_all.py
python scripts/export_r_contracts.py
python scripts/validate_r_contracts.py
python -m pytest -q
