#!/usr/bin/env python3
"""Run article-figure extraction plus all five independent NSAID models."""
from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from medsid_repro.nsaid_main_figures import reproduce_all
from medsid_repro.independent_nsaid_abcde import run_independent_models_abcde
from medsid_repro.independent_nsaid_psa import run_psa_reaggregation


def main() -> None:
    workbook = ROOT / "sources" / "nsaid_2024_original_workbook_came077880.ww1.xlsm"
    main_figures = reproduce_all(
        workbook=workbook,
        figure3_digitised_csv=ROOT / "data" / "nsaid_2024_figure3_digitised_points.csv",
        table2_csv=ROOT / "data" / "nsaid_2024_published_table2.csv",
        workbook_summary_csv=ROOT / "outputs" / "nsaid_excel_summary_from_original_workbook.csv",
        output_dir=ROOT / "outputs" / "nsaid_2024_main_figures",
    )
    independent = run_independent_models_abcde(
        workbook_path=workbook,
        table2_csv=ROOT / "data" / "nsaid_2024_published_table2.csv",
        table3_csv=ROOT / "data" / "nsaid_2024_published_table3.csv",
        figure3_digitised_csv=ROOT / "data" / "nsaid_2024_figure3_digitised_points.csv",
        output_dir=ROOT / "outputs" / "independent_models_ABCDE",
    )
    psa = run_psa_reaggregation(
        workbook_path=workbook,
        output_dir=ROOT / "outputs" / "independent_psa",
    )
    print("NSAID 2024 workflow completed: article figures, deterministic Models A-E, and PSA re-aggregation")
    print(json.dumps({"main_figures": main_figures, "independent_models_ABCDE": independent, "psa_reaggregation": psa}, indent=2))


if __name__ == "__main__":
    main()
