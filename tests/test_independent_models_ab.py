from pathlib import Path

import pandas as pd

from medsid_repro.independent_nsaid_ab import exposure_duration_sensitivity_ab, build_partial_table2_reproduction

ROOT = Path(__file__).resolve().parents[1]
WORKBOOK = ROOT / "sources" / "nsaid_2024_original_workbook_came077880.ww1.xlsm"
TABLE2 = ROOT / "data" / "nsaid_2024_published_table2.csv"


def test_partial_table2_contains_two_independent_models():
    df = build_partial_table2_reproduction(WORKBOOK, TABLE2)
    assert set(df["model_id"]) == {"A", "B"}
    assert (df["independent_incremental_discounted_cost_gbp"] > 0).all()
    assert (df["independent_incremental_discounted_qaly"] < 0).all()


def test_partial_exposure_duration_sensitivity_has_expected_scope():
    df = exposure_duration_sensitivity_ab(WORKBOOK)
    total = df[df["scope"] == "A+B partial total"].sort_values("duration_years")
    assert len(total) == 40
    assert total.iloc[0]["duration_years"] == 0.25
    assert total.iloc[-1]["duration_years"] == 10.0
    assert (total["england_qaly_impact"] < 0).all()
    assert (total["england_cost_impact_gbp"] > 0).all()
