"""Dynamic Python Streamlit dashboard for the MedSID NSAID reproduction.

Run locally:
    streamlit run dashboard/streamlit_app.py

The default screen reruns the live Python state-transition models with the
Camacho et al. (BMJ 2024) article base-case assumptions. A separate optional
screen retains the transparent intervention scenario layer added in v13.
"""
from __future__ import annotations

from pathlib import Path
import json
import sys

import matplotlib.pyplot as plt
import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from medsid_repro.dashboard_scenario import (  # noqa: E402
    ARTICLE_BASE_CASE_DEFAULTS,
    MODEL_IDS,
    MODEL_LABELS,
    article_base_case_curve,
    article_reference_is_comparable,
    attach_published_table3_comparison,
    calculate_article_base_case_from_contract,
    calculate_article_base_case_live,
    calculate_scenario_from_contract,
    calculate_scenario_live,
    scenario_curve,
)

CONTRACT_PATH = ROOT / "dashboard" / "data" / "dashboard_scenario_contract.csv"
MANIFEST_PATH = ROOT / "dashboard" / "data" / "dashboard_contract_manifest.json"
WORKBOOK_PATH = ROOT / "sources" / "nsaid_2024_original_workbook_came077880.ww1.xlsm"
PUBLISHED_TABLE3_PATH = ROOT / "data" / "nsaid_2024_published_table3.csv"
CACHED_PSA_SUMMARY_PATH = ROOT / "outputs" / "independent_psa" / "figure2_psa_reaggregation_summary.json"

st.set_page_config(page_title="MedSID NSAID article reproduction", layout="wide")


@st.cache_data(show_spinner=False)
def load_contract(path: str) -> pd.DataFrame:
    return pd.read_csv(path)


@st.cache_data(show_spinner=False)
def load_json(path: str) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


@st.cache_data(show_spinner=False)
def run_article_live_cached(
    workbook_path: str,
    duration_years: float,
    selected_models: tuple[str, ...],
    model_counts: tuple[tuple[str, float], ...],
):
    return calculate_article_base_case_live(
        Path(workbook_path),
        duration_years=duration_years,
        selected_models=list(selected_models),
        model_counts=dict(model_counts),
    )


@st.cache_data(show_spinner=False)
def run_scenario_live_cached(
    workbook_path: str,
    duration_years: float,
    selected_models: tuple[str, ...],
    model_counts: tuple[tuple[str, float], ...],
    uptake: float,
    effectiveness: float,
    implementation_cost: float,
):
    return calculate_scenario_live(
        Path(workbook_path),
        duration_years=duration_years,
        selected_models=list(selected_models),
        model_counts=dict(model_counts),
        uptake=uptake,
        effectiveness=effectiveness,
        implementation_cost_per_approached_hpe_gbp=implementation_cost,
    )


def gbp(value: float) -> str:
    return f"£{value:,.0f}"


def qaly(value: float) -> str:
    return f"{value:,.1f}"


def percentage(value: float) -> str:
    return f"{value:,.2f}%"


def make_event_plot(events: pd.DataFrame, value_column: str, xlabel: str):
    plot_data = events[events[value_column].abs() > 1e-10].copy()
    fig, ax = plt.subplots(figsize=(8.0, 4.2))
    ax.barh(plot_data["event"], plot_data[value_column])
    ax.set_xlabel(xlabel)
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(axis="x", alpha=0.3)
    fig.tight_layout()
    return fig


def make_duration_plot(curve: pd.DataFrame, cost_column: str, qaly_column: str, qaly_ylabel: str):
    fig, axes = plt.subplots(nrows=2, ncols=1, figsize=(8.0, 6.0), sharex=True)
    axes[0].plot(curve["duration_years"], curve[cost_column] / 1_000_000.0, marker="o", markersize=2.8)
    axes[0].set_ylabel("Cost impact (£m)")
    axes[1].plot(curve["duration_years"], curve[qaly_column], marker="o", markersize=2.8)
    axes[1].set_ylabel(qaly_ylabel)
    axes[1].set_xlabel("Duration of exposure to hazardous prescribing (years)")
    for ax in axes:
        ax.grid(axis="y", alpha=0.3)
        ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    return fig


contract = load_contract(str(CONTRACT_PATH))
manifest = load_json(str(MANIFEST_PATH))
default_count_rows = (
    contract.sort_values(["duration_years", "model_id"])
    .drop_duplicates("model_id")[["model_id", "model_label", "default_england_hpe_count"]]
    .sort_values("model_id")
    .reset_index(drop=True)
)

st.title("MedSID NSAID medicines-safety model explorer")
st.caption(
    "Default view: live Python state-transition models using the BMJ 2024 article base case. "
    "The optional intervention view remains available for user-defined scenario analysis."
)

with st.sidebar:
    st.header("Model inputs")
    analysis_view = st.radio(
        "Analysis view",
        options=["Article base-case reproduction", "Illustrative intervention scenario"],
        help=(
            "The article view calculates the full hazardous-prescribing burden. "
            "The intervention view applies a user-defined reducible fraction and optional implementation cost."
        ),
    )
    calculation_mode = st.radio(
        "Calculation mode",
        options=["Live Python state-transition models", "Fast validated contract"],
        help=(
            "Live mode reruns the five Python state-transition engines for the selected duration. "
            "Fast mode reads a versioned grid exported from those engines."
        ),
    )
    selected_models = st.multiselect(
        "Models included",
        options=MODEL_IDS,
        default=MODEL_IDS,
        format_func=lambda model_id: f"{model_id}: {MODEL_LABELS[model_id]}",
    )
    duration = st.slider(
        "HPE exposure duration (years)",
        min_value=0.25,
        max_value=10.0,
        value=float(ARTICLE_BASE_CASE_DEFAULTS["hpe_exposure_duration_years"]),
        step=0.25,
        help="The BMJ 2024 base case assumes exposure for the model lifetime, up to 10 years unless an adverse event stops exposure.",
    )
    scale = st.number_input(
        "Population scale relative to England",
        min_value=0.0001,
        value=1.0,
        step=0.05,
        format="%.4f",
    )
    if analysis_view == "Illustrative intervention scenario":
        st.subheader("Intervention assumptions")
        uptake = st.slider("Intervention uptake", min_value=0.0, max_value=1.0, value=0.60, step=0.01)
        effectiveness = st.slider("Effectiveness among reached HPEs", min_value=0.0, max_value=1.0, value=0.25, step=0.01)
        unit_cost = st.number_input(
            "Implementation cost per approached HPE (£)",
            min_value=0.0,
            value=0.0,
            step=1.0,
            help="User-defined scenario assumption. This value is not estimated in the BMJ 2024 article.",
        )
    else:
        uptake = 1.0
        effectiveness = 1.0
        unit_cost = 0.0
        st.caption("Article default: full incremental HPE burden; no intervention cost is added.")

count_editor = default_count_rows.copy()
count_editor["scenario_hpe_count"] = count_editor["default_england_hpe_count"] * float(scale)
with st.expander("Advanced: edit HPE counts by model"):
    st.caption("Workbook-derived national scaling values are fractional internally; Table 3 reports rounded numbers of people.")
    edited_counts = st.data_editor(
        count_editor[["model_id", "model_label", "scenario_hpe_count"]],
        disabled=["model_id", "model_label"],
        hide_index=True,
        use_container_width=True,
    )

if not selected_models:
    st.warning("Select at least one model.")
    st.stop()

model_counts = {row.model_id: float(row.scenario_hpe_count) for row in edited_counts.itertuples()}
count_tuple = tuple(sorted(model_counts.items()))
model_tuple = tuple(selected_models)

if analysis_view == "Article base-case reproduction":
    if calculation_mode == "Live Python state-transition models":
        with st.spinner("Running live Python state-transition models..."):
            metrics, model_results, events = run_article_live_cached(
                str(WORKBOOK_PATH), duration, model_tuple, count_tuple
            )
    else:
        metrics, model_results, events = calculate_article_base_case_from_contract(
            contract,
            duration_years=duration,
            selected_models=selected_models,
            model_counts=model_counts,
        )
    curve = article_base_case_curve(contract, selected_models=selected_models, model_counts=model_counts)
    comparison = attach_published_table3_comparison(model_results, PUBLISHED_TABLE3_PATH)
    published_cost = float(comparison["published_table3_psa_mean_cost_impact_gbp"].sum())
    published_qaly = float(comparison["published_table3_psa_mean_qaly_impact"].sum())
    deterministic_cost = float(metrics["article_cost_impact_gbp"])
    deterministic_qaly = float(metrics["article_qaly_impact"])
    comparable = article_reference_is_comparable(contract, duration, selected_models, model_counts)

    metric_cols = st.columns(4)
    metric_cols[0].metric("Live deterministic cost impact", gbp(deterministic_cost))
    metric_cols[1].metric("Live deterministic QALY impact", qaly(deterministic_qaly))
    metric_cols[2].metric("Published Table 3 PSA mean cost", gbp(published_cost))
    metric_cols[3].metric("Published Table 3 PSA mean QALYs", qaly(published_qaly))

    if comparable:
        st.info(
            "Article base-case inputs are active: all five models, England population scaling, 10-year time horizon, "
            "10-year maximum HPE exposure duration, NHS perspective, 2020-21 costs, and 3.5% annual discounting. "
            "The live result is a deterministic reconstruction. The published Table 3 values are PSA means, so exact equality is not expected."
        )
    else:
        st.warning(
            "One or more inputs differ from the article England base case. Published Table 3 values are shown only as a fixed reference."
        )

    summary_tab, models_tab, validation_tab = st.tabs(["Article summary", "Model comparison", "Validation and scope"])
    with summary_tab:
        left, right = st.columns(2)
        with left:
            st.subheader("Expected excess events")
            st.pyplot(
                make_event_plot(events, "baseline_excess_events", "Expected excess events over the selected horizon"),
                use_container_width=True,
            )
            st.dataframe(events[["event", "baseline_excess_events"]], use_container_width=True, hide_index=True)
        with right:
            st.subheader("Exposure-duration sensitivity")
            st.pyplot(
                make_duration_plot(curve, "article_cost_impact_gbp", "article_qaly_impact", "QALY impact"),
                use_container_width=True,
            )

    with models_tab:
        display_columns = [
            "model_id",
            "model_label",
            "scenario_hpe_count",
            "incremental_discounted_cost_per_person_gbp",
            "incremental_discounted_qaly_per_person",
            "deterministic_cost_impact_gbp",
            "published_table3_psa_mean_cost_impact_gbp",
            "cost_difference_vs_published_psa_mean_gbp",
            "deterministic_qaly_impact",
            "published_table3_psa_mean_qaly_impact",
            "qaly_difference_vs_published_psa_mean",
        ]
        st.dataframe(comparison[display_columns], use_container_width=True, hide_index=True)
        st.download_button(
            "Download article base-case comparison CSV",
            data=comparison.to_csv(index=False).encode("utf-8"),
            file_name="medsid_article_base_case_live_comparison.csv",
            mime="text/csv",
        )

    with validation_tab:
        st.subheader("Default live result versus the published article")
        cost_difference = deterministic_cost - published_cost
        qaly_difference = deterministic_qaly - published_qaly
        validation_rows = [
            {
                "output": "Total cost impact (£)",
                "live deterministic reconstruction": deterministic_cost,
                "published Table 3 PSA mean": published_cost,
                "difference": cost_difference,
                "difference relative to published mean": percentage(100.0 * cost_difference / published_cost),
            },
            {
                "output": "Total QALY impact",
                "live deterministic reconstruction": deterministic_qaly,
                "published Table 3 PSA mean": published_qaly,
                "difference": qaly_difference,
                "difference relative to published magnitude": percentage(100.0 * qaly_difference / abs(published_qaly)),
            },
        ]
        st.dataframe(pd.DataFrame(validation_rows), use_container_width=True, hide_index=True)
        if CACHED_PSA_SUMMARY_PATH.exists():
            cached_psa = load_json(str(CACHED_PSA_SUMMARY_PATH))
            st.caption(
                "The public workbook stores 1,000 cached PSA iterations. Reaggregating those stored iterations gives "
                f"{gbp(float(cached_psa['mean_incremental_cost_gbp']))} and "
                f"{qaly(float(cached_psa['mean_incremental_qaly']))} QALYs. "
                "The article reports PSA means from 10,000 samples."
            )
        st.subheader("Article base-case assumptions")
        st.json(ARTICLE_BASE_CASE_DEFAULTS)
        st.subheader("Scientific scope")
        st.markdown(
            """
- The selected point is recalculated by the live Python state-transition engines when live mode is selected.
- The duration curve uses the versioned contract exported from those same engines so the interface remains responsive.
- The deterministic trace and reward calculations are independently reconstructed and regression-tested against workbook cached values.
- The repository reaggregates the workbook-saved PSA outputs, but it does not yet independently draw every uncertain parameter and rerun Models A--E for 10,000 simulations.
"""
        )
        st.json(manifest)

else:
    if calculation_mode == "Live Python state-transition models":
        with st.spinner("Running live Python state-transition models..."):
            metrics, model_results, events = run_scenario_live_cached(
                str(WORKBOOK_PATH), duration, model_tuple, count_tuple, uptake, effectiveness, unit_cost
            )
    else:
        metrics, model_results, events = calculate_scenario_from_contract(
            contract,
            duration_years=duration,
            selected_models=selected_models,
            model_counts=model_counts,
            uptake=uptake,
            effectiveness=effectiveness,
            implementation_cost_per_approached_hpe_gbp=unit_cost,
        )
    curve = scenario_curve(
        contract,
        selected_models=selected_models,
        model_counts=model_counts,
        uptake=uptake,
        effectiveness=effectiveness,
        implementation_cost_per_approached_hpe_gbp=unit_cost,
    )

    metric_cols = st.columns(4)
    metric_cols[0].metric("Gross NHS cost avoided", gbp(metrics["gross_cost_avoided_gbp"]))
    metric_cols[1].metric("QALYs gained", qaly(metrics["qaly_gained"]))
    metric_cols[2].metric("Implementation cost", gbp(metrics["implementation_cost_gbp"]))
    metric_cols[3].metric("Net budget impact", gbp(metrics["net_budget_impact_gbp"]))

    st.info(
        "Illustrative scenario assumption: avoided burden = baseline HPE burden × uptake × effectiveness. "
        "The dashboard does not infer an intervention effect or an implementation cost; users supply those assumptions."
    )

    summary_tab, models_tab, validation_tab = st.tabs(["Scenario summary", "Model results", "Validation and scope"])
    with summary_tab:
        left, right = st.columns(2)
        with left:
            st.subheader("Estimated safety events avoided")
            st.pyplot(make_event_plot(events, "events_avoided", "Estimated events avoided"), use_container_width=True)
            st.dataframe(events, use_container_width=True, hide_index=True)
        with right:
            st.subheader("Exposure-duration curve")
            st.pyplot(make_duration_plot(curve, "gross_cost_avoided_gbp", "qaly_gained", "QALYs gained"), use_container_width=True)

    with models_tab:
        display_columns = [
            "model_id",
            "model_label",
            "scenario_hpe_count",
            "incremental_discounted_cost_per_person_gbp",
            "incremental_discounted_qaly_per_person",
            "baseline_incremental_cost_gbp",
            "baseline_incremental_qaly",
            "gross_cost_avoided_gbp",
            "qaly_gained",
        ]
        st.dataframe(model_results[display_columns], use_container_width=True, hide_index=True)
        st.download_button(
            "Download model-level scenario CSV",
            data=model_results.to_csv(index=False).encode("utf-8"),
            file_name="medsid_python_dashboard_scenario.csv",
            mime="text/csv",
        )

    with validation_tab:
        st.subheader("What is recalculated dynamically?")
        st.markdown(
            """
- **Live Python state-transition models:** reruns the five formula engines for the selected exposure duration.
- **Fast validated contract:** reads a versioned duration grid generated from the validated Python formula engines.
- **Intervention layer:** multiplies baseline burden by user-supplied uptake and effectiveness assumptions.
- **Cross-language check:** GitHub Actions runs standard scenario cases in Python and R and fails if their outputs differ beyond tolerance.
"""
        )
        st.json(manifest)
