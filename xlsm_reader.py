"""Reproduce the main figures from Camacho et al. (BMJ 2024;386:e077880).

Scientific scope
----------------
This module intentionally separates three evidence levels:

1. Figure 1: direct extraction of cached workbook outputs from ``Results.Summ``.
2. Figure 2: direct extraction of the cached England-level PSA point cloud from
   ``PSA.Outputs`` followed by a Python redraw and a Python-computed confidence
   ellipse. The included workbook stores 1,000 simulations, whereas the article
   reports 10,000 simulations.
3. Figure 3: redraw from digitised points extracted from the published figure.
   This is not an independent Markov-model recalculation.

The module does not claim an independent Python translation of the five Markov
models. It creates traceable scientific-reproduction outputs from the original
workbook and published article.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable
import json

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from scipy.stats import chi2

from medsid_repro.xlsm_reader import XlsmXmlReader


FIG1_CATEGORIES = [
    "Deaths",
    "Symptomatic ulcers",
    "Serious gastrointestinal events",
    "Strokes",
    "Acute exacerbations of heart failure",
    "Acute kidney injuries",
]

MODEL_ORDER = [
    "NSAID in older people without gastroprotection",
    "NSAID with oral anticoagulant",
    "NSAID with chronic kidney disease",
    "NSAID with previous peptic ulcer without gastroprotection",
    "NSAID with heart failure",
]

FIG1_DISPLAY_LABELS = {
    "NSAID in older people without gastroprotection": "NSAID in older people without gastroprotection",
    "NSAID with oral anticoagulant": "NSAID with oral anticoagulant",
    "NSAID with chronic kidney disease": "NSAID with chronic kidney disease",
    "NSAID with previous peptic ulcer without gastroprotection": "NSAID with previous peptic ulcer",
    "NSAID with heart failure": "NSAID with heart failure",
}

BMJ_FIG1_COLORS = {
    "NSAID in older people without gastroprotection": "#1f77b4",
    "NSAID with oral anticoagulant": "#f6b21a",
    "NSAID with chronic kidney disease": "#d4148e",
    "NSAID with previous peptic ulcer without gastroprotection": "#6f63b6",
    "NSAID with heart failure": "#f47a20",
}

BMJ_FIG2_SCATTER = "#1f77b4"
BMJ_FIG2_ELLIPSE = "#d4148e"
BMJ_FIG2_MEAN = "#f6b21a"


@dataclass(frozen=True)
class Figure2Summary:
    n_samples: int
    mean_cost_gbp: float
    mean_qaly: float
    probability_additional_cost: float
    probability_negative_qaly: float


def _ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def extract_figure1_workbook_data(workbook: Path) -> pd.DataFrame:
    """Extract Figure 1 event counts from cached workbook outputs.

    The workbook stores the event counts in ``Results.Summ!F22:K26`` and the
    corresponding labels in ``Results.Summ!E22:E26``. Values are counts for the
    English population over ten years.
    """
    reader = XlsmXmlReader(workbook)
    rows: list[dict[str, object]] = []
    for row in range(22, 27):
        label = reader.cell("Results.Summ", f"E{row}")
        if not isinstance(label, str):
            raise ValueError(f"Expected a model label in Results.Summ!E{row}")
        record: dict[str, object] = {"model": label}
        for col, category in zip("FGHIJK", FIG1_CATEGORIES, strict=True):
            value = reader.cell("Results.Summ", f"{col}{row}")
            if value is None:
                raise ValueError(f"Missing cached workbook value: Results.Summ!{col}{row}")
            record[category] = float(value)
        rows.append(record)
    return pd.DataFrame(rows)


def extract_figure2_workbook_data(workbook: Path) -> tuple[pd.DataFrame, pd.DataFrame, Figure2Summary]:
    """Extract Figure 2 England-level PSA cloud and workbook ellipse points.

    The cached PSA cloud is in ``PSA.Outputs!K15:L1014`` for the supplied
    workbook. The number of active rows is read from ``PSA.Data!B12``.
    """
    reader = XlsmXmlReader(workbook)
    n_samples_value = reader.cell("PSA.Data", "B12")
    if n_samples_value is None:
        raise ValueError("Missing number of simulations in PSA.Data!B12")
    n_samples = int(float(n_samples_value))
    points = []
    for row in range(15, 15 + n_samples):
        cost = reader.cell("PSA.Outputs", f"K{row}")
        qaly = reader.cell("PSA.Outputs", f"L{row}")
        if cost is None or qaly is None:
            raise ValueError(f"Missing cached PSA output in PSA.Outputs row {row}")
        points.append({"iteration": row - 14, "incremental_cost_gbp": float(cost), "incremental_qaly": float(qaly)})
    cloud = pd.DataFrame(points)

    ellipse_points = []
    for row in range(15, 116):
        cost = reader.cell("PSA.Outputs", f"O{row}")
        qaly = reader.cell("PSA.Outputs", f"P{row}")
        if cost is None or qaly is None:
            continue
        ellipse_points.append({"point": row - 14, "incremental_cost_gbp": float(cost), "incremental_qaly": float(qaly)})
    workbook_ellipse = pd.DataFrame(ellipse_points)

    summary = Figure2Summary(
        n_samples=n_samples,
        mean_cost_gbp=float(cloud["incremental_cost_gbp"].mean()),
        mean_qaly=float(cloud["incremental_qaly"].mean()),
        probability_additional_cost=float((cloud["incremental_cost_gbp"] > 0).mean()),
        probability_negative_qaly=float((cloud["incremental_qaly"] < 0).mean()),
    )
    return cloud, workbook_ellipse, summary


def confidence_ellipse(points: pd.DataFrame, level: float = 0.95, n_points: int = 101) -> pd.DataFrame:
    """Compute a bivariate normal confidence ellipse for cost and QALY samples."""
    values = points[["incremental_qaly", "incremental_cost_gbp"]].to_numpy(dtype=float)
    mean = values.mean(axis=0)
    covariance = np.cov(values, rowvar=False)
    eigenvalues, eigenvectors = np.linalg.eigh(covariance)
    order = np.argsort(eigenvalues)[::-1]
    eigenvalues = eigenvalues[order]
    eigenvectors = eigenvectors[:, order]
    radius = np.sqrt(chi2.ppf(level, df=2))
    angles = np.linspace(0.0, 2.0 * np.pi, n_points)
    unit_circle = np.vstack([np.cos(angles), np.sin(angles)])
    transform = eigenvectors @ np.diag(np.sqrt(eigenvalues))
    ellipse = mean[:, None] + radius * transform @ unit_circle
    return pd.DataFrame({"incremental_qaly": ellipse[0], "incremental_cost_gbp": ellipse[1]})


def plot_figure1(data: pd.DataFrame, output_path: Path) -> None:
    """Draw a Python version of BMJ article Figure 1."""
    order = [m for m in MODEL_ORDER if m in set(data["model"])]
    indexed = data.set_index("model").loc[order]
    x = np.arange(len(FIG1_CATEGORIES))
    bottom = np.zeros(len(FIG1_CATEGORIES), dtype=float)
    fig, ax = plt.subplots(figsize=(9.3, 5.6))
    for model in order:
        values = indexed.loc[model, FIG1_CATEGORIES].astype(float).to_numpy() / 1000.0
        ax.bar(
            x,
            values,
            bottom=bottom,
            label=FIG1_DISPLAY_LABELS[model],
            color=BMJ_FIG1_COLORS[model],
            edgecolor="none",
            width=0.58,
        )
        bottom += values
    ax.set_xticks(x)
    ax.set_xticklabels(
        [
            "Deaths",
            "Symptomatic\nulcers",
            "Serious\ngastrointestinal\nevents",
            "Strokes",
            "Acute exacerbations\nof heart failure",
            "Acute kidney\ninjuries",
        ],
        rotation=40,
        ha="right",
    )
    ax.set_ylabel("Expected no. of\nexcess events (000s)", fontweight="bold")
    ax.set_ylim(0, 8)
    ax.set_yticks([0, 2, 4, 6, 8])
    ax.grid(axis="y", color="#9e9e9e", linewidth=1.0, alpha=0.8)
    ax.set_axisbelow(True)
    ax.legend(fontsize=8, frameon=False, loc="upper left", handlelength=1.0, handletextpad=0.45)
    ax.spines[["top", "right"]].set_visible(False)
    ax.spines["left"].set_color("#707070")
    ax.spines["bottom"].set_color("#707070")
    fig.tight_layout()
    fig.savefig(output_path, dpi=220, bbox_inches="tight")
    plt.close(fig)


def plot_figure2(cloud: pd.DataFrame, ellipse: pd.DataFrame, output_path: Path) -> None:
    """Draw a Python version of BMJ article Figure 2 from cached workbook PSA."""
    x = cloud["incremental_qaly"].to_numpy() / 1000.0
    y = cloud["incremental_cost_gbp"].to_numpy() / 1_000_000.0
    ex = ellipse["incremental_qaly"].to_numpy() / 1000.0
    ey = ellipse["incremental_cost_gbp"].to_numpy() / 1_000_000.0
    fig, ax = plt.subplots(figsize=(7.4, 5.9))
    ax.scatter(x, y, s=9, alpha=0.30, linewidths=0, color=BMJ_FIG2_SCATTER)
    line95, = ax.plot(ex, ey, linewidth=1.8, color=BMJ_FIG2_ELLIPSE, label="95% CI")
    mean_pt = ax.scatter([x.mean()], [y.mean()], marker="D", s=52, facecolors=BMJ_FIG2_MEAN, edgecolors="#203040", linewidths=0.8, label="Mean", zorder=3)
    ax.axhline(0, linewidth=1.0, color="black")
    ax.axvline(0, linewidth=1.0, color="black")
    ax.set_xlim(-12, 2)
    ax.set_ylim(-40, 120)
    ax.set_xticks([-12, -10, -8, -6, -4, -2, 0, 2])
    ax.set_yticks([-40, 0, 40, 80, 120])
    ax.grid(axis="y", color="#9e9e9e", linewidth=1.0, alpha=0.8)
    ax.set_axisbelow(True)
    ax.set_xlabel("QALY impact of hazardous prescribing (000s)", fontweight="bold")
    ax.set_ylabel("Cost impact of hazardous\nprescribing (£ millions)", fontweight="bold")
    ax.legend(handles=[mean_pt, line95], labels=["Mean", "95% CI"], frameon=False, loc="upper left", ncol=2, handletextpad=0.4, columnspacing=1.2)
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(output_path, dpi=220, bbox_inches="tight")
    plt.close(fig)


def load_figure3_digitised_points(csv_path: Path) -> pd.DataFrame:
    data = pd.read_csv(csv_path)
    required = {"duration_years", "cost_impact_gbp_millions", "qaly_impact_thousands"}
    missing = required.difference(data.columns)
    if missing:
        raise ValueError(f"Figure 3 digitised CSV is missing columns: {sorted(missing)}")
    return data.sort_values("duration_years").reset_index(drop=True)


def plot_figure3_digitised(data: pd.DataFrame, output_path: Path) -> None:
    """Draw a digitised reconstruction of BMJ article Figure 3."""
    fig, axes = plt.subplots(nrows=2, ncols=1, figsize=(7.6, 7.3), sharex=True)
    axes[0].plot(data["duration_years"], data["cost_impact_gbp_millions"], marker="o", markersize=3.6)
    axes[0].axhline(0, linewidth=0.9)
    axes[0].set_ylabel("Cost impact of exposure to\nhazardous prescribing (£ millions)")
    axes[0].set_ylim(-10, 40)
    axes[1].plot(data["duration_years"], data["qaly_impact_thousands"], marker="o", markersize=3.6)
    axes[1].axhline(0, linewidth=0.9)
    axes[1].set_ylabel("QALY impact of exposure to\nhazardous prescribing (000s)")
    axes[1].set_xlabel("Duration of exposure to hazardous prescribing (years)")
    axes[1].set_ylim(-8, 2)
    axes[1].set_xlim(0, 10)
    for ax in axes:
        ax.spines[["top", "right"]].set_visible(False)
        ax.grid(axis="y", linewidth=0.5, alpha=0.6)
    fig.tight_layout()
    fig.savefig(output_path, dpi=220, bbox_inches="tight")
    plt.close(fig)


def compare_table2_to_workbook(table2_csv: Path, workbook_summary_csv: Path) -> pd.DataFrame:
    """Compare article Table 2 means with cached workbook PSA summary means."""
    published = pd.read_csv(table2_csv)
    workbook = pd.read_csv(workbook_summary_csv)
    merged = published.merge(workbook, on="model_id", suffixes=("_published", "_workbook"))
    comparisons = [
        ("hpe_cost_mean", "hpe_cost_mean_gbp"),
        ("no_hpe_cost_mean", "no_hpe_cost_mean_gbp"),
        ("incremental_cost_mean", "incremental_cost_mean_gbp"),
        ("hpe_qaly_mean", "hpe_qaly_mean"),
        ("no_hpe_qaly_mean", "no_hpe_qaly_mean"),
        ("incremental_qaly_mean", "incremental_qaly_mean"),
    ]
    rows: list[dict[str, object]] = []
    for _, row in merged.iterrows():
        for workbook_col, published_col in comparisons:
            p = float(row[f"{published_col}_published"] if f"{published_col}_published" in merged.columns else row[published_col])
            w = float(row[f"{workbook_col}_workbook"] if f"{workbook_col}_workbook" in merged.columns else row[workbook_col])
            rows.append({
                "model_id": row["model_id"],
                "metric": published_col,
                "published_value": p,
                "cached_workbook_value": w,
                "absolute_difference": abs(w - p),
            })
    return pd.DataFrame(rows)


def reproduce_all(
    workbook: Path,
    figure3_digitised_csv: Path,
    table2_csv: Path,
    workbook_summary_csv: Path,
    output_dir: Path,
) -> dict[str, object]:
    """Generate all new NSAID 2024 main-figure outputs."""
    output_dir = _ensure_dir(output_dir)

    fig1 = extract_figure1_workbook_data(workbook)
    fig1.to_csv(output_dir / "figure1_workbook_event_counts.csv", index=False)
    plot_figure1(fig1, output_dir / "figure1_expected_excess_events_workbook.png")

    cloud, workbook_ellipse, fig2_summary = extract_figure2_workbook_data(workbook)
    cloud.to_csv(output_dir / "figure2_workbook_psa_cloud.csv", index=False)
    workbook_ellipse.to_csv(output_dir / "figure2_workbook_cached_ellipse.csv", index=False)
    python_ellipse = confidence_ellipse(cloud)
    python_ellipse.to_csv(output_dir / "figure2_python_ellipse.csv", index=False)
    plot_figure2(cloud, workbook_ellipse if not workbook_ellipse.empty else python_ellipse, output_dir / "figure2_total_cost_qaly_psa_workbook.png")

    fig3 = load_figure3_digitised_points(figure3_digitised_csv)
    fig3.to_csv(output_dir / "figure3_digitised_points_used.csv", index=False)
    plot_figure3_digitised(fig3, output_dir / "figure3_exposure_duration_digitised_reconstruction.png")

    table2_comparison = compare_table2_to_workbook(table2_csv, workbook_summary_csv)
    table2_comparison.to_csv(output_dir / "table2_published_vs_cached_workbook_means.csv", index=False)

    status_rows = [
        {
            "item": "BMJ Figure 1",
            "status": "generated",
            "evidence_level": "direct cached-workbook extraction and Python redraw",
            "limitation": "The workbook values are cached outputs, not independent Python Markov-model calculations.",
        },
        {
            "item": "BMJ Figure 2",
            "status": "generated",
            "evidence_level": "direct cached-workbook England-level PSA extraction and Python redraw",
            "limitation": f"The supplied workbook stores {fig2_summary.n_samples} PSA samples; the article reports 10000 simulations.",
        },
        {
            "item": "BMJ Figure 3",
            "status": "generated",
            "evidence_level": "digitised reconstruction from the published BMJ figure",
            "limitation": "The curve is not an independent Markov-model recalculation because the workbook does not store the complete exposure-duration grid and LibreOffice cannot correctly recalculate its Excel LAMBDA formulas.",
        },
        {
            "item": "Independent Python translation of five Markov models",
            "status": "completed for deterministic analysis",
            "evidence_level": "Models A, B, C, D and E independently reconstructed and validated from workbook parameters",
            "limitation": "Independent PSA sampling remains to be implemented before claiming complete uncertainty-analysis reproduction.",
        },
    ]
    status = pd.DataFrame(status_rows)
    status.to_csv(output_dir / "reproduction_status.csv", index=False)

    summary = {
        "figure1_total_excess_deaths_cached_workbook": float(fig1["Deaths"].sum()),
        "figure1_total_acute_hf_exacerbations_cached_workbook": float(fig1["Acute exacerbations of heart failure"].sum()),
        "figure1_total_acute_kidney_injuries_cached_workbook": float(fig1["Acute kidney injuries"].sum()),
        "figure2_n_cached_workbook_psa_samples": fig2_summary.n_samples,
        "figure2_mean_cost_gbp_cached_workbook": fig2_summary.mean_cost_gbp,
        "figure2_mean_qaly_cached_workbook": fig2_summary.mean_qaly,
        "figure2_probability_additional_cost_cached_workbook": fig2_summary.probability_additional_cost,
        "figure2_probability_negative_qaly_cached_workbook": fig2_summary.probability_negative_qaly,
        "figure3_method": "digitised reconstruction from published figure",
        "independent_python_deterministic_markov_reimplementation_all_five_models": True,
        "independent_python_markov_reimplementation_model_A": True,
        "independent_python_markov_reimplementation_model_B": True,
        "independent_python_markov_reimplementation_model_C": True,
        "independent_python_markov_reimplementation_model_D": True,
        "independent_python_markov_reimplementation_model_E": True,
        "independent_python_psa_reimplementation": False,
    }
    (output_dir / "workflow_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary