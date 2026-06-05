from pathlib import Path
import json

from medsid_repro.independent_nsaid_d import run_independent_model_d

ROOT = Path(__file__).resolve().parents[1]
WORKBOOK = ROOT / "sources" / "nsaid_2024_original_workbook_came077880.ww1.xlsm"


def test_independent_model_d_matches_workbook(tmp_path):
    run_independent_model_d(WORKBOOK, tmp_path)
    validation = json.loads((tmp_path / "independent_model_D_validation_summary.json").read_text())
    assert validation["all_trace_errors_below_1e-12"]
    assert validation["all_reward_errors_below_1e-10"]
