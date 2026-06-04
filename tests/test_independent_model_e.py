from pathlib import Path
import json

from medsid_repro.independent_nsaid_e import run_independent_model_e

ROOT = Path(__file__).resolve().parents[1]
WORKBOOK = ROOT / "sources" / "nsaid_2024_original_workbook_came077880.ww1.xlsm"


def test_independent_model_e_matches_workbook(tmp_path):
    run_independent_model_e(WORKBOOK, tmp_path)
    validation = json.loads((tmp_path / "independent_model_E_validation_summary.json").read_text())
    assert validation["all_trace_errors_below_1e-12"]
    assert validation["all_reward_errors_below_1e-10"]
