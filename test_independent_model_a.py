from pathlib import Path
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from medsid_repro.dashboard_scenario import calculate_scenario_from_contract, scenario_curve

CONTRACT = pd.read_csv(ROOT / "dashboard" / "data" / "dashboard_scenario_contract.csv")


def test_dashboard_contract_has_five_models_and_quarter_year_grid():
    assert sorted(CONTRACT["model_id"].unique().tolist()) == ["A", "B", "C", "D", "E"]
    assert CONTRACT.shape[0] == 200
    assert CONTRACT["duration_years"].min() == 0.25
    assert CONTRACT["duration_years"].max() == 10.0


def test_dashboard_scenario_returns_positive_avoidable_cost_and_qaly_gain():
    metrics, rows, events = calculate_scenario_from_contract(
        CONTRACT,
        duration_years=10.0,
        selected_models=["A", "B", "C", "D", "E"],
        uptake=0.60,
        effectiveness=0.25,
        implementation_cost_per_approached_hpe_gbp=0.0,
    )
    assert rows.shape[0] == 5
    assert events.shape[0] == 6
    assert metrics["gross_cost_avoided_gbp"] > 0
    assert metrics["qaly_gained"] > 0
    assert metrics["net_budget_impact_gbp"] == metrics["gross_cost_avoided_gbp"]


def test_duration_curve_has_40_points_and_increasing_final_burden():
    curve = scenario_curve(
        CONTRACT,
        selected_models=["A", "B", "C", "D", "E"],
        uptake=0.60,
        effectiveness=0.25,
    )
    assert curve.shape[0] == 40
    assert curve.iloc[-1]["gross_cost_avoided_gbp"] > curve.iloc[0]["gross_cost_avoided_gbp"]
    assert curve.iloc[-1]["qaly_gained"] > curve.iloc[0]["qaly_gained"]
