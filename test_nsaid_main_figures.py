from pathlib import Path
import json

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs" / "independent_psa"


def test_psa_reaggregation_matches_workbook_total_cloud():
    summary = json.loads((OUT / "figure2_psa_reaggregation_summary.json").read_text())
    assert summary["n_iterations"] == 1000
    assert summary["probability_additional_cost"] == 1.0
    assert summary["probability_negative_qaly"] == 1.0
    assert summary["max_abs_cost_difference_vs_workbook_total"] < 1e-4
    assert summary["max_abs_qaly_difference_vs_workbook_total"] < 1e-8


def test_psa_reaggregation_outputs_expected_files():
    expected = [
        "figure2_model_level_england_query_psa_outputs.csv",
        "figure2_england_total_psa_reaggregated.csv",
        "figure2_reaggregated_vs_workbook_total_validation.csv",
        "figure2_reaggregated_python_ellipse.csv",
        "figure2_reaggregated_from_model_level_psa.png",
        "figure2_psa_reaggregation_summary.json",
    ]
    for name in expected:
        assert (OUT / name).exists()
    cloud = pd.read_csv(OUT / "figure2_england_total_psa_reaggregated.csv")
    assert cloud.shape[0] == 1000
    assert {"incremental_cost_gbp", "incremental_qaly"}.issubset(cloud.columns)
