from pathlib import Path
import sys

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root))

from medsid_repro.independent_nsaid_e import run_independent_model_e

workbook = root / "sources" / "nsaid_2024_original_workbook_came077880.ww1.xlsm"
out = root / "outputs" / "independent_model_E"
print(run_independent_model_e(workbook, out))
