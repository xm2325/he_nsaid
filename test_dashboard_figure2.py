import json
import pandas as pd
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def test_all_11_models_pass():
    summary = json.loads((ROOT / "outputs" / "summary_status.json").read_text())
    assert summary["n_models"] == 11
    assert summary["n_passed"] == 11
    assert summary["all_11_passed"] is True

def test_all_validation_checks_pass():
    checks = pd.read_csv(ROOT / "outputs" / "all_validation_checks.csv")
    assert len(checks) >= 50
    assert checks["passed"].all()

def test_nsaid_workbook_audit_detects_model_sheets():
    audit = pd.read_csv(ROOT / "outputs" / "nsaid_workbook_sheet_audit.csv")
    for sheet in ["Parameters", "PSA.Data", "A.Markov", "B.Markov", "C.Markov", "D.Markov", "E.Markov"]:
        assert sheet in set(audit["sheet"])

def test_image_comparisons_exist():
    idx = pd.read_csv(ROOT / "outputs" / "image_comparison_index.csv")
    assert len(idx) >= 4
    for p in idx["comparison_panel"]:
        assert (ROOT / p).exists()
