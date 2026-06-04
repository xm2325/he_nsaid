#!/usr/bin/env python3
"""Generate NSAID 2024 BMJ main-figure reproductions with explicit evidence levels."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from medsid_repro.nsaid_main_figures import reproduce_all


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workbook", type=Path, default=ROOT / "sources" / "nsaid_2024_original_workbook_came077880.ww1.xlsm")
    parser.add_argument("--figure3-data", type=Path, default=ROOT / "data" / "nsaid_2024_figure3_digitised_points.csv")
    parser.add_argument("--table2", type=Path, default=ROOT / "data" / "nsaid_2024_published_table2.csv")
    parser.add_argument("--workbook-summary", type=Path, default=ROOT / "outputs" / "nsaid_excel_summary_from_original_workbook.csv")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "outputs" / "nsaid_2024_main_figures")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    summary = reproduce_all(
        workbook=args.workbook,
        figure3_digitised_csv=args.figure3_data,
        table2_csv=args.table2,
        workbook_summary_csv=args.workbook_summary,
        output_dir=args.output_dir,
    )
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
