"""Aggregate independently reconstructed NSAID gastrointestinal models A and B.

This module reports deterministic validation and a partial exposure-duration
sensitivity analysis for the two gastrointestinal models.  The A+B sensitivity
curve is intentionally labelled partial: it is not a reproduction of the BMJ
article's total Figure 3 until models C, D and E are also independently rebuilt.
"""
from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Dict
import json

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

from .independent_nsaid_gi import (
    load_gi_model_inputs,
    run_independent_gi_model,
    run_markov_trace,
    summarise_trace,
)

MODEL_LABELS = {
    "A": "NSAID in older people without gastroprotection",
    "B": "NSAID with previous peptic ulcer without gastroprotection",
}

# Published Table 3 estimated numbers of people affected by an HPE in England.
# These counts are used only for scaling the partial A+B sensitivity curve.
ENGLAND_HPE_COUNTS = {
    "A": 107_474,
    "B": 6_868,
}


def _incremental(summary_hpe: Dict[str, float], summary_no_hpe: Dict[str, float]) -> Dict[str, float]:
    return {metric: float(summary_hpe[metric] - summary_no_hpe[metric]) for metric in summary_hpe}


def build_partial_table2_reproduction(workbook_path: Path, table2_csv: Path) -> pd.DataFrame:
    published = pd.read_csv(table2_csv)
    published_by_id = published.set_index("model_id")
    mapping = {
        "A": "nsaid_older_no_gastro",
        "B": "nsaid_peptic_ulcer_no_gastro",
    }
    rows = []
    for model_id, published_id in mapping.items():
        inputs = load_gi_model_inputs(workbook_path, model_id=model_id)
        hpe = summarise_trace(inputs, run_markov_trace(inputs, "HPE"))
        no_hpe = summarise_trace(inputs, run_markov_trace(inputs, "No HPE"))
        inc = _incremental(hpe, no_hpe)
        pub = published_by_id.loc[published_id]
        rows.append({
            "model_id": model_id,
            "label": MODEL_LABELS[model_id],
            "independent_hpe_discounted_cost_gbp": hpe["discounted_cost"],
            "independent_no_hpe_discounted_cost_gbp": no_hpe["discounted_cost"],
            "independent_incremental_discounted_cost_gbp": inc["discounted_cost"],
            "published_table2_incremental_cost_mean_gbp": float(pub["incremental_cost_mean_gbp"]),
            "independent_hpe_discounted_qaly": hpe["discounted_qaly"],
            "independent_no_hpe_discounted_qaly": no_hpe["discounted_qaly"],
            "independent_incremental_discounted_qaly": inc["discounted_qaly"],
            "published_table2_incremental_qaly_mean": float(pub["incremental_qaly_mean"]),
            "note": "Independent deterministic base-case output versus published PSA mean from Table 2; small differences are expected.",
        })
    return pd.DataFrame(rows)


def exposure_duration_sensitivity_ab(workbook_path: Path) -> pd.DataFrame:
    durations = np.arange(0.25, 10.0 + 0.001, 0.25)
    base_inputs = {model_id: load_gi_model_inputs(workbook_path, model_id=model_id) for model_id in ["A", "B"]}
    rows = []
    for duration in durations:
        total_cost = 0.0
        total_qaly = 0.0
        for model_id in ["A", "B"]:
            inputs = replace(base_inputs[model_id], max_hpe_years=float(duration))
            hpe = summarise_trace(inputs, run_markov_trace(inputs, "HPE"))
            no_hpe = summarise_trace(inputs, run_markov_trace(inputs, "No HPE"))
            inc_cost = hpe["discounted_cost"] - no_hpe["discounted_cost"]
            inc_qaly = hpe["discounted_qaly"] - no_hpe["discounted_qaly"]
            scaled_cost = inc_cost * ENGLAND_HPE_COUNTS[model_id]
            scaled_qaly = inc_qaly * ENGLAND_HPE_COUNTS[model_id]
            total_cost += scaled_cost
            total_qaly += scaled_qaly
            rows.append({
                "duration_years": float(duration),
                "scope": model_id,
                "label": MODEL_LABELS[model_id],
                "incremental_discounted_cost_gbp": inc_cost,
                "incremental_discounted_qaly": inc_qaly,
                "england_hpe_count": ENGLAND_HPE_COUNTS[model_id],
                "england_cost_impact_gbp": scaled_cost,
                "england_qaly_impact": scaled_qaly,
            })
        rows.append({
            "duration_years": float(duration),
            "scope": "A+B partial total",
            "label": "Partial England total for independently reconstructed GI models A and B only",
            "incremental_discounted_cost_gbp": np.nan,
            "incremental_discounted_qaly": np.nan,
            "england_hpe_count": ENGLAND_HPE_COUNTS["A"] + ENGLAND_HPE_COUNTS["B"],
            "england_cost_impact_gbp": total_cost,
            "england_qaly_impact": total_qaly,
        })
    return pd.DataFrame(rows)


def plot_partial_exposure_duration_sensitivity(data: pd.DataFrame, output_path: Path) -> None:
    total = data[data["scope"] == "A+B partial total"].copy()
    fig, axes = plt.subplots(nrows=2, ncols=1, figsize=(7.4, 7.2), sharex=True)
    axes[0].plot(total["duration_years"], total["england_cost_impact_gbp"] / 1_000_000.0, marker="o", markersize=3.0)
    axes[0].axhline(0.0, linewidth=0.9)
    axes[0].set_ylabel("Partial cost impact (£ millions)")
    axes[1].plot(total["duration_years"], total["england_qaly_impact"] / 1000.0, marker="o", markersize=3.0)
    axes[1].axhline(0.0, linewidth=0.9)
    axes[1].set_ylabel("Partial QALY impact (000s)")
    axes[1].set_xlabel("Duration of exposure to hazardous prescribing (years)")
    for ax in axes:
        ax.grid(axis="y", linewidth=0.5, alpha=0.6)
        ax.spines[["top", "right"]].set_visible(False)
    fig.suptitle("Independent A+B gastrointestinal models only: partial sensitivity curve", fontsize=11)
    fig.tight_layout()
    fig.savefig(output_path, dpi=220, bbox_inches="tight")
    plt.close(fig)


def run_independent_models_ab(workbook_path: Path, table2_csv: Path, output_dir: Path) -> Dict[str, object]:
    output_dir.mkdir(parents=True, exist_ok=True)
    model_outputs = {}
    for model_id in ["A", "B"]:
        model_outputs[model_id] = run_independent_gi_model(
            workbook_path=workbook_path,
            output_dir=output_dir / f"independent_model_{model_id}",
            model_id=model_id,
        )

    table2 = build_partial_table2_reproduction(workbook_path, table2_csv)
    table2.to_csv(output_dir / "partial_table2_deterministic_reproduction_models_A_B.csv", index=False)

    sensitivity = exposure_duration_sensitivity_ab(workbook_path)
    sensitivity.to_csv(output_dir / "partial_figure3_exposure_duration_sensitivity_models_A_B.csv", index=False)
    plot_partial_exposure_duration_sensitivity(
        sensitivity,
        output_dir / "partial_figure3_exposure_duration_sensitivity_models_A_B.png",
    )

    validation_rows = []
    for model_id in ["A", "B"]:
        val_path = output_dir / f"independent_model_{model_id}" / f"independent_model_{model_id}_validation_summary.json"
        validation = json.loads(val_path.read_text())
        validation_rows.append({"model_id": model_id, "label": MODEL_LABELS[model_id], **validation})
    validation_df = pd.DataFrame(validation_rows)
    validation_df.to_csv(output_dir / "independent_models_A_B_validation_summary.csv", index=False)

    summary = {
        "independent_models_completed": ["A", "B"],
        "all_trace_errors_below_1e-12": bool(validation_df["all_trace_errors_below_1e-12"].all()),
        "all_reward_errors_below_1e-10": bool(validation_df["all_reward_errors_below_1e-10"].all()),
        "partial_figure3_scope": "A+B gastrointestinal models only; models C, D and E are not included",
    }
    (output_dir / "independent_models_A_B_workflow_summary.json").write_text(json.dumps(summary, indent=2))
    return summary
