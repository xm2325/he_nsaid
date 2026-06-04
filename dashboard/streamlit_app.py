"""Dynamic Python Streamlit dashboard for the MedSID NSAID prototype.

Run locally:
    streamlit run dashboard/streamlit_app.py

Deploy with Streamlit Community Cloud by selecting this file as the app entry
point. The default fast mode reads the versioned scenario contract exported from
the validated Python engines. The optional live mode reruns the Python formula
engines for the selected exposure duration.
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
    MODEL_IDS,
    MODEL_LABELS,
    calculate_scenario_from_contract,
    calculate_scenario_live,
    scenario_curve,
)

CONTRACT_PATH = ROOT / "dashboard" / "data" / "dashboard_scenario_contract.csv"
MANIFEST_PATH = ROOT / "dashboard" / "data" / "dashboard_contract_manifest.json"
WORKBOOK_PATH = ROOT / "sources" / "nsaid_2024_original_workbook_came077880.ww1.xlsm"

st.set_page_config(page_title="MedSID NSAID scenario explorer", layout="wide")


@st.cache_data(show_spinner=False)
def load_contract(path: str) -> pd.DataFrame:
    return pd.read_csv(path)


@st.cache_data(show_spinner=False)
def load_manifest(path: str) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def gbp(value: float) -> str:
    return f"£{value:,.0f}"


def qaly(value: float) -> str:
    return f"{value:,.1f}"


def make_event_plot(events: pd.DataFrame):
    plot_data = events[events["events_avoided"].abs() > 1e-10].copy()
    fig, ax = plt.subplots(figsize=(8.0, 4.2))
    ax.barh(plot_data["event"], plot_data["events_avoided"])
    ax.set_xlabel("Estimated events avoided")
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(axis="x", alpha=0.3)
    fig.tight_layout()
    return fig


def make_duration_plot(curve: pd.DataFrame):
    fig, axes = plt.subplots(nrows=2, ncols=1, figsize=(8.0, 6.0), sharex=True)
    axes[0].plot(curve["duration_years"], curve["gross_cost_avoided_gbp"] / 1_000_000.0, marker="o", markersize=2.8)
    axes[0].set_ylabel("Gross cost avoided (£m)")
    axes[1].plot(curve["duration_years"], curve["qaly_gained"], marker="o", markersize=2.8)
    axes[1].set_ylabel("QALYs gained")
    axes[1].set_xlabel("Duration of exposure to hazardous prescribing (years)")
    for ax in axes:
        ax.grid(axis="y", alpha=0.3)
        ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    return fig


contract = load_contract(str(CONTRACT_PATH))
manifest = load_manifest(str(MANIFEST_PATH))
default_count_rows = (
    contract.sort_values(["duration_years", "model_id"])
    .drop_duplicates("model_id")[["model_id", "model_label", "default_england_hpe_count"]]
    .sort_values("model_id")
    .reset_index(drop=True)
)

st.title("MedSID NSAID medicines-safety scenario explorer")
st.caption("Dynamic Python version: five validated NSAID state-transition models plus a transparent intervention scenario layer.")

with st.sidebar:
    st.header("Scenario inputs")
    calculation_mode = st.radio(
        "Calculation mode",
        options=["Fast validated contract", "Live Python state-transition models"],
        help="Fast mode reads a versioned grid generated from the Python formula engines. Live mode reruns the models for the selected duration.",
    )
    selected_models = st.multiselect(
        "Models included",
        options=MODEL_IDS,
        default=MODEL_IDS,
        format_func=lambda model_id: f"{model_id}: {MODEL_LABELS[model_id]}",
    )
    duration = st.slider("HPE exposure duration (years)", min_value=0.25, max_value=10.0, value=10.0, step=0.25)
    uptake = st.slider("Intervention uptake", min_value=0.0, max_value=1.0, value=0.60, step=0.01)
    effectiveness = st.slider("Effectiveness among reached HPEs", min_value=0.0, max_value=1.0, value=0.25, step=0.01)
    unit_cost = st.number_input("Implementation cost per approached HPE (£)", min_value=0.0, value=0.0, step=1.0)
    scale = st.number_input("Population scale relative to England", min_value=0.0001, value=1.0, step=0.05, format="%.4f")

count_editor = default_count_rows.copy()
count_editor["scenario_hpe_count"] = count_editor["default_england_hpe_count"] * float(scale)
with st.expander("Advanced: edit HPE counts by model"):
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

if calculation_mode == "Live Python state-transition models":
    with st.spinner("Running validated Python state-transition models..."):
        metrics, model_results, events = calculate_scenario_live(
            WORKBOOK_PATH,
            duration_years=duration,
            selected_models=selected_models,
            model_counts=model_counts,
            uptake=uptake,
            effectiveness=effectiveness,
            implementation_cost_per_approached_hpe_gbp=unit_cost,
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
    "Scenario assumption: avoided burden = baseline HPE burden × uptake × effectiveness. "
    "The dashboard does not infer intervention effectiveness; users supply that assumption."
)

summary_tab, models_tab, validation_tab = st.tabs(["Scenario summary", "Model results", "Validation and scope"])
with summary_tab:
    left, right = st.columns(2)
    with left:
        st.subheader("Estimated safety events avoided")
        st.pyplot(make_event_plot(events), use_container_width=True)
        st.dataframe(events, use_container_width=True, hide_index=True)
    with right:
        st.subheader("Exposure-duration curve")
        st.pyplot(make_duration_plot(curve), use_container_width=True)

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
- **Fast validated contract:** reads a versioned duration grid generated from the validated Python formula engines.
- **Live Python state-transition models:** reruns the five formula engines for the selected exposure duration.
- **Intervention layer:** multiplies baseline burden by user-supplied uptake and effectiveness assumptions.
- **Cross-language check:** GitHub Actions runs standard scenario cases in Python and R and fails if their outputs differ beyond tolerance.
"""
    )
    st.json(manifest)
