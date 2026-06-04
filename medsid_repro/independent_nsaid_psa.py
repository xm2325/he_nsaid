"""PSA re-aggregation workflow for NSAID 2024 Figure 2.

This module reconstructs the England-level probabilistic sensitivity analysis
(PSA) cloud from model-level arm outcomes saved in the original workbook
``PSA.Data`` sheet. It does not yet draw stochastic parameters independently.
Instead, it uses the workbook's 1,000 cached PSA arm outcomes for each model,
then independently recomputes incremental per-person and England-level total
cost/QALY impacts.

Scientific status
-----------------
- Deterministic Models A--E are independently reimplemented elsewhere.
- This PSA workflow validates the PSA aggregation and Figure 2 scaling logic.
- It is not yet a full parameter-level independent PSA sampler.
"""
from __future__ import annotations

from pathlib import Path
from typing import Dict, Tuple
import json

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.stats import chi2

from .xlsm_reader import XlsmXmlReader

MODEL_IDS = ["A", "B", "C", "D", "E"]
MODEL_LABELS = {
    "A": "NSAID in older people without gastroprotection",
    "B": "NSAID with previous peptic ulcer without gastroprotection",
    "C": "NSAID with oral anticoagulant",
    "D": "NSAID with heart failure",
    "E": "NSAID with chronic kidney disease",
}
# Rounded published Table 3 values; exact workbook counts are read by
# ``_exact_england_hpe_counts`` for validation and figure generation.
ENGLAND_HPE_COUNTS = {"A": 107_474, "B": 6_868, "C": 23_153, "D": 8_926, "E": 15_799}

# PSA.Data columns for model-level arm outcomes:
# cost HPE, cost no HPE, QALY HPE, QALY no HPE
PSA_DATA_COLUMNS = {
    "A": ("E", "F", "H", "I"),
    "B": ("K", "L", "N", "O"),
    "C": ("Q", "R", "T", "U"),
    "D": ("W", "X", "Z", "AA"),
    "E": ("AC", "AD", "AF", "AG"),
}

# PSA.Data columns for England-level query impact by model.
# These include the workbook PSA scaling used for national burden.
PSA_QUERY_COLUMNS = {
    "A": ("AI", "AL"),
    "B": ("AO", "AR"),
    "C": ("AU", "AX"),
    "D": ("BA", "BD"),
    "E": ("BG", "BJ"),
}



def _exact_england_hpe_counts(reader: XlsmXmlReader) -> Dict[str, float]:
    """Read exact England HPE counts used by the workbook calculations."""
    return {model_id: float(reader.cell("Parameters", f"M{1115 + i}")) for i, model_id in enumerate(MODEL_IDS, start=1)}


def _read_cell_float(reader: XlsmXmlReader, sheet: str, cell: str) -> float:
    value = reader.cell(sheet, cell)
    if value is None:
        raise ValueError(f"Missing value in {sheet}!{cell}")
    return float(value)


def extract_model_level_psa(workbook_path: Path) -> pd.DataFrame:
    """Extract model-level PSA arm outcomes from ``PSA.Data``.

    Returns one row per iteration and model with arm-level cost/QALY plus
    incremental per-person and England-level impacts.
    """
    reader = XlsmXmlReader(workbook_path)
    exact_counts = _exact_england_hpe_counts(reader)
    n_samples = int(_read_cell_float(reader, "PSA.Data", "B12"))
    rows = []
    for model_id, cols in PSA_DATA_COLUMNS.items():
        c_hpe, c_no, q_hpe, q_no = cols
        count = exact_counts[model_id]
        for i in range(1, n_samples + 1):
            row = 16 + i  # row 16 is deterministic; rows 17.. are PSA draws
            cost_hpe = _read_cell_float(reader, "PSA.Data", f"{c_hpe}{row}")
            cost_no = _read_cell_float(reader, "PSA.Data", f"{c_no}{row}")
            qaly_hpe = _read_cell_float(reader, "PSA.Data", f"{q_hpe}{row}")
            qaly_no = _read_cell_float(reader, "PSA.Data", f"{q_no}{row}")
            inc_cost = cost_hpe - cost_no
            inc_qaly = qaly_hpe - qaly_no
            rows.append({
                "iteration": i,
                "model_id": model_id,
                "model_label": MODEL_LABELS[model_id],
                "england_hpe_count": count,
                "cost_hpe": cost_hpe,
                "cost_no_hpe": cost_no,
                "qaly_hpe": qaly_hpe,
                "qaly_no_hpe": qaly_no,
                "incremental_cost_per_person": inc_cost,
                "incremental_qaly_per_person": inc_qaly,
                "england_incremental_cost_gbp": inc_cost * count,
                "england_incremental_qaly": inc_qaly * count,
            })
    return pd.DataFrame(rows)


def extract_england_query_level_psa(workbook_path: Path) -> pd.DataFrame:
    """Extract England-level model impacts from ``PSA.Data``.

    These columns are the workbook's PSA national burden calculations for each
    model. They are preferred for Figure 2 reproduction because they preserve
    all workbook scaling choices used before summing to the total cloud.
    """
    reader = XlsmXmlReader(workbook_path)
    n_samples = int(_read_cell_float(reader, "PSA.Data", "B12"))
    rows = []
    for model_id, (cost_col, qaly_col) in PSA_QUERY_COLUMNS.items():
        for i in range(1, n_samples + 1):
            row = 16 + i
            rows.append({
                "iteration": i,
                "model_id": model_id,
                "model_label": MODEL_LABELS[model_id],
                "england_incremental_cost_gbp": _read_cell_float(reader, "PSA.Data", f"{cost_col}{row}"),
                "england_incremental_qaly": _read_cell_float(reader, "PSA.Data", f"{qaly_col}{row}"),
            })
    return pd.DataFrame(rows)


def aggregate_england_psa(model_level: pd.DataFrame) -> pd.DataFrame:
    """Aggregate model-level PSA rows to England-level total cost/QALY impact."""
    grouped = model_level.groupby("iteration", as_index=False).agg(
        incremental_cost_gbp=("england_incremental_cost_gbp", "sum"),
        incremental_qaly=("england_incremental_qaly", "sum"),
    )
    return grouped


def extract_workbook_total_cloud(workbook_path: Path) -> pd.DataFrame:
    """Read workbook total cloud from ``PSA.Outputs`` for validation only."""
    reader = XlsmXmlReader(workbook_path)
    n_samples = int(_read_cell_float(reader, "PSA.Data", "B12"))
    rows = []
    for i in range(1, n_samples + 1):
        row = 14 + i
        rows.append({
            "iteration": i,
            "workbook_total_cost_gbp": _read_cell_float(reader, "PSA.Outputs", f"K{row}"),
            "workbook_total_qaly": _read_cell_float(reader, "PSA.Outputs", f"L{row}"),
        })
    return pd.DataFrame(rows)


def confidence_ellipse(points: pd.DataFrame, level: float = 0.95, n_points: int = 201) -> pd.DataFrame:
    values = points[["incremental_qaly", "incremental_cost_gbp"]].to_numpy(float)
    mean = values.mean(axis=0)
    covariance = np.cov(values, rowvar=False)
    eigenvalues, eigenvectors = np.linalg.eigh(covariance)
    order = np.argsort(eigenvalues)[::-1]
    eigenvalues = eigenvalues[order]
    eigenvectors = eigenvectors[:, order]
    radius = np.sqrt(chi2.ppf(level, df=2))
    theta = np.linspace(0.0, 2.0 * np.pi, n_points)
    circle = np.vstack([np.cos(theta), np.sin(theta)])
    ellipse = mean[:, None] + radius * eigenvectors @ np.diag(np.sqrt(eigenvalues)) @ circle
    return pd.DataFrame({"incremental_qaly": ellipse[0], "incremental_cost_gbp": ellipse[1]})


def plot_figure2_from_psa(total_cloud: pd.DataFrame, ellipse: pd.DataFrame, output_path: Path) -> None:
    x = total_cloud["incremental_qaly"].to_numpy() / 1000.0
    y = total_cloud["incremental_cost_gbp"].to_numpy() / 1_000_000.0
    ex = ellipse["incremental_qaly"].to_numpy() / 1000.0
    ey = ellipse["incremental_cost_gbp"].to_numpy() / 1_000_000.0

    fig, ax = plt.subplots(figsize=(7.4, 5.9))
    ax.scatter(x, y, s=9, alpha=0.30, linewidths=0, color="#1f77b4")
    line95, = ax.plot(ex, ey, linewidth=1.8, color="#d4148e", label="95% CI")
    mean_pt = ax.scatter([x.mean()], [y.mean()], marker="D", s=52,
                         facecolors="#f6b21a", edgecolors="#203040",
                         linewidths=0.8, label="Mean", zorder=3)
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
    ax.legend(handles=[mean_pt, line95], labels=["Mean", "95% CI"],
              frameon=False, loc="upper left", ncol=2, handletextpad=0.4,
              columnspacing=1.2)
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(output_path, dpi=220, bbox_inches="tight")
    plt.close(fig)


def run_psa_reaggregation(workbook_path: Path, output_dir: Path) -> Dict[str, float]:
    output_dir.mkdir(parents=True, exist_ok=True)
    model_level = extract_model_level_psa(workbook_path)
    query_level = extract_england_query_level_psa(workbook_path)
    total = aggregate_england_psa(query_level)
    total_from_arm_outputs = aggregate_england_psa(model_level)
    workbook_total = extract_workbook_total_cloud(workbook_path)
    validation = total.merge(workbook_total, on="iteration")
    validation["cost_abs_error"] = validation["incremental_cost_gbp"] - validation["workbook_total_cost_gbp"]
    validation["qaly_abs_error"] = validation["incremental_qaly"] - validation["workbook_total_qaly"]

    ellipse = confidence_ellipse(total)
    model_level.to_csv(output_dir / "figure2_model_level_arm_psa_outputs.csv", index=False)
    query_level.to_csv(output_dir / "figure2_model_level_england_query_psa_outputs.csv", index=False)
    total_from_arm_outputs.to_csv(output_dir / "figure2_england_total_scaled_from_arm_outputs_diagnostic.csv", index=False)
    total.to_csv(output_dir / "figure2_england_total_psa_reaggregated.csv", index=False)
    validation.to_csv(output_dir / "figure2_reaggregated_vs_workbook_total_validation.csv", index=False)
    ellipse.to_csv(output_dir / "figure2_reaggregated_python_ellipse.csv", index=False)
    plot_figure2_from_psa(total, ellipse, output_dir / "figure2_reaggregated_from_model_level_psa.png")

    summary = {
        "n_iterations": int(total.shape[0]),
        "mean_incremental_cost_gbp": float(total["incremental_cost_gbp"].mean()),
        "mean_incremental_qaly": float(total["incremental_qaly"].mean()),
        "probability_additional_cost": float((total["incremental_cost_gbp"] > 0).mean()),
        "probability_negative_qaly": float((total["incremental_qaly"] < 0).mean()),
        "max_abs_cost_difference_vs_workbook_total": float(validation["cost_abs_error"].abs().max()),
        "max_abs_qaly_difference_vs_workbook_total": float(validation["qaly_abs_error"].abs().max()),
        "max_abs_cost_difference_scaled_from_arm_outputs_vs_query_total": float((total_from_arm_outputs["incremental_cost_gbp"] - total["incremental_cost_gbp"]).abs().max()),
        "max_abs_qaly_difference_scaled_from_arm_outputs_vs_query_total": float((total_from_arm_outputs["incremental_qaly"] - total["incremental_qaly"]).abs().max()),
        "scientific_status": (
            "Reaggregates workbook England-level model PSA query outputs through Python; "
            "also exports a diagnostic arm-output scaling file. This is not yet "
            "a parameter-level independent PSA sampler."
        ),
    }
    (output_dir / "figure2_psa_reaggregation_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary
