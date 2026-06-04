#!/usr/bin/env python3
"""Export deterministic state-transition contracts for the native R runner.

The R implementation intentionally consumes explicit, versioned transition and
reward contracts generated from the Python formula engines. This keeps the R
runner dependency-light and makes cross-language regression validation easy in
GitHub Actions.

This is a native R state-transition replay implementation. The formula-level
model translation remains authoritative in Python; the R contract runner is a
portable second implementation of trace propagation, reward accumulation and
PSA aggregation.
"""
from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
import json
import sys

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from medsid_repro.independent_nsaid_gi import (  # noqa: E402
    STATE_NAMES as GI_STATES,
    STATE_INDEX as GI_INDEX,
    _age_lookup as gi_age_lookup,
    load_gi_model_inputs,
    run_markov_trace as run_gi_trace,
    summarise_trace as summarise_gi,
    transition_matrix as gi_transition,
)
from medsid_repro.independent_nsaid_c import (  # noqa: E402
    STATE_NAMES as C_STATES,
    STATE_INDEX as C_INDEX,
    _lower_bound_lookup as c_lookup,
    load_model_c_inputs,
    run_markov_trace as run_c_trace,
    summarise_trace as summarise_c,
    transition_matrix as c_transition,
)
from medsid_repro.independent_nsaid_d import (  # noqa: E402
    STATE_NAMES as D_STATES,
    STATE_INDEX as D_INDEX,
    load_model_d_inputs,
    run_markov_trace as run_d_trace,
    summarise_trace as summarise_d,
    transition_matrix as d_transition,
)
from medsid_repro.independent_nsaid_e import (  # noqa: E402
    STATE_NAMES as E_STATES,
    STATE_INDEX as E_INDEX,
    _lookup_lower_bound as e_lookup,
    load_model_e_inputs,
    run_markov_trace as run_e_trace,
    summarise_trace as summarise_e,
    transition_matrix as e_transition,
)
from medsid_repro.independent_nsaid_psa import (  # noqa: E402
    aggregate_england_psa,
    extract_england_query_level_psa,
)

WORKBOOK = ROOT / "sources" / "nsaid_2024_original_workbook_came077880.ww1.xlsm"
OUT = ROOT / "r" / "data"


def add_matrix_rows(rows: list[dict], model_id: str, arm: str, cycle: int, matrix: np.ndarray, states: list[str]) -> None:
    for i, from_state in enumerate(states, start=1):
        for j, to_state in enumerate(states, start=1):
            value = float(matrix[i - 1, j - 1])
            if abs(value) > 0.0:
                rows.append({
                    "model_id": model_id,
                    "arm": arm,
                    "cycle": cycle,
                    "from_index": i,
                    "from_state": from_state,
                    "to_index": j,
                    "to_state": to_state,
                    "probability": value,
                })


def add_trace_rows(rows: list[dict], model_id: str, arm: str, trace: pd.DataFrame, states: list[str]) -> None:
    for _, record in trace.iterrows():
        for i, state in enumerate(states, start=1):
            rows.append({
                "model_id": model_id,
                "arm": arm,
                "cycle": int(record["cycle"]),
                "state_index": i,
                "state": state,
                "occupancy": float(record[state]),
            })


def add_reward_rows(rows: list[dict], model_id: str, inputs: object, states: list[str], alive: np.ndarray,
                    utilities_by_cycle: list[np.ndarray], costs: np.ndarray, discount_times: list[float],
                    include_discounted_ly: bool) -> None:
    n_cycles = int(inputs.time_horizon_years * inputs.cycles_per_year)
    for cycle in range(n_cycles):
        qdisc = float((1.0 + inputs.discount_qaly) ** discount_times[cycle])
        cdisc = float((1.0 + inputs.discount_qaly) ** discount_times[cycle])
        # This mirrors the workbook where several cost sheets reference DQALYs.
        if model_id == "C":
            cdisc = float((1.0 + inputs.discount_cost) ** discount_times[cycle])
        for i, state in enumerate(states, start=1):
            rows.append({
                "model_id": model_id,
                "cycle": cycle,
                "state_index": i,
                "state": state,
                "cycle_length": float(inputs.cycle_length),
                "ly_weight": float(alive[i - 1] * inputs.cycle_length),
                "qaly_weight": float(utilities_by_cycle[cycle][i - 1] * inputs.cycle_length),
                "cost_weight": float(costs[i - 1]),
                "qaly_discount_factor": qdisc,
                "cost_discount_factor": cdisc,
                "ly_discount_factor": qdisc if include_discounted_ly else 1.0,
                "include_discounted_ly": int(include_discounted_ly),
            })


def export() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    transitions: list[dict] = []
    initials: list[dict] = []
    rewards: list[dict] = []
    references: list[dict] = []
    traces: list[dict] = []

    loaders = {
        "A": lambda: load_gi_model_inputs(WORKBOOK, "A"),
        "B": lambda: load_gi_model_inputs(WORKBOOK, "B"),
        "C": lambda: load_model_c_inputs(WORKBOOK),
        "D": lambda: load_model_d_inputs(WORKBOOK),
        "E": lambda: load_model_e_inputs(WORKBOOK),
    }

    for model_id, load in loaders.items():
        inputs = load()
        if model_id in {"A", "B"}:
            states, idx = GI_STATES, GI_INDEX
            trace_fn, summary_fn = run_gi_trace, summarise_gi
            dead_names = ["Dead"]
            utilities = []
            for c in range(int(inputs.time_horizon_years * inputs.cycles_per_year)):
                age = inputs.cohort_age + c * inputs.cycle_length
                u = gi_age_lookup(age, inputs.gp_utility_by_age) + inputs.disutility_by_state.copy()
                u[idx["Dead"]] = 0.0
                utilities.append(u)
            discount_times = [c * inputs.cycle_length for c in range(int(inputs.time_horizon_years * inputs.cycles_per_year))]
        elif model_id == "C":
            states, idx = C_STATES, C_INDEX
            trace_fn, summary_fn = run_c_trace, summarise_c
            dead_names = ["Dead"]
            utilities = []
            for c in range(int(inputs.time_horizon_years * inputs.cycles_per_year)):
                age = inputs.cohort_age + c * inputs.cycle_length
                u = c_lookup(age, inputs.utility_by_age) + inputs.disutility_by_state.copy()
                u[idx["Dead"]] = 0.0
                utilities.append(u)
            discount_times = [c * inputs.cycle_length for c in range(int(inputs.time_horizon_years * inputs.cycles_per_year))]
        elif model_id == "D":
            states, idx = D_STATES, D_INDEX
            trace_fn, summary_fn = run_d_trace, summarise_d
            dead_names = ["Dead"]
            utilities = [inputs.utility_by_state.copy() for _ in range(int(inputs.time_horizon_years * inputs.cycles_per_year))]
            discount_times = [c * inputs.cycle_length + inputs.cycle_length / 2.0 for c in range(int(inputs.time_horizon_years * inputs.cycles_per_year))]
        else:
            states, idx = E_STATES, E_INDEX
            trace_fn, summary_fn = run_e_trace, summarise_e
            dead_names = ["Dead (AKI)", "Dead (other)"]
            utilities = []
            for c in range(int(inputs.time_horizon_years * inputs.cycles_per_year)):
                age = inputs.cohort_age + c * inputs.cycle_length
                u = e_lookup(age, inputs.genpop_utility_by_age) + inputs.disutility_by_state.copy()
                u[idx["Dead (AKI)"]] = 0.0
                u[idx["Dead (other)"]] = 0.0
                utilities.append(u)
            discount_times = [c * inputs.cycle_length for c in range(int(inputs.time_horizon_years * inputs.cycles_per_year))]

        alive = np.ones(len(states), dtype=float)
        for name in dead_names:
            alive[idx[name]] = 0.0
        add_reward_rows(rewards, model_id, inputs, states, alive, utilities, inputs.costs_by_state,
                        discount_times, include_discounted_ly=(model_id == "E"))

        for arm in ["HPE", "No HPE"]:
            trace = trace_fn(inputs, arm)
            summary = summary_fn(inputs, trace)
            add_trace_rows(traces, model_id, arm, trace, states)
            for metric, value in summary.items():
                references.append({"model_id": model_id, "arm": arm, "metric": metric, "reference_value": float(value)})
            initial = trace.iloc[0]
            for i, state in enumerate(states, start=1):
                initials.append({"model_id": model_id, "arm": arm, "state_index": i, "state": state, "probability": float(initial[state])})

            n_cycles = int(inputs.time_horizon_years * inputs.cycles_per_year)
            for cycle in range(1, n_cycles + 1):
                start_time = (cycle - 1) * inputs.cycle_length
                end_time = cycle * inputs.cycle_length
                age = inputs.cohort_age + (cycle - 1) * inputs.cycle_length
                if model_id in {"A", "B"}:
                    use_hpe = arm == "HPE" and (end_time < inputs.max_hpe_years)
                    expired = arm == "HPE" and (end_time >= inputs.max_hpe_years)
                    matrix = gi_transition(inputs, age, use_hpe_acquisition=use_hpe, hpe_expired=expired)
                elif model_id == "C":
                    crossing = arm == "HPE" and start_time < inputs.max_hpe_years <= end_time
                    matrix = c_transition(inputs, age, crossing_hpe_duration=crossing)
                elif model_id == "D":
                    crossing = arm == "HPE" and start_time < inputs.max_hpe_years <= end_time
                    matrix = d_transition(inputs, age, crossing_hpe_duration=crossing)
                else:
                    crossing = arm == "HPE" and start_time < inputs.max_hpe_years <= end_time
                    matrix = e_transition(inputs, age, crossing_hpe_duration=crossing)
                add_matrix_rows(transitions, model_id, arm, cycle, matrix, states)

    pd.DataFrame(transitions).to_csv(OUT / "transition_contract.csv", index=False)
    pd.DataFrame(initials).to_csv(OUT / "initial_state_contract.csv", index=False)
    pd.DataFrame(rewards).to_csv(OUT / "reward_contract.csv", index=False)
    pd.DataFrame(references).to_csv(OUT / "summary_reference.csv", index=False)
    pd.DataFrame(traces).to_csv(OUT / "trace_reference.csv", index=False)

    psa_model = extract_england_query_level_psa(WORKBOOK)
    psa_total = aggregate_england_psa(psa_model)
    psa_model.to_csv(OUT / "psa_model_level_england.csv", index=False)
    psa_total.to_csv(OUT / "psa_total_reference.csv", index=False)

    manifest = {
        "models": ["A", "B", "C", "D", "E"],
        "arms": ["HPE", "No HPE"],
        "n_cycles": 40,
        "psa_iterations": int(psa_total.shape[0]),
        "r_runner_scope": "Native R trace propagation, reward accumulation and PSA aggregation over versioned contracts exported from Python formula engines.",
        "parameter_level_psa": False,
    }
    (OUT / "contract_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    export()
