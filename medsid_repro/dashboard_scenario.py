"""Shared scenario engine for the dynamic MedSID NSAID dashboards.

The Python Streamlit app can either use the exported scenario contract for fast
interaction or call the validated Python formula engines directly. The R Shiny
app reads the same versioned scenario contract.

The intervention calculation is intentionally simple and transparent:
the avoided burden equals the baseline HPE burden multiplied by intervention
uptake and intervention effectiveness. This is a scenario-exploration layer,
not an additional causal-effect model.
"""
from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Dict, Iterable, Mapping, Sequence

import numpy as np
import pandas as pd

from .independent_nsaid_abcde import (
    MODEL_IDS,
    MODEL_LABELS,
    PUBLISHED_IDS,
    _load_all_inputs,
    _summarise_model,
    run_gi_trace,
    run_c_trace,
    run_d_trace,
    run_e_trace,
)
from .xlsm_reader import XlsmXmlReader

EVENT_CATEGORIES = [
    "Deaths",
    "Symptomatic ulcers",
    "Serious gastrointestinal events",
    "Strokes",
    "Acute exacerbations of heart failure",
    "Acute kidney injuries",
]
EVENT_SLUGS = {
    "Deaths": "deaths",
    "Symptomatic ulcers": "symptomatic_ulcers",
    "Serious gastrointestinal events": "serious_gastrointestinal_events",
    "Strokes": "strokes",
    "Acute exacerbations of heart failure": "acute_exacerbations_of_heart_failure",
    "Acute kidney injuries": "acute_kidney_injuries",
}


def exact_england_hpe_counts(workbook_path: Path) -> Dict[str, float]:
    reader = XlsmXmlReader(workbook_path)
    return {
        model_id: float(reader.cell("Parameters", f"M{1115 + index}"))
        for index, model_id in enumerate(MODEL_IDS, start=1)
    }


def _event_probabilities(inputs: object, model_id: str) -> tuple[Dict[str, float], Dict[str, float]]:
    """Return cumulative event burdens per exposed person for HPE and No-HPE arms."""
    if model_id in {"A", "B"}:
        hpe = run_gi_trace(inputs, "HPE")
        no_hpe = run_gi_trace(inputs, "No HPE")
        hpe_events = {
            "Deaths": float(hpe.iloc[-1]["Dead"]),
            "Symptomatic ulcers": float(hpe.iloc[:-1]["Symptomatic ulcer"].sum()),
            "Serious gastrointestinal events": float(hpe.iloc[:-1]["Serious GI event"].sum()),
        }
        no_events = {
            "Deaths": float(no_hpe.iloc[-1]["Dead"]),
            "Symptomatic ulcers": float(no_hpe.iloc[:-1]["Symptomatic ulcer"].sum()),
            "Serious gastrointestinal events": float(no_hpe.iloc[:-1]["Serious GI event"].sum()),
        }
    elif model_id == "C":
        hpe = run_c_trace(inputs, "HPE")
        no_hpe = run_c_trace(inputs, "No HPE")
        hpe_events = {
            "Deaths": float(hpe.iloc[-1]["Dead"]),
            "Symptomatic ulcers": float(hpe.iloc[:-1]["Symptomatic ulcer"].sum()),
            "Serious gastrointestinal events": float(hpe.iloc[:-1]["Serious GI event"].sum()),
            "Strokes": float(hpe.iloc[:-1][["Stroke", "Recurrent stroke"]].sum().sum()),
        }
        no_events = {
            "Deaths": float(no_hpe.iloc[-1]["Dead"]),
            "Symptomatic ulcers": float(no_hpe.iloc[:-1]["Symptomatic ulcer"].sum()),
            "Serious gastrointestinal events": float(no_hpe.iloc[:-1]["Serious GI event"].sum()),
            "Strokes": float(no_hpe.iloc[:-1][["Stroke", "Recurrent stroke"]].sum().sum()),
        }
    elif model_id == "D":
        hpe = run_d_trace(inputs, "HPE")
        no_hpe = run_d_trace(inputs, "No HPE")
        exac_states = ["HF w HPE", "HF post event no HPE"]
        hpe_events = {
            "Deaths": float(hpe.iloc[-1]["Dead"]),
            "Acute exacerbations of heart failure": float(hpe.iloc[1:-1][exac_states].sum().sum()),
        }
        no_events = {
            "Deaths": float(no_hpe.iloc[-1]["Dead"]),
            "Acute exacerbations of heart failure": float(no_hpe.iloc[1:-1][exac_states].sum().sum()),
        }
    elif model_id == "E":
        hpe = run_e_trace(inputs, "HPE")
        no_hpe = run_e_trace(inputs, "No HPE")
        aki_states = ["Primary care AKI", "Secondary care AKI (no RRT)", "Secondary care AKI (with RRT)"]
        death_states = ["Dead (AKI)", "Dead (other)"]
        hpe_events = {
            "Deaths": float(hpe.iloc[-2][death_states].sum()),
            "Acute kidney injuries": float(hpe.iloc[:-1][aki_states].sum().sum()),
        }
        no_events = {
            "Deaths": float(no_hpe.iloc[-2][death_states].sum()),
            "Acute kidney injuries": float(no_hpe.iloc[:-1][aki_states].sum().sum()),
        }
    else:
        raise ValueError(f"Unsupported model: {model_id}")

    return hpe_events, no_events


def calculate_model_row(inputs: object, model_id: str, duration_years: float, default_hpe_count: float) -> Dict[str, float | str]:
    scenario_inputs = replace(inputs, max_hpe_years=float(duration_years))
    hpe, no_hpe = _summarise_model(scenario_inputs, model_id)
    hpe_events, no_events = _event_probabilities(scenario_inputs, model_id)
    row: Dict[str, float | str] = {
        "contract_version": "v13",
        "duration_years": float(duration_years),
        "model_id": model_id,
        "model_label": MODEL_LABELS[model_id],
        "default_england_hpe_count": float(default_hpe_count),
        "incremental_discounted_cost_per_person_gbp": float(hpe["discounted_cost"] - no_hpe["discounted_cost"]),
        "incremental_discounted_qaly_per_person": float(hpe["discounted_qaly"] - no_hpe["discounted_qaly"]),
    }
    for category in EVENT_CATEGORIES:
        slug = EVENT_SLUGS[category]
        row[f"excess_event_{slug}_per_person"] = float(hpe_events.get(category, 0.0) - no_events.get(category, 0.0))
    return row


def build_dashboard_contract(workbook_path: Path, durations: Iterable[float] | None = None) -> pd.DataFrame:
    """Generate the versioned dashboard contract from live Python formula engines."""
    if durations is None:
        durations = np.arange(0.25, 10.0 + 0.001, 0.25)
    base_inputs = _load_all_inputs(workbook_path)
    default_counts = exact_england_hpe_counts(workbook_path)
    rows = []
    for duration in durations:
        for model_id in MODEL_IDS:
            rows.append(calculate_model_row(base_inputs[model_id], model_id, float(duration), default_counts[model_id]))
    return pd.DataFrame(rows)


def _select_duration_rows(contract: pd.DataFrame, duration_years: float, selected_models: Sequence[str]) -> pd.DataFrame:
    available = sorted(contract["duration_years"].unique())
    nearest = min(available, key=lambda value: abs(float(value) - float(duration_years)))
    if abs(float(nearest) - float(duration_years)) > 1e-8:
        raise ValueError(f"Duration {duration_years} is not available in the dashboard contract")
    rows = contract[(contract["duration_years"].sub(float(nearest)).abs() < 1e-8) & contract["model_id"].isin(selected_models)].copy()
    if rows.empty:
        raise ValueError("At least one model must be selected")
    return rows


def calculate_scenario_from_contract(
    contract: pd.DataFrame,
    duration_years: float,
    selected_models: Sequence[str],
    model_counts: Mapping[str, float] | None = None,
    uptake: float = 0.60,
    effectiveness: float = 0.25,
    implementation_cost_per_approached_hpe_gbp: float = 0.0,
) -> tuple[Dict[str, float], pd.DataFrame, pd.DataFrame]:
    """Calculate a dashboard scenario from versioned contract rows."""
    if not 0.0 <= uptake <= 1.0:
        raise ValueError("uptake must be in [0, 1]")
    if not 0.0 <= effectiveness <= 1.0:
        raise ValueError("effectiveness must be in [0, 1]")
    rows = _select_duration_rows(contract, duration_years, selected_models)
    counts = dict(model_counts or {})
    rows["scenario_hpe_count"] = [
        float(counts.get(model_id, default))
        for model_id, default in zip(rows["model_id"], rows["default_england_hpe_count"])
    ]
    rows["reducible_fraction"] = float(uptake * effectiveness)
    rows["baseline_incremental_cost_gbp"] = rows["scenario_hpe_count"] * rows["incremental_discounted_cost_per_person_gbp"]
    rows["baseline_incremental_qaly"] = rows["scenario_hpe_count"] * rows["incremental_discounted_qaly_per_person"]
    rows["gross_cost_avoided_gbp"] = rows["baseline_incremental_cost_gbp"] * rows["reducible_fraction"]
    rows["qaly_gained"] = -rows["baseline_incremental_qaly"] * rows["reducible_fraction"]

    event_rows = []
    for category in EVENT_CATEGORIES:
        slug = EVENT_SLUGS[category]
        per_person_col = f"excess_event_{slug}_per_person"
        baseline = float((rows["scenario_hpe_count"] * rows[per_person_col]).sum())
        avoided = baseline * float(uptake * effectiveness)
        event_rows.append({"event": category, "baseline_excess_events": baseline, "events_avoided": avoided})
    events = pd.DataFrame(event_rows)

    approached_hpe = float(rows["scenario_hpe_count"].sum()) * float(uptake)
    implementation_cost = approached_hpe * float(implementation_cost_per_approached_hpe_gbp)
    gross_saving = float(rows["gross_cost_avoided_gbp"].sum())
    metrics = {
        "duration_years": float(duration_years),
        "selected_model_count": float(len(rows)),
        "total_hpe_count": float(rows["scenario_hpe_count"].sum()),
        "uptake": float(uptake),
        "effectiveness": float(effectiveness),
        "reducible_fraction": float(uptake * effectiveness),
        "baseline_incremental_cost_gbp": float(rows["baseline_incremental_cost_gbp"].sum()),
        "baseline_incremental_qaly": float(rows["baseline_incremental_qaly"].sum()),
        "gross_cost_avoided_gbp": gross_saving,
        "qaly_gained": float(rows["qaly_gained"].sum()),
        "implementation_cost_gbp": float(implementation_cost),
        "net_budget_impact_gbp": float(gross_saving - implementation_cost),
    }
    return metrics, rows, events


def calculate_scenario_live(
    workbook_path: Path,
    duration_years: float,
    selected_models: Sequence[str],
    model_counts: Mapping[str, float] | None = None,
    uptake: float = 0.60,
    effectiveness: float = 0.25,
    implementation_cost_per_approached_hpe_gbp: float = 0.0,
) -> tuple[Dict[str, float], pd.DataFrame, pd.DataFrame]:
    """Run live Python formula engines for a single dashboard scenario."""
    live_contract = build_dashboard_contract(workbook_path, durations=[float(duration_years)])
    return calculate_scenario_from_contract(
        live_contract,
        duration_years=duration_years,
        selected_models=selected_models,
        model_counts=model_counts,
        uptake=uptake,
        effectiveness=effectiveness,
        implementation_cost_per_approached_hpe_gbp=implementation_cost_per_approached_hpe_gbp,
    )


def scenario_curve(
    contract: pd.DataFrame,
    selected_models: Sequence[str],
    model_counts: Mapping[str, float] | None = None,
    uptake: float = 0.60,
    effectiveness: float = 0.25,
    implementation_cost_per_approached_hpe_gbp: float = 0.0,
) -> pd.DataFrame:
    rows = []
    for duration in sorted(contract["duration_years"].unique()):
        metrics, _, _ = calculate_scenario_from_contract(
            contract,
            duration_years=float(duration),
            selected_models=selected_models,
            model_counts=model_counts,
            uptake=uptake,
            effectiveness=effectiveness,
            implementation_cost_per_approached_hpe_gbp=implementation_cost_per_approached_hpe_gbp,
        )
        rows.append(metrics)
    return pd.DataFrame(rows)


# Article base-case defaults reported in Camacho et al. (BMJ 2024).
# The live Python engines read their clinical and economic inputs from the
# public workbook. These values define the dashboard starting point and the
# published Table 3 comparator.
ARTICLE_BASE_CASE_DEFAULTS = {
    "time_horizon_years": 10.0,
    "hpe_exposure_duration_years": 10.0,
    "discount_rate_costs": 0.035,
    "discount_rate_qalys": 0.035,
    "perspective": "English NHS",
    "cost_year": "2020-21",
    "population": "English population registered with a GP",
    "population_size": 63_049_603,
    "effects_assumption": "additive",
    "published_psa_samples": 10_000,
}


def calculate_article_base_case_from_contract(
    contract: pd.DataFrame,
    duration_years: float = 10.0,
    selected_models: Sequence[str] = tuple(MODEL_IDS),
    model_counts: Mapping[str, float] | None = None,
) -> tuple[Dict[str, float], pd.DataFrame, pd.DataFrame]:
    """Calculate the article-style hazardous-prescribing burden.

    This is not an intervention calculation. It returns the full incremental
    NHS cost and QALY impact of the selected hazardous prescribing events (HPEs)
    relative to the corresponding no-HPE arms. The implementation reuses the
    validated contract engine with a reducible fraction of one so that the
    original scenario layer remains available as an optional dashboard view.
    """
    metrics, rows, events = calculate_scenario_from_contract(
        contract,
        duration_years=duration_years,
        selected_models=selected_models,
        model_counts=model_counts,
        uptake=1.0,
        effectiveness=1.0,
        implementation_cost_per_approached_hpe_gbp=0.0,
    )
    metrics = dict(metrics)
    metrics.update(
        {
            "article_cost_impact_gbp": float(metrics["baseline_incremental_cost_gbp"]),
            "article_qaly_impact": float(metrics["baseline_incremental_qaly"]),
        }
    )
    return metrics, rows, events


def calculate_article_base_case_live(
    workbook_path: Path,
    duration_years: float = 10.0,
    selected_models: Sequence[str] = tuple(MODEL_IDS),
    model_counts: Mapping[str, float] | None = None,
) -> tuple[Dict[str, float], pd.DataFrame, pd.DataFrame]:
    """Run live Python state-transition engines for an article-style burden calculation."""
    live_contract = build_dashboard_contract(workbook_path, durations=[float(duration_years)])
    return calculate_article_base_case_from_contract(
        live_contract,
        duration_years=duration_years,
        selected_models=selected_models,
        model_counts=model_counts,
    )


def article_base_case_curve(
    contract: pd.DataFrame,
    selected_models: Sequence[str],
    model_counts: Mapping[str, float] | None = None,
) -> pd.DataFrame:
    """Return the article-style burden curve over the exported duration grid."""
    curve = scenario_curve(
        contract,
        selected_models=selected_models,
        model_counts=model_counts,
        uptake=1.0,
        effectiveness=1.0,
        implementation_cost_per_approached_hpe_gbp=0.0,
    )
    curve = curve.copy()
    curve["article_cost_impact_gbp"] = curve["baseline_incremental_cost_gbp"]
    curve["article_qaly_impact"] = curve["baseline_incremental_qaly"]
    return curve


def load_published_table3_base_case(table3_path: Path) -> pd.DataFrame:
    """Read the published Table 3 base-case PSA means for Models A--E."""
    table3 = pd.read_csv(table3_path)
    base = table3.loc[table3["scenario"] == "base_case"].copy()
    if base.shape[0] != 2:
        raise ValueError("Published Table 3 CSV must contain two base_case rows")
    cost_row = base.loc[base["metric"] == "total_cost_impact"].iloc[0]
    qaly_row = base.loc[base["metric"] == "total_qaly_impact"].iloc[0]
    rows = []
    for model_id in MODEL_IDS:
        published_column = PUBLISHED_IDS[model_id]
        rows.append(
            {
                "model_id": model_id,
                "model_label": MODEL_LABELS[model_id],
                "published_table3_psa_mean_cost_impact_gbp": float(cost_row[published_column]) * 1_000_000.0,
                "published_table3_psa_mean_qaly_impact": float(qaly_row[published_column]),
            }
        )
    return pd.DataFrame(rows)


def attach_published_table3_comparison(model_rows: pd.DataFrame, table3_path: Path) -> pd.DataFrame:
    """Attach published Table 3 PSA means to deterministic live-model rows."""
    published = load_published_table3_base_case(table3_path)
    rows = model_rows.merge(published, on=["model_id", "model_label"], how="left", validate="one_to_one")
    rows["deterministic_cost_impact_gbp"] = rows["baseline_incremental_cost_gbp"]
    rows["deterministic_qaly_impact"] = rows["baseline_incremental_qaly"]
    rows["cost_difference_vs_published_psa_mean_gbp"] = (
        rows["deterministic_cost_impact_gbp"] - rows["published_table3_psa_mean_cost_impact_gbp"]
    )
    rows["qaly_difference_vs_published_psa_mean"] = (
        rows["deterministic_qaly_impact"] - rows["published_table3_psa_mean_qaly_impact"]
    )
    return rows


def article_reference_is_comparable(
    contract: pd.DataFrame,
    duration_years: float,
    selected_models: Sequence[str],
    model_counts: Mapping[str, float],
    atol: float = 1e-6,
) -> bool:
    """Return True only when dashboard inputs equal the article England base case."""
    if abs(float(duration_years) - ARTICLE_BASE_CASE_DEFAULTS["hpe_exposure_duration_years"]) > atol:
        return False
    if list(selected_models) != list(MODEL_IDS) and set(selected_models) != set(MODEL_IDS):
        return False
    defaults = (
        contract.sort_values(["duration_years", "model_id"])
        .drop_duplicates("model_id")
        .set_index("model_id")["default_england_hpe_count"]
        .to_dict()
    )
    return all(abs(float(model_counts[model_id]) - float(defaults[model_id])) <= atol for model_id in MODEL_IDS)
