"""Aggregate independently reconstructed NSAID Models A, B and C."""
from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Dict
import json

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from .independent_nsaid_gi import load_gi_model_inputs, run_independent_gi_model, run_markov_trace as run_gi_trace, summarise_trace as summarise_gi
from .independent_nsaid_c import load_model_c_inputs, run_independent_model_c, run_markov_trace as run_c_trace, summarise_trace as summarise_c

MODEL_LABELS = {
    "A": "NSAID in older people without gastroprotection",
    "B": "NSAID with previous peptic ulcer without gastroprotection",
    "C": "NSAID with oral anticoagulant",
}

# Published Table 3 estimated numbers of people affected by an HPE in England.
ENGLAND_HPE_COUNTS = {"A": 107_474, "B": 6_868, "C": 23_153}
PUBLISHED_IDS = {
    "A": "nsaid_older_no_gastro",
    "B": "nsaid_peptic_ulcer_no_gastro",
    "C": "nsaid_oral_anticoagulant",
}


def _summaries(workbook_path: Path, model_id: str, duration: float | None = None) -> tuple[Dict[str, float], Dict[str, float]]:
    if model_id in {"A", "B"}:
        inputs = load_gi_model_inputs(workbook_path, model_id=model_id)
        if duration is not None:
            inputs = replace(inputs, max_hpe_years=float(duration))
        return summarise_gi(inputs, run_gi_trace(inputs, "HPE")), summarise_gi(inputs, run_gi_trace(inputs, "No HPE"))
    if model_id == "C":
        inputs = load_model_c_inputs(workbook_path)
        if duration is not None:
            inputs = replace(inputs, max_hpe_years=float(duration))
        return summarise_c(inputs, run_c_trace(inputs, "HPE")), summarise_c(inputs, run_c_trace(inputs, "No HPE"))
    raise ValueError(f"Unsupported model: {model_id}")


def build_partial_table2_reproduction(workbook_path: Path, table2_csv: Path) -> pd.DataFrame:
    published = pd.read_csv(table2_csv).set_index("model_id")
    rows = []
    for model_id in ["A", "B", "C"]:
        hpe, no_hpe = _summaries(workbook_path, model_id)
        inc_cost = hpe["discounted_cost"] - no_hpe["discounted_cost"]
        inc_qaly = hpe["discounted_qaly"] - no_hpe["discounted_qaly"]
        pub = published.loc[PUBLISHED_IDS[model_id]]
        rows.append({
            "model_id": model_id,
            "label": MODEL_LABELS[model_id],
            "independent_hpe_discounted_cost_gbp": hpe["discounted_cost"],
            "independent_no_hpe_discounted_cost_gbp": no_hpe["discounted_cost"],
            "independent_incremental_discounted_cost_gbp": inc_cost,
            "published_table2_incremental_cost_mean_gbp": float(pub["incremental_cost_mean_gbp"]),
            "independent_hpe_discounted_qaly": hpe["discounted_qaly"],
            "independent_no_hpe_discounted_qaly": no_hpe["discounted_qaly"],
            "independent_incremental_discounted_qaly": inc_qaly,
            "published_table2_incremental_qaly_mean": float(pub["incremental_qaly_mean"]),
            "note": "Independent deterministic base-case output versus published PSA mean from Table 2; small differences are expected.",
        })
    return pd.DataFrame(rows)


def build_partial_national_base_case(workbook_path: Path, table3_csv: Path) -> pd.DataFrame:
    """Scale deterministic Model A-C results to published England HPE counts."""
    published = pd.read_csv(table3_csv)
    published_cost = published[(published["scenario"] == "base_case") & (published["metric"] == "total_cost_impact")].iloc[0]
    published_qaly = published[(published["scenario"] == "base_case") & (published["metric"] == "total_qaly_impact")].iloc[0]
    published_cols = {"A": "nsaid_older_no_gastro", "B": "nsaid_peptic_ulcer_no_gastro", "C": "nsaid_oral_anticoagulant"}
    rows = []
    total_cost = 0.0
    total_qaly = 0.0
    for model_id in ["A", "B", "C"]:
        hpe, no_hpe = _summaries(workbook_path, model_id)
        scaled_cost = (hpe["discounted_cost"] - no_hpe["discounted_cost"]) * ENGLAND_HPE_COUNTS[model_id]
        scaled_qaly = (hpe["discounted_qaly"] - no_hpe["discounted_qaly"]) * ENGLAND_HPE_COUNTS[model_id]
        total_cost += scaled_cost
        total_qaly += scaled_qaly
        col = published_cols[model_id]
        rows.append({
            "scope": model_id,
            "label": MODEL_LABELS[model_id],
            "england_hpe_count": ENGLAND_HPE_COUNTS[model_id],
            "independent_deterministic_cost_impact_gbp": scaled_cost,
            "published_table3_psa_mean_cost_impact_gbp": float(published_cost[col]) * 1_000_000.0,
            "independent_deterministic_qaly_impact": scaled_qaly,
            "published_table3_psa_mean_qaly_impact": float(published_qaly[col]),
        })
    rows.append({
        "scope": "A+B+C partial total",
        "label": "Partial England total for independently reconstructed Models A, B and C only",
        "england_hpe_count": sum(ENGLAND_HPE_COUNTS.values()),
        "independent_deterministic_cost_impact_gbp": total_cost,
        "published_table3_psa_mean_cost_impact_gbp": sum(float(published_cost[published_cols[m]]) for m in ["A", "B", "C"]) * 1_000_000.0,
        "independent_deterministic_qaly_impact": total_qaly,
        "published_table3_psa_mean_qaly_impact": sum(float(published_qaly[published_cols[m]]) for m in ["A", "B", "C"]),
    })
    return pd.DataFrame(rows)


def exposure_duration_sensitivity_abc(workbook_path: Path) -> pd.DataFrame:
    gi_base = {model_id: load_gi_model_inputs(workbook_path, model_id=model_id) for model_id in ["A", "B"]}
    c_base = load_model_c_inputs(workbook_path)
    rows = []
    for duration in np.arange(0.25, 10.0 + 0.001, 0.25):
        total_cost = 0.0
        total_qaly = 0.0
        for model_id in ["A", "B", "C"]:
            if model_id in {"A", "B"}:
                inputs = replace(gi_base[model_id], max_hpe_years=float(duration))
                hpe = summarise_gi(inputs, run_gi_trace(inputs, "HPE"))
                no_hpe = summarise_gi(inputs, run_gi_trace(inputs, "No HPE"))
            else:
                inputs = replace(c_base, max_hpe_years=float(duration))
                hpe = summarise_c(inputs, run_c_trace(inputs, "HPE"))
                no_hpe = summarise_c(inputs, run_c_trace(inputs, "No HPE"))
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
            "scope": "A+B+C partial total",
            "label": "Partial England total for independently reconstructed Models A, B and C only",
            "incremental_discounted_cost_gbp": np.nan,
            "incremental_discounted_qaly": np.nan,
            "england_hpe_count": sum(ENGLAND_HPE_COUNTS.values()),
            "england_cost_impact_gbp": total_cost,
            "england_qaly_impact": total_qaly,
        })
    return pd.DataFrame(rows)


def plot_partial_exposure_duration_sensitivity(data: pd.DataFrame, output_path: Path) -> None:
    total = data[data["scope"] == "A+B+C partial total"].copy()
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
    fig.suptitle("Independent Models A+B+C only: partial sensitivity curve", fontsize=11)
    fig.tight_layout()
    fig.savefig(output_path, dpi=220, bbox_inches="tight")
    plt.close(fig)


def run_independent_models_abc(workbook_path: Path, table2_csv: Path, output_dir: Path, table3_csv: Path | None = None) -> Dict[str, object]:
    output_dir.mkdir(parents=True, exist_ok=True)
    model_outputs = {
        "A": run_independent_gi_model(workbook_path, output_dir / "independent_model_A", model_id="A"),
        "B": run_independent_gi_model(workbook_path, output_dir / "independent_model_B", model_id="B"),
        "C": run_independent_model_c(workbook_path, output_dir / "independent_model_C"),
    }

    table2 = build_partial_table2_reproduction(workbook_path, table2_csv)
    table2.to_csv(output_dir / "partial_table2_deterministic_reproduction_models_A_B_C.csv", index=False)
    if table3_csv is not None:
        national = build_partial_national_base_case(workbook_path, table3_csv)
        national.to_csv(output_dir / "partial_table3_england_base_case_models_A_B_C.csv", index=False)
    sensitivity = exposure_duration_sensitivity_abc(workbook_path)
    sensitivity.to_csv(output_dir / "partial_figure3_exposure_duration_sensitivity_models_A_B_C.csv", index=False)
    plot_partial_exposure_duration_sensitivity(sensitivity, output_dir / "partial_figure3_exposure_duration_sensitivity_models_A_B_C.png")

    validation_rows = []
    for model_id in ["A", "B", "C"]:
        validation = json.loads((output_dir / f"independent_model_{model_id}" / f"independent_model_{model_id}_validation_summary.json").read_text())
        validation_rows.append({"model_id": model_id, "label": MODEL_LABELS[model_id], **validation})
    validation_df = pd.DataFrame(validation_rows)
    validation_df.to_csv(output_dir / "independent_models_A_B_C_validation_summary.csv", index=False)

    summary = {
        "independent_models_completed": ["A", "B", "C"],
        "all_trace_errors_below_1e-12": bool(validation_df["all_trace_errors_below_1e-12"].all()),
        "all_reward_errors_below_1e-10": bool(validation_df["all_reward_errors_below_1e-10"].all()),
        "partial_figure3_scope": "Models A+B+C only; Models D and E are not included",
    }
    (output_dir / "independent_models_A_B_C_workflow_summary.json").write_text(json.dumps(summary, indent=2))
    return summary
