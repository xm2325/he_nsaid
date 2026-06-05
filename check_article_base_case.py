#!/usr/bin/env python3
"""Validate the versioned contracts consumed by the native R runner.

This script mirrors the base-R contract replay algorithm in Python so that the
CSV contract layer can be checked in environments where R is not installed.
The GitHub Actions R job additionally runs the R implementation itself.
"""
from __future__ import annotations

from pathlib import Path
import json
import sys

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "r" / "data"
OUT = ROOT / "outputs" / "r_contract_validation"


def load() -> dict[str, pd.DataFrame]:
    return {
        "transitions": pd.read_csv(DATA / "transition_contract.csv"),
        "initial": pd.read_csv(DATA / "initial_state_contract.csv"),
        "rewards": pd.read_csv(DATA / "reward_contract.csv"),
        "summary_reference": pd.read_csv(DATA / "summary_reference.csv"),
        "trace_reference": pd.read_csv(DATA / "trace_reference.csv"),
        "psa_model": pd.read_csv(DATA / "psa_model_level_england.csv"),
        "psa_total_reference": pd.read_csv(DATA / "psa_total_reference.csv"),
    }


def run_arm(data: dict[str, pd.DataFrame], model_id: str, arm: str) -> tuple[pd.DataFrame, dict[str, float]]:
    initial = data["initial"].query("model_id == @model_id and arm == @arm").sort_values("state_index")
    states = initial["state"].tolist()
    n_states = len(states)
    rewards = data["rewards"].query("model_id == @model_id").sort_values(["cycle", "state_index"])
    n_cycles = int(rewards["cycle"].max()) + 1
    trace = np.zeros((n_cycles + 1, n_states), dtype=float)
    trace[0] = initial["probability"].to_numpy(dtype=float)
    for cycle in range(1, n_cycles + 1):
        rows = data["transitions"].query("model_id == @model_id and arm == @arm and cycle == @cycle")
        matrix = np.zeros((n_states, n_states), dtype=float)
        for row in rows.itertuples(index=False):
            matrix[int(row.from_index) - 1, int(row.to_index) - 1] = float(row.probability)
        trace[cycle] = trace[cycle - 1] @ matrix

    totals = {
        "total_ly": 0.0,
        "discounted_ly": 0.0,
        "total_qaly": 0.0,
        "discounted_qaly": 0.0,
        "total_cost": 0.0,
        "discounted_cost": 0.0,
    }
    for cycle in range(n_cycles):
        rows = rewards.query("cycle == @cycle").sort_values("state_index")
        start = trace[cycle]
        end = trace[cycle + 1]
        occupancy = 0.5 * (start + end)
        ly = float(start @ rows["ly_weight"].to_numpy(dtype=float))
        qaly = float(occupancy @ rows["qaly_weight"].to_numpy(dtype=float))
        cost = float(occupancy @ rows["cost_weight"].to_numpy(dtype=float))
        totals["total_ly"] += ly
        totals["discounted_ly"] += ly / float(rows["ly_discount_factor"].iloc[0])
        totals["total_qaly"] += qaly
        totals["discounted_qaly"] += qaly / float(rows["qaly_discount_factor"].iloc[0])
        totals["total_cost"] += cost
        totals["discounted_cost"] += cost / float(rows["cost_discount_factor"].iloc[0])

    trace_df = pd.DataFrame(trace, columns=states)
    trace_df.insert(0, "cycle", range(n_cycles + 1))
    return trace_df, totals


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    data = load()
    summary_rows: list[dict] = []
    trace_rows: list[dict] = []
    for model_id in ["A", "B", "C", "D", "E"]:
        for arm in ["HPE", "No HPE"]:
            trace, totals = run_arm(data, model_id, arm)
            ref_trace = data["trace_reference"].query("model_id == @model_id and arm == @arm").sort_values(["cycle", "state_index"])
            calc = trace.drop(columns=["cycle"]).to_numpy(dtype=float).reshape(-1)
            ref = ref_trace["occupancy"].to_numpy(dtype=float)
            trace_error = float(np.max(np.abs(calc - ref)))
            trace_rows.append({"model_id": model_id, "arm": arm, "max_absolute_trace_error": trace_error})
            ref_summary = data["summary_reference"].query("model_id == @model_id and arm == @arm")
            for row in ref_summary.itertuples(index=False):
                calc_value = float(totals[row.metric])
                summary_rows.append({
                    "model_id": model_id,
                    "arm": arm,
                    "metric": row.metric,
                    "contract_replay": calc_value,
                    "python_reference": float(row.reference_value),
                    "absolute_error": calc_value - float(row.reference_value),
                })

    trace_validation = pd.DataFrame(trace_rows)
    summary_validation = pd.DataFrame(summary_rows)
    trace_validation.to_csv(OUT / "trace_validation.csv", index=False)
    summary_validation.to_csv(OUT / "summary_validation.csv", index=False)

    psa_total = data["psa_model"].groupby("iteration", as_index=False).agg(
        incremental_cost_gbp=("england_incremental_cost_gbp", "sum"),
        incremental_qaly=("england_incremental_qaly", "sum"),
    )
    psa_validation = psa_total.merge(data["psa_total_reference"], on="iteration", suffixes=("_contract", "_reference"))
    psa_validation["cost_abs_error"] = psa_validation["incremental_cost_gbp_contract"] - psa_validation["incremental_cost_gbp_reference"]
    psa_validation["qaly_abs_error"] = psa_validation["incremental_qaly_contract"] - psa_validation["incremental_qaly_reference"]
    psa_validation.to_csv(OUT / "psa_validation.csv", index=False)

    summary = {
        "max_absolute_trace_error": float(trace_validation["max_absolute_trace_error"].max()),
        "max_absolute_summary_error": float(summary_validation["absolute_error"].abs().max()),
        "max_absolute_psa_cost_error": float(psa_validation["cost_abs_error"].abs().max()),
        "max_absolute_psa_qaly_error": float(psa_validation["qaly_abs_error"].abs().max()),
    }
    (OUT / "validation_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    assert summary["max_absolute_trace_error"] < 1e-12
    assert summary["max_absolute_summary_error"] < 1e-9
    assert summary["max_absolute_psa_cost_error"] < 1e-4
    assert summary["max_absolute_psa_qaly_error"] < 1e-8


if __name__ == "__main__":
    main()
