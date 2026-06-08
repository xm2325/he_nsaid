#!/usr/bin/env python3
"""Export cached-workbook PSA reference rows for the Streamlit Figure 2 tab."""
from __future__ import annotations

from pathlib import Path
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from medsid_repro.dashboard_figure2 import export_dashboard_figure2_reference  # noqa: E402


def main() -> None:
    workbook = ROOT / "sources" / "nsaid_2024_original_workbook_came077880.ww1.xlsm"
    output_dir = ROOT / "dashboard" / "data"
    summary = export_dashboard_figure2_reference(workbook, output_dir)
    print("PASS: exported cached-workbook PSA reference rows for the Streamlit Figure 2 tab.")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
