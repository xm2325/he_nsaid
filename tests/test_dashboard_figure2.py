from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

from medsid_repro.dashboard_figure2 import (
    FIGURE2_CLOUD_FILENAME,
    FIGURE2_ELLIPSE_FILENAME,
    FIGURE2_SUMMARY_FILENAME,
    export_dashboard_figure2_reference,
    load_dashboard_figure2_reference,
    make_figure2_dashboard_plot,
)

ROOT = Path(__file__).resolve().parents[1]
WORKBOOK = ROOT / "sources" / "nsaid_2024_original_workbook_came077880.ww1.xlsm"


def test_dashboard_figure2_reference_export_and_load(tmp_path: Path) -> None:
    summary = export_dashboard_figure2_reference(WORKBOOK, tmp_path)
    assert summary["workbook_cached_iterations"] == 1000
    assert summary["article_reported_iterations"] == 10_000
    assert np.isclose(summary["cached_workbook_mean_incremental_cost_gbp"], 31_197_502.33274322)
    assert np.isclose(summary["cached_workbook_mean_incremental_qaly"], -6174.5594430818865)
    assert summary["cached_workbook_probability_additional_cost"] == 1.0
    assert summary["cached_workbook_probability_negative_qaly"] == 1.0

    for filename in [FIGURE2_CLOUD_FILENAME, FIGURE2_ELLIPSE_FILENAME, FIGURE2_SUMMARY_FILENAME]:
        assert (tmp_path / filename).exists()

    cloud, ellipse, loaded_summary = load_dashboard_figure2_reference(tmp_path)
    assert cloud.shape[0] == 1000
    assert ellipse.shape[0] == 201
    assert loaded_summary == summary


def test_dashboard_figure2_plot_can_be_drawn() -> None:
    cloud, ellipse, _ = load_dashboard_figure2_reference(ROOT / "dashboard" / "data")
    fig = make_figure2_dashboard_plot(
        cloud,
        ellipse,
        published_mean_cost_gbp=31_430_000.0,
        published_mean_qaly=-6335.0,
        deterministic_cost_gbp=29_804_408.0,
        deterministic_qaly=-6051.0,
        deterministic_label="Live deterministic base case",
    )
    assert len(fig.axes) == 1
    assert fig.axes[0].get_xlim() == (-12.0, 2.0)
    assert fig.axes[0].get_ylim() == (-40.0, 120.0)
    plt.close(fig)


def test_streamlit_source_contains_figure2_tab() -> None:
    source = (ROOT / "dashboard" / "streamlit_app.py").read_text(encoding="utf-8")
    assert "Figure 2 PSA cloud" in source
    assert "make_figure2_dashboard_plot" in source
