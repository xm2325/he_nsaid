"""Dashboard support for a Figure 2-style PSA cost-QALY cloud.

The public NSAID workbook stores 1,000 probabilistic sensitivity analysis (PSA)
iterations. The BMJ article reports Figure 2 from 10,000 simulations. This
module reaggregates the cached workbook England-level model outputs in Python,
exports a small dashboard reference data set, and draws a Figure 2-style chart.

The exported cloud is a traceable cached-workbook reference. It is not a new
parameter-level 10,000-sample PSA run.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any
import json

import matplotlib.pyplot as plt
import pandas as pd

from .independent_nsaid_psa import (
    aggregate_england_psa,
    confidence_ellipse,
    extract_england_query_level_psa,
)

FIGURE2_CLOUD_FILENAME = "figure2_cached_psa_cloud.csv"
FIGURE2_ELLIPSE_FILENAME = "figure2_cached_psa_ellipse.csv"
FIGURE2_SUMMARY_FILENAME = "figure2_cached_psa_summary.json"

# BMJ Figure 2 colour choices used for the dashboard redraw.
FIGURE2_SCATTER_COLOR = "#1f77b4"
FIGURE2_ELLIPSE_COLOR = "#d4148e"
FIGURE2_PUBLISHED_MEAN_COLOR = "#f6b21a"
FIGURE2_CACHED_MEAN_COLOR = "#ffffff"
FIGURE2_DETERMINISTIC_COLOR = "#202020"

REQUIRED_CLOUD_COLUMNS = {"iteration", "incremental_cost_gbp", "incremental_qaly"}
REQUIRED_ELLIPSE_COLUMNS = {"incremental_cost_gbp", "incremental_qaly"}


def _validate_columns(data: pd.DataFrame, required: set[str], label: str) -> None:
    missing = sorted(required.difference(data.columns))
    if missing:
        raise ValueError(f"{label} is missing required columns: {missing}")


def export_dashboard_figure2_reference(workbook_path: Path, output_dir: Path) -> dict[str, Any]:
    """Export cached-workbook PSA rows used by the Streamlit Figure 2 tab.

    The function reads England-level PSA outputs for Models A--E from the
    workbook, sums the five model outputs by iteration in Python, computes a
    95% bivariate-normal ellipse, and writes versioned dashboard files.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    query_level = extract_england_query_level_psa(workbook_path)
    cloud = aggregate_england_psa(query_level)
    ellipse = confidence_ellipse(cloud, level=0.95, n_points=201)

    _validate_columns(cloud, REQUIRED_CLOUD_COLUMNS, "Figure 2 cloud")
    _validate_columns(ellipse, REQUIRED_ELLIPSE_COLUMNS, "Figure 2 ellipse")

    summary: dict[str, Any] = {
        "reference": "BMJ 2024 Figure 2-style dashboard redraw from cached public-workbook PSA outputs",
        "workbook_cached_iterations": int(cloud.shape[0]),
        "article_reported_iterations": 10_000,
        "cached_workbook_mean_incremental_cost_gbp": float(cloud["incremental_cost_gbp"].mean()),
        "cached_workbook_mean_incremental_qaly": float(cloud["incremental_qaly"].mean()),
        "cached_workbook_probability_additional_cost": float((cloud["incremental_cost_gbp"] > 0).mean()),
        "cached_workbook_probability_negative_qaly": float((cloud["incremental_qaly"] < 0).mean()),
        "published_article_probability_additional_cost": 0.9994,
        "published_article_probability_negative_qaly": 1.0,
        "source_logic": (
            "Read cached England-level Model A--E PSA query outputs from PSA.Data, "
            "sum by iteration in Python, and compute a 95% ellipse from the stored cloud."
        ),
        "scientific_limit": (
            "The public workbook stores 1,000 cached PSA iterations. The article reports "
            "10,000 simulations. This dashboard reference is not a new parameter-level PSA run."
        ),
    }

    cloud.to_csv(output_dir / FIGURE2_CLOUD_FILENAME, index=False)
    ellipse.to_csv(output_dir / FIGURE2_ELLIPSE_FILENAME, index=False)
    (output_dir / FIGURE2_SUMMARY_FILENAME).write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary


def load_dashboard_figure2_reference(data_dir: Path) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    """Load and validate the dashboard Figure 2 cloud, ellipse, and metadata."""
    cloud = pd.read_csv(data_dir / FIGURE2_CLOUD_FILENAME)
    ellipse = pd.read_csv(data_dir / FIGURE2_ELLIPSE_FILENAME)
    summary = json.loads((data_dir / FIGURE2_SUMMARY_FILENAME).read_text(encoding="utf-8"))

    _validate_columns(cloud, REQUIRED_CLOUD_COLUMNS, "Figure 2 cloud")
    _validate_columns(ellipse, REQUIRED_ELLIPSE_COLUMNS, "Figure 2 ellipse")
    expected_rows = int(summary["workbook_cached_iterations"])
    if cloud.shape[0] != expected_rows:
        raise ValueError(
            f"Figure 2 cached cloud has {cloud.shape[0]} rows but metadata records {expected_rows}"
        )
    return cloud, ellipse, summary


def make_figure2_dashboard_plot(
    cloud: pd.DataFrame,
    ellipse: pd.DataFrame,
    *,
    published_mean_cost_gbp: float,
    published_mean_qaly: float,
    deterministic_cost_gbp: float,
    deterministic_qaly: float,
    deterministic_label: str = "Selected deterministic point",
):
    """Draw a Figure 2-style dashboard plot with transparent comparison markers."""
    _validate_columns(cloud, REQUIRED_CLOUD_COLUMNS, "Figure 2 cloud")
    _validate_columns(ellipse, REQUIRED_ELLIPSE_COLUMNS, "Figure 2 ellipse")

    x = cloud["incremental_qaly"].to_numpy(dtype=float) / 1_000.0
    y = cloud["incremental_cost_gbp"].to_numpy(dtype=float) / 1_000_000.0
    ellipse_x = ellipse["incremental_qaly"].to_numpy(dtype=float) / 1_000.0
    ellipse_y = ellipse["incremental_cost_gbp"].to_numpy(dtype=float) / 1_000_000.0

    fig, ax = plt.subplots(figsize=(8.1, 5.7))
    ax.scatter(
        x,
        y,
        s=11,
        alpha=0.28,
        linewidths=0,
        color=FIGURE2_SCATTER_COLOR,
        label="Cached workbook PSA rows (n=1,000)",
    )
    ax.plot(
        ellipse_x,
        ellipse_y,
        linewidth=2.0,
        linestyle=":",
        color=FIGURE2_ELLIPSE_COLOR,
        label="95% ellipse from cached rows",
    )
    ax.scatter(
        [published_mean_qaly / 1_000.0],
        [published_mean_cost_gbp / 1_000_000.0],
        marker="D",
        s=66,
        facecolors=FIGURE2_PUBLISHED_MEAN_COLOR,
        edgecolors="#203040",
        linewidths=0.8,
        label="Published Table 3 PSA mean",
        zorder=5,
    )
    ax.scatter(
        [float(x.mean())],
        [float(y.mean())],
        marker="o",
        s=62,
        facecolors=FIGURE2_CACHED_MEAN_COLOR,
        edgecolors="#203040",
        linewidths=1.0,
        label="Cached-workbook PSA mean",
        zorder=5,
    )
    ax.scatter(
        [deterministic_qaly / 1_000.0],
        [deterministic_cost_gbp / 1_000_000.0],
        marker="X",
        s=88,
        color=FIGURE2_DETERMINISTIC_COLOR,
        label=deterministic_label,
        zorder=6,
    )

    ax.axhline(0.0, linewidth=1.0, color="black")
    ax.axvline(0.0, linewidth=1.0, color="black")
    ax.set_xlim(-12, 2)
    ax.set_ylim(-40, 120)
    ax.set_xticks([-12, -10, -8, -6, -4, -2, 0, 2])
    ax.set_yticks([-40, 0, 40, 80, 120])
    ax.grid(axis="y", linewidth=1.0, alpha=0.55)
    ax.set_axisbelow(True)
    ax.set_xlabel("QALY impact of hazardous prescribing (000s)", fontweight="bold")
    ax.set_ylabel("Cost impact of hazardous\nprescribing (£ millions)", fontweight="bold")
    ax.legend(frameon=False, loc="upper left", fontsize=8.2)
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    return fig
