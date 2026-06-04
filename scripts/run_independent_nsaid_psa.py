#!/usr/bin/env python3
"""Run model-level PSA re-aggregation for NSAID Figure 2."""
from pathlib import Path
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from medsid_repro.independent_nsaid_psa import run_psa_reaggregation

def main() -> None:
    workbook = ROOT / "sources" / "nsaid_2024_original_workbook_came077880.ww1.xlsm"
    out = ROOT / "outputs" / "independent_psa"
    summary = run_psa_reaggregation(workbook, out)
    print(json.dumps(summary, indent=2))

if __name__ == "__main__":
    main()
