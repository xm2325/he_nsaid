"""Aggregate independently reconstructed NSAID Models A, B, C, D and E."""
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
from .independent_nsaid_d import load_model_d_inputs, run_independent_model_d, run_markov_trace as run_d_trace, summarise_trace as summarise_d
from .independent_nsaid_e import load_model_e_inputs, run_independent_model_e, run_markov_trace as run_e_trace, summarise_trace as summarise_e
from .xlsm_reader import XlsmXmlReader
from .nsaid_main_figures import FIG1_CATEGORIES, extract_figure1_workbook_data, plot_figure1

MODEL_IDS = ["A", "B", "C", "D", "E"]
MODEL_LABELS = {
    "A": "NSAID in older people without gastroprotection",
    "B": "NSAID with previous peptic ulcer without gastroprotection",
    "C": "NSAID with oral anticoagulant",
    "D": "NSAID with heart failure",
    "E": "NSAID with chronic kidney disease",
}
PUBLISHED_IDS = {
    "A": "nsaid_older_no_gastro",
    "B": "nsaid_peptic_ulcer_no_gastro",
    "C": "nsaid_oral_anticoagulant",
    "D": "nsaid_heart_failure",
    "E": "nsaid_chronic_kidney_disease",
}
# Published Table 3 estimated HPE counts in England.
ENGLAND_HPE_COUNTS = {"A": 107_474, "B": 6_868, "C": 23_153, "D": 8_926, "E": 15_799}


def _load_all_inputs(workbook_path: Path) -> Dict[str, object]:
    return {
        "A": load_gi_model_inputs(workbook_path, model_id="A"),
        "B": load_gi_model_inputs(workbook_path, model_id="B"),
        "C": load_model_c_inputs(workbook_path),
        "D": load_model_d_inputs(workbook_path),
        "E": load_model_e_inputs(workbook_path),
    }


def _summarise_model(inputs: object, model_id: str) -> tuple[Dict[str, float], Dict[str, float]]:
    if model_id in {"A", "B"}:
        return summarise_gi(inputs, run_gi_trace(inputs, "HPE")), summarise_gi(inputs, run_gi_trace(inputs, "No HPE"))
    if model_id == "C":
        return summarise_c(inputs, run_c_trace(inputs, "HPE")), summarise_c(inputs, run_c_trace(inputs, "No HPE"))
    if model_id == "D":
        return summarise_d(inputs, run_d_trace(inputs, "HPE")), summarise_d(inputs, run_d_trace(inputs, "No HPE"))
    if model_id == "E":
        return summarise_e(inputs, run_e_trace(inputs, "HPE")), summarise_e(inputs, run_e_trace(inputs, "No HPE"))
    raise ValueError(f"Unsupported model: {model_id}")


def _summaries(workbook_path: Path, model_id: str, duration: float | None = None) -> tuple[Dict[str, float], Dict[str, float]]:
    inputs = _load_all_inputs(workbook_path)[model_id]
    if duration is not None:
        inputs = replace(inputs, max_hpe_years=float(duration))
    return _summarise_model(inputs, model_id)



def build_figure1_independent_event_counts(workbook_path: Path) -> pd.DataFrame:
    """Independently reconstruct BMJ Figure 1 event counts from model traces.

    The workbook Figure 1 calculations use final death prevalence and sums of
    transient event-state occupancies over the ten-year horizon.  Because the
    transient entry states last one cycle, these sums count acute events.
    """
    r = XlsmXmlReader(workbook_path)
    exact_counts = {model_id: float(r.cell("Parameters", f"M{1115 + i}")) for i, model_id in enumerate(MODEL_IDS, start=1)}
    inputs = _load_all_inputs(workbook_path)
    rows = []
    for model_id in MODEL_IDS:
        hpe_inputs = inputs[model_id]
        if model_id in {"A", "B"}:
            hpe = run_gi_trace(hpe_inputs, "HPE")
            no_hpe = run_gi_trace(hpe_inputs, "No HPE")
            events_hpe = {
                "Deaths": float(hpe.iloc[-1]["Dead"]),
                "Symptomatic ulcers": float(hpe.iloc[:-1]["Symptomatic ulcer"].sum()),
                "Serious gastrointestinal events": float(hpe.iloc[:-1]["Serious GI event"].sum()),
            }
            events_no = {
                "Deaths": float(no_hpe.iloc[-1]["Dead"]),
                "Symptomatic ulcers": float(no_hpe.iloc[:-1]["Symptomatic ulcer"].sum()),
                "Serious gastrointestinal events": float(no_hpe.iloc[:-1]["Serious GI event"].sum()),
            }
        elif model_id == "C":
            hpe = run_c_trace(hpe_inputs, "HPE")
            no_hpe = run_c_trace(hpe_inputs, "No HPE")
            events_hpe = {
                "Deaths": float(hpe.iloc[-1]["Dead"]),
                "Symptomatic ulcers": float(hpe.iloc[:-1]["Symptomatic ulcer"].sum()),
                "Serious gastrointestinal events": float(hpe.iloc[:-1]["Serious GI event"].sum()),
                "Strokes": float(hpe.iloc[:-1][["Stroke", "Recurrent stroke"]].sum().sum()),
            }
            events_no = {
                "Deaths": float(no_hpe.iloc[-1]["Dead"]),
                "Symptomatic ulcers": float(no_hpe.iloc[:-1]["Symptomatic ulcer"].sum()),
                "Serious gastrointestinal events": float(no_hpe.iloc[:-1]["Serious GI event"].sum()),
                "Strokes": float(no_hpe.iloc[:-1][["Stroke", "Recurrent stroke"]].sum().sum()),
            }
        elif model_id == "D":
            hpe = run_d_trace(hpe_inputs, "HPE")
            no_hpe = run_d_trace(hpe_inputs, "No HPE")
            # D.Markov V4 / AL4 use rows 11:49 and sum the HF-with-HPE plus
            # HF-post-event-no-HPE occupancy summaries. The initial HPE state in
            # row 10 is intentionally excluded by the workbook summary formula.
            exac_summary_states = ["HF w HPE", "HF post event no HPE"]
            events_hpe = {"Deaths": float(hpe.iloc[-1]["Dead"]), "Acute exacerbations of heart failure": float(hpe.iloc[1:-1][exac_summary_states].sum().sum())}
            events_no = {"Deaths": float(no_hpe.iloc[-1]["Dead"]), "Acute exacerbations of heart failure": float(no_hpe.iloc[1:-1][exac_summary_states].sum().sum())}
        else:
            hpe = run_e_trace(hpe_inputs, "HPE")
            no_hpe = run_e_trace(hpe_inputs, "No HPE")
            aki_states = ["Primary care AKI", "Secondary care AKI (no RRT)", "Secondary care AKI (with RRT)"]
            death_states = ["Dead (AKI)", "Dead (other)"]
            # E.Markov V4 / AP4 use the derived death summary at row 50,
            # corresponding to trace index -2 in the 41-row 10-year trace.
            events_hpe = {"Deaths": float(hpe.iloc[-2][death_states].sum()), "Acute kidney injuries": float(hpe.iloc[:-1][aki_states].sum().sum())}
            events_no = {"Deaths": float(no_hpe.iloc[-2][death_states].sum()), "Acute kidney injuries": float(no_hpe.iloc[:-1][aki_states].sum().sum())}

        row = {"model": MODEL_LABELS[model_id]}
        for category in FIG1_CATEGORIES:
            row[category] = exact_counts[model_id] * (events_hpe.get(category, 0.0) - events_no.get(category, 0.0))
        rows.append(row)
    return pd.DataFrame(rows)


def compare_independent_figure1_to_workbook(independent: pd.DataFrame, workbook_path: Path) -> pd.DataFrame:
    cached = extract_figure1_workbook_data(workbook_path)
    joined = independent.merge(cached, on="model", suffixes=("_independent", "_workbook_cached"))
    rows = []
    for _, row in joined.iterrows():
        for category in FIG1_CATEGORIES:
            independent_value = float(row[f"{category}_independent"])
            workbook_value = float(row[f"{category}_workbook_cached"])
            rows.append({
                "model": row["model"],
                "event_category": category,
                "independent_python": independent_value,
                "workbook_cached": workbook_value,
                "absolute_error": independent_value - workbook_value,
            })
    return pd.DataFrame(rows)


def build_table2_reproduction(workbook_path: Path, table2_csv: Path) -> pd.DataFrame:
    """Independent deterministic reconstruction beside published PSA means."""
    published = pd.read_csv(table2_csv).set_index("model_id")
    inputs_by_model = _load_all_inputs(workbook_path)
    rows = []
    for model_id in MODEL_IDS:
        hpe, no_hpe = _summarise_model(inputs_by_model[model_id], model_id)
        pub = published.loc[PUBLISHED_IDS[model_id]]
        rows.append({
            "model_id": model_id,
            "label": MODEL_LABELS[model_id],
            "independent_hpe_discounted_cost_gbp": hpe["discounted_cost"],
            "independent_no_hpe_discounted_cost_gbp": no_hpe["discounted_cost"],
            "independent_incremental_discounted_cost_gbp": hpe["discounted_cost"] - no_hpe["discounted_cost"],
            "published_table2_incremental_cost_psa_mean_gbp": float(pub["incremental_cost_mean_gbp"]),
            "independent_hpe_discounted_qaly": hpe["discounted_qaly"],
            "independent_no_hpe_discounted_qaly": no_hpe["discounted_qaly"],
            "independent_incremental_discounted_qaly": hpe["discounted_qaly"] - no_hpe["discounted_qaly"],
            "published_table2_incremental_qaly_psa_mean": float(pub["incremental_qaly_mean"]),
            "note": "Independent deterministic base-case output versus published PSA mean; exact equality is not expected.",
        })
    return pd.DataFrame(rows)


def build_national_base_case(workbook_path: Path, table3_csv: Path) -> pd.DataFrame:
    """Scale all five deterministic results to published England HPE counts."""
    published = pd.read_csv(table3_csv)
    published_cost = published[(published["scenario"] == "base_case") & (published["metric"] == "total_cost_impact")].iloc[0]
    published_qaly = published[(published["scenario"] == "base_case") & (published["metric"] == "total_qaly_impact")].iloc[0]
    inputs_by_model = _load_all_inputs(workbook_path)
    rows = []
    total_cost, total_qaly = 0.0, 0.0
    for model_id in MODEL_IDS:
        hpe, no_hpe = _summarise_model(inputs_by_model[model_id], model_id)
        inc_cost = hpe["discounted_cost"] - no_hpe["discounted_cost"]
        inc_qaly = hpe["discounted_qaly"] - no_hpe["discounted_qaly"]
        scaled_cost = inc_cost * ENGLAND_HPE_COUNTS[model_id]
        scaled_qaly = inc_qaly * ENGLAND_HPE_COUNTS[model_id]
        total_cost += scaled_cost
        total_qaly += scaled_qaly
        pub_col = PUBLISHED_IDS[model_id]
        rows.append({
            "scope": model_id,
            "label": MODEL_LABELS[model_id],
            "england_hpe_count": ENGLAND_HPE_COUNTS[model_id],
            "independent_incremental_discounted_cost_per_person_gbp": inc_cost,
            "independent_incremental_discounted_qaly_per_person": inc_qaly,
            "independent_deterministic_cost_impact_gbp": scaled_cost,
            "published_table3_psa_mean_cost_impact_gbp": float(published_cost[pub_col]) * 1_000_000.0,
            "independent_deterministic_qaly_impact": scaled_qaly,
            "published_table3_psa_mean_qaly_impact": float(published_qaly[pub_col]),
        })
    rows.append({
        "scope": "A+B+C+D+E total",
        "label": "England total for all five independently reconstructed models",
        "england_hpe_count": sum(ENGLAND_HPE_COUNTS.values()),
        "independent_incremental_discounted_cost_per_person_gbp": np.nan,
        "independent_incremental_discounted_qaly_per_person": np.nan,
        "independent_deterministic_cost_impact_gbp": total_cost,
        "published_table3_psa_mean_cost_impact_gbp": float(published_cost["total"]) * 1_000_000.0,
        "independent_deterministic_qaly_impact": total_qaly,
        "published_table3_psa_mean_qaly_impact": float(published_qaly["total"]),
    })
    return pd.DataFrame(rows)


def exposure_duration_sensitivity_abcde(workbook_path: Path) -> pd.DataFrame:
    """Recalculate full Figure 3 sensitivity inputs using all five models."""
    base = _load_all_inputs(workbook_path)
    rows = []
    for duration in np.arange(0.25, 10.0 + 0.001, 0.25):
        total_cost, total_qaly = 0.0, 0.0
        for model_id in MODEL_IDS:
            inputs = replace(base[model_id], max_hpe_years=float(duration))
            hpe, no_hpe = _summarise_model(inputs, model_id)
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
            "scope": "A+B+C+D+E total",
            "label": "England total for all five independently reconstructed models",
            "incremental_discounted_cost_gbp": np.nan,
            "incremental_discounted_qaly": np.nan,
            "england_hpe_count": sum(ENGLAND_HPE_COUNTS.values()),
            "england_cost_impact_gbp": total_cost,
            "england_qaly_impact": total_qaly,
        })
    return pd.DataFrame(rows)


def plot_full_exposure_duration_sensitivity(data: pd.DataFrame, output_path: Path) -> None:
    total = data[data["scope"] == "A+B+C+D+E total"].copy()
    fig, axes = plt.subplots(nrows=2, ncols=1, figsize=(7.0, 6.7), sharex=True)
    axes[0].plot(total["duration_years"], total["england_cost_impact_gbp"] / 1_000_000.0, marker="o", markersize=3.0, linewidth=1.5)
    axes[0].axhline(0.0, linewidth=0.9, color="black")
    axes[0].set_ylabel("Cost impact of exposure to\nhazardous prescribing (£ millions)")
    axes[0].set_ylim(-10, 40)
    axes[1].plot(total["duration_years"], total["england_qaly_impact"] / 1000.0, marker="o", markersize=3.0, linewidth=1.5)
    axes[1].axhline(0.0, linewidth=0.9, color="black")
    axes[1].set_ylabel("QALY impact of exposure to\nhazardous prescribing (000s)")
    axes[1].set_xlabel("Duration of exposure to hazardous prescribing (years)")
    axes[1].set_ylim(-8, 2)
    axes[1].set_xlim(0, 10)
    for ax in axes:
        ax.grid(axis="y", linewidth=0.5, alpha=0.6)
        ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(output_path, dpi=220, bbox_inches="tight")
    plt.close(fig)


def build_figure3_digitised_comparison(sensitivity: pd.DataFrame, digitised_csv: Path) -> pd.DataFrame:
    independent = sensitivity[sensitivity["scope"] == "A+B+C+D+E total"][["duration_years", "england_cost_impact_gbp", "england_qaly_impact"]].copy()
    independent["independent_cost_impact_gbp_millions"] = independent["england_cost_impact_gbp"] / 1_000_000.0
    independent["independent_qaly_impact_thousands"] = independent["england_qaly_impact"] / 1000.0
    digitised = pd.read_csv(digitised_csv)
    merged = independent.merge(digitised, on="duration_years", how="inner")
    merged["cost_difference_millions_independent_minus_digitised"] = merged["independent_cost_impact_gbp_millions"] - merged["cost_impact_gbp_millions"]
    merged["qaly_difference_thousands_independent_minus_digitised"] = merged["independent_qaly_impact_thousands"] - merged["qaly_impact_thousands"]
    return merged


def plot_figure3_digitised_comparison(comparison: pd.DataFrame, output_path: Path) -> None:
    fig, axes = plt.subplots(nrows=2, ncols=1, figsize=(7.0, 6.7), sharex=True)
    axes[0].plot(comparison["duration_years"], comparison["independent_cost_impact_gbp_millions"], marker="o", markersize=2.8, linewidth=1.5, label="Independent Python")
    axes[0].plot(comparison["duration_years"], comparison["cost_impact_gbp_millions"], marker="x", markersize=3.2, linewidth=1.0, label="Published figure digitisation")
    axes[0].set_ylabel("Cost impact (£ millions)")
    axes[0].legend(frameon=False, fontsize=8)
    axes[1].plot(comparison["duration_years"], comparison["independent_qaly_impact_thousands"], marker="o", markersize=2.8, linewidth=1.5, label="Independent Python")
    axes[1].plot(comparison["duration_years"], comparison["qaly_impact_thousands"], marker="x", markersize=3.2, linewidth=1.0, label="Published figure digitisation")
    axes[1].set_ylabel("QALY impact (000s)")
    axes[1].set_xlabel("Duration of exposure to hazardous prescribing (years)")
    for ax in axes:
        ax.grid(axis="y", linewidth=0.5, alpha=0.6)
        ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(output_path, dpi=220, bbox_inches="tight")
    plt.close(fig)


def run_independent_models_abcde(workbook_path: Path, table2_csv: Path, table3_csv: Path, figure3_digitised_csv: Path, output_dir: Path) -> Dict[str, object]:
    output_dir.mkdir(parents=True, exist_ok=True)
    runners = {
        "A": lambda out: run_independent_gi_model(workbook_path, out, model_id="A"),
        "B": lambda out: run_independent_gi_model(workbook_path, out, model_id="B"),
        "C": lambda out: run_independent_model_c(workbook_path, out),
        "D": lambda out: run_independent_model_d(workbook_path, out),
        "E": lambda out: run_independent_model_e(workbook_path, out),
    }
    for model_id in MODEL_IDS:
        runners[model_id](output_dir / f"independent_model_{model_id}")

    figure1 = build_figure1_independent_event_counts(workbook_path)
    figure1.to_csv(output_dir / "figure1_independent_expected_excess_events_all_five_models.csv", index=False)
    plot_figure1(figure1, output_dir / "figure1_independent_expected_excess_events_all_five_models.png")
    figure1_comparison = compare_independent_figure1_to_workbook(figure1, workbook_path)
    figure1_comparison.to_csv(output_dir / "figure1_independent_vs_workbook_cached_comparison.csv", index=False)

    table2 = build_table2_reproduction(workbook_path, table2_csv)
    table2.to_csv(output_dir / "table2_deterministic_reproduction_all_five_models.csv", index=False)
    national = build_national_base_case(workbook_path, table3_csv)
    national.to_csv(output_dir / "table3_england_base_case_all_five_models.csv", index=False)
    sensitivity = exposure_duration_sensitivity_abcde(workbook_path)
    sensitivity.to_csv(output_dir / "figure3_independent_exposure_duration_sensitivity_all_five_models.csv", index=False)
    plot_full_exposure_duration_sensitivity(sensitivity, output_dir / "figure3_independent_exposure_duration_sensitivity_all_five_models.png")
    comparison = build_figure3_digitised_comparison(sensitivity, figure3_digitised_csv)
    comparison.to_csv(output_dir / "figure3_independent_vs_published_digitised_comparison.csv", index=False)
    plot_figure3_digitised_comparison(comparison, output_dir / "figure3_independent_vs_published_digitised_comparison.png")

    validation_rows = []
    for model_id in MODEL_IDS:
        validation = json.loads((output_dir / f"independent_model_{model_id}" / f"independent_model_{model_id}_validation_summary.json").read_text())
        validation_rows.append({"model_id": model_id, "label": MODEL_LABELS[model_id], **validation})
    validation_df = pd.DataFrame(validation_rows)
    validation_df.to_csv(output_dir / "independent_models_A_B_C_D_E_validation_summary.csv", index=False)
    total = national[national["scope"] == "A+B+C+D+E total"].iloc[0]
    summary = {
        "independent_models_completed": MODEL_IDS,
        "all_trace_errors_below_1e-12": bool(validation_df["all_trace_errors_below_1e-12"].all()),
        "all_reward_errors_below_1e-10": bool(validation_df["all_reward_errors_below_1e-10"].all()),
        "figure1_scope": "All five independently reconstructed deterministic models",
        "figure1_max_absolute_error_vs_workbook_cached": float(figure1_comparison["absolute_error"].abs().max()),
        "figure3_scope": "All five independently reconstructed deterministic models",
        "deterministic_england_total_cost_impact_gbp": float(total["independent_deterministic_cost_impact_gbp"]),
        "deterministic_england_total_qaly_impact": float(total["independent_deterministic_qaly_impact"]),
        "published_table3_psa_mean_total_cost_impact_gbp": float(total["published_table3_psa_mean_cost_impact_gbp"]),
        "published_table3_psa_mean_total_qaly_impact": float(total["published_table3_psa_mean_qaly_impact"]),
        "figure3_digitised_cost_rmse_gbp_millions": float(np.sqrt(np.mean(comparison["cost_difference_millions_independent_minus_digitised"] ** 2))),
        "figure3_digitised_qaly_rmse_thousands": float(np.sqrt(np.mean(comparison["qaly_difference_thousands_independent_minus_digitised"] ** 2))),
        "psa_reimplementation_completed": False,
    }
    (output_dir / "independent_models_A_B_C_D_E_workflow_summary.json").write_text(json.dumps(summary, indent=2))
    return summary
