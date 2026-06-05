#!/usr/bin/env python3
from pathlib import Path
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from medsid_repro.independent_nsaid_c import run_independent_model_c

summary = run_independent_model_c(
    ROOT / "sources" / "nsaid_2024_original_workbook_came077880.ww1.xlsm",
    ROOT / "outputs" / "independent_model_C",
)
print(json.dumps(summary, indent=2))
