from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from medsid_repro.nsaid_main_figures import (
    extract_figure1_workbook_data,
    extract_figure2_workbook_data,
    load_figure3_digitised_points,
    reproduce_all,
)

ROOT = Path(__file__).resolve().parents[1]
WORKBOOK = ROOT / "sources" / "nsaid_2024_original_workbook_came077880.ww1.xlsm"


def test_figure1_is_extracted_from_workbook_cache() -> None:
    data = extract_figure1_workbook_data(WORKBOOK)
    assert data.shape == (5, 7)
    assert np.isclose(data["Deaths"].sum(), 735.9676530384182)
    assert np.isclose(data["Acute exacerbations of heart failure"].sum(), 6748.277620347485)
    assert np.isclose(data["Acute kidney injuries"].sum(), 3270.865986714495)


def test_figure2_is_england_level_cached_psa() -> None:
    cloud, workbook_ellipse, summary = extract_figure2_workbook_data(WORKBOOK)
    assert len(cloud) == 1000
    assert len(workbook_ellipse) == 101
    assert np.isclose(summary.mean_cost_gbp, 31197502.33274317, rtol=0, atol=1e-4)
    assert np.isclose(summary.mean_qaly, -6174.5594430818865, rtol=0, atol=1e-8)
    assert summary.probability_additional_cost == 1.0
    assert summary.probability_negative_qaly == 1.0


def test_figure3_digitised_points_are_monotonic() -> None:
    data = load_figure3_digitised_points(ROOT / "data" / "nsaid_2024_figure3_digitised_points.csv")
    assert len(data) == 40
    assert np.isclose(data["duration_years"].iloc[0], 0.25)
    assert np.isclose(data["duration_years"].iloc[-1], 10.0)
    assert (data["cost_impact_gbp_millions"].diff().dropna() >= 0).all()
    assert (data["qaly_impact_thousands"].diff().dropna() <= 0).all()


def test_workflow_regenerates_new_outputs(tmp_path: Path) -> None:
    summary = reproduce_all(
        workbook=WORKBOOK,
        figure3_digitised_csv=ROOT / "data" / "nsaid_2024_figure3_digitised_points.csv",
        table2_csv=ROOT / "data" / "nsaid_2024_published_table2.csv",
        workbook_summary_csv=ROOT / "outputs" / "nsaid_excel_summary_from_original_workbook.csv",
        output_dir=tmp_path,
    )
    expected = [
        "figure1_expected_excess_events_workbook.png",
        "figure1_workbook_event_counts.csv",
        "figure2_total_cost_qaly_psa_workbook.png",
        "figure2_workbook_psa_cloud.csv",
        "figure3_exposure_duration_digitised_reconstruction.png",
        "figure3_digitised_points_used.csv",
        "reproduction_status.csv",
        "workflow_summary.json",
    ]
    for name in expected:
        assert (tmp_path / name).exists()
    assert summary["independent_python_deterministic_markov_reimplementation_all_five_models"] is True
    assert summary["independent_python_markov_reimplementation_model_A"] is True
    assert summary["independent_python_markov_reimplementation_model_E"] is True
    assert summary["independent_python_psa_reimplementation"] is False


def test_status_is_explicit_about_limits() -> None:
    status = pd.read_csv(ROOT / "outputs" / "nsaid_2024_main_figures" / "reproduction_status.csv")
    fig3 = status.loc[status["item"] == "BMJ Figure 3"].iloc[0]
    markov = status.loc[status["item"] == "Independent Python translation of five Markov models"].iloc[0]
    assert "digitised" in fig3["evidence_level"]
    assert markov["status"] == "completed for deterministic analysis"
    assert "PSA" in markov["limitation"]
