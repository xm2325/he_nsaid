from pathlib import Path
import sys

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root))

from medsid_repro.independent_nsaid_abcde import run_independent_models_abcde

print(run_independent_models_abcde(
    workbook_path=root / "sources" / "nsaid_2024_original_workbook_came077880.ww1.xlsm",
    table2_csv=root / "data" / "nsaid_2024_published_table2.csv",
    table3_csv=root / "data" / "nsaid_2024_published_table3.csv",
    figure3_digitised_csv=root / "data" / "nsaid_2024_figure3_digitised_points.csv",
    output_dir=root / "outputs" / "independent_models_ABCDE",
))
