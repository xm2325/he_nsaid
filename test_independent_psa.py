from pathlib import Path
import json
import pandas as pd

from medsid_repro.independent_nsaid_abcde import run_independent_models_abcde

ROOT = Path(__file__).resolve().parents[1]
WORKBOOK = ROOT / "sources" / "nsaid_2024_original_workbook_came077880.ww1.xlsm"


def test_independent_models_abcde_workflow(tmp_path):
    summary = run_independent_models_abcde(
        workbook_path=WORKBOOK,
        table2_csv=ROOT / "data" / "nsaid_2024_published_table2.csv",
        table3_csv=ROOT / "data" / "nsaid_2024_published_table3.csv",
        figure3_digitised_csv=ROOT / "data" / "nsaid_2024_figure3_digitised_points.csv",
        output_dir=tmp_path,
    )
    assert summary["independent_models_completed"] == ["A", "B", "C", "D", "E"]
    assert summary["all_trace_errors_below_1e-12"]
    assert summary["all_reward_errors_below_1e-10"]
    assert not summary["psa_reimplementation_completed"]
    assert summary["figure1_max_absolute_error_vs_workbook_cached"] < 1e-9
    assert (tmp_path / "figure1_independent_expected_excess_events_all_five_models.png").exists()
    assert (tmp_path / "figure1_independent_vs_workbook_cached_comparison.csv").exists()
    assert (tmp_path / "figure3_independent_exposure_duration_sensitivity_all_five_models.png").exists()
    assert (tmp_path / "figure3_independent_vs_published_digitised_comparison.png").exists()
    table2 = pd.read_csv(tmp_path / "table2_deterministic_reproduction_all_five_models.csv")
    assert table2["model_id"].tolist() == ["A", "B", "C", "D", "E"]
    table3 = pd.read_csv(tmp_path / "table3_england_base_case_all_five_models.csv")
    total = table3[table3["scope"] == "A+B+C+D+E total"].iloc[0]
    assert abs(total["independent_deterministic_cost_impact_gbp"] - 29_804_682.608383935) < 1e-5
    assert abs(total["independent_deterministic_qaly_impact"] - (-6050.9809190179585)) < 1e-9
