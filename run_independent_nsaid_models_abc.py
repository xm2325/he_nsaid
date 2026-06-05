from pathlib import Path
import sys
import json

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root))

from medsid_repro.independent_nsaid_ab import run_independent_models_ab

summary = run_independent_models_ab(
    workbook_path=root / "sources" / "nsaid_2024_original_workbook_came077880.ww1.xlsm",
    table2_csv=root / "data" / "nsaid_2024_published_table2.csv",
    output_dir=root / "outputs" / "independent_models_AB",
)
print(json.dumps(summary, indent=2))
