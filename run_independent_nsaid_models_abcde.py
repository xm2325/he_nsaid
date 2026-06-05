#!/usr/bin/env python3
from pathlib import Path
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from medsid_repro.independent_nsaid_abc import run_independent_models_abc

summary = run_independent_models_abc(
    workbook_path=ROOT / "sources" / "nsaid_2024_original_workbook_came077880.ww1.xlsm",
    table2_csv=ROOT / "data" / "nsaid_2024_published_table2.csv",
    output_dir=ROOT / "outputs" / "independent_models_ABC",
)
print(json.dumps(summary, indent=2))
