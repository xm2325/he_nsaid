"""Reusable deterministic gastrointestinal NSAID state-transition engine.

The engine independently reconstructs workbook models A and B from parameter
values.  It does not read cached Markov traces when calculating results; cached
traces are used only for regression validation.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple

import json
import math
import numpy as np
import pandas as pd

from .xlsm_reader import XlsmXmlReader

STATE_NAMES = [
    "Well no HPE",
    "Well with HPE",
    "GI discomfort",
    "Unresolved GI discomfort",
    "Symptomatic ulcer",
    "Unresolved ulcer",
    "Serious GI event",
    "Unresolved serious GI event",
    "Post-event",
    "Dead",
]
STATE_INDEX = {name: i for i, name in enumerate(STATE_NAMES)}


@dataclass
class GIModelInputs:
    discount_qaly: float
    discount_cost: float
    time_horizon_years: float
    half_cycle: bool
    cycle_length: float
    cycles_per_year: int
    max_hpe_years: float
    cohort_age: float
    gp_utility_by_age: List[Tuple[float, float, float]]
    p_death_gp_by_age: List[Tuple[float, float]]
    p_death_ulcer_by_age: List[Tuple[float, float]]
    p_death_serious_by_age: List[Tuple[float, float]]
    p_repeat_event: float
    p_gi_no_hpe: float
    p_gi_hpe: float
    p_ulcer_no_hpe: float
    p_ulcer_hpe: float
    p_serious_no_hpe: float
    p_serious_hpe: float
    costs_by_state: np.ndarray
    disutility_by_state: np.ndarray


def _age_lookup(age: float, bands: List[Tuple[float, ...]]) -> float:
    """Match Excel ``MATCH(age, lower_bounds, 1)`` semantics.

    The workbook uses the largest age-band lower bound that is less than or
    equal to the current age.  It does not switch only at the inclusive upper
    endpoint stored for display.  For example, 74.25 remains in the 70--74
    lookup band until age reaches 75.
    """
    candidates = [(float(item[0]), float(item[-1])) for item in bands]
    eligible = [value for lower, value in candidates if lower <= age]
    return eligible[-1] if eligible else candidates[0][1]


def load_gi_model_inputs(workbook_path: Path, model_id: str) -> GIModelInputs:
    model_id = model_id.upper()
    if model_id not in {"A", "B"}:
        raise ValueError(f"The shared GI engine currently supports models A and B, got: {model_id}")
    r = XlsmXmlReader(workbook_path)
    cycle_length = float(r.cell("Parameters", "M172")) ** -1
    cycles_per_year = int(r.cell("Parameters", "M172"))
    gp_utility = [
        (50.0, 54.0, float(r.cell("Parameters", "M71"))),
        (55.0, 59.0, float(r.cell("Parameters", "M72"))),
        (60.0, 64.0, float(r.cell("Parameters", "M73"))),
        (65.0, 69.0, float(r.cell("Parameters", "M74"))),
        (70.0, 74.0, float(r.cell("Parameters", "M75"))),
        (75.0, 79.0, float(r.cell("Parameters", "M76"))),
        (80.0, 84.0, float(r.cell("Parameters", "M77"))),
        (85.0, 89.0, float(r.cell("Parameters", "M78"))),
    ]
    p_death_gp = [
        (55.0, float(r.cell("Parameters", "M200"))),
        (60.0, float(r.cell("Parameters", "M201"))),
        (65.0, float(r.cell("Parameters", "M202"))),
        (70.0, float(r.cell("Parameters", "M203"))),
        (75.0, float(r.cell("Parameters", "M204"))),
    ]
    p_death_ulcer = [
        (55.0, float(r.cell("Parameters", "M207"))),
        (60.0, float(r.cell("Parameters", "M208"))),
        (65.0, float(r.cell("Parameters", "M209"))),
        (70.0, float(r.cell("Parameters", "M210"))),
        (75.0, float(r.cell("Parameters", "M211"))),
    ]
    p_death_serious = [
        (55.0, float(r.cell("Parameters", "M215"))),
        (60.0, float(r.cell("Parameters", "M216"))),
        (65.0, float(r.cell("Parameters", "M217"))),
        (70.0, float(r.cell("Parameters", "M218"))),
        (75.0, float(r.cell("Parameters", "M219"))),
    ]
    costs = np.array([float(r.cell("Parameters", f"M{row}")) for row in range(224, 234)], dtype=float)
    disutil = np.array([float(r.cell("Parameters", f"M{row}")) for row in range(236, 246)], dtype=float)
    cohort_age_cell = "M170" if model_id == "A" else "M171"
    return GIModelInputs(
        discount_qaly=float(r.cell("Parameters", "M7")),
        discount_cost=float(r.cell("Parameters", "M8")),
        time_horizon_years=float(r.cell("Parameters", "M9")),
        half_cycle=bool(int(r.cell("Parameters", "M10"))),
        cycle_length=cycle_length,
        cycles_per_year=cycles_per_year,
        max_hpe_years=float(r.cell("Parameters", "M173")),
        cohort_age=float(r.cell("Parameters", cohort_age_cell)),
        gp_utility_by_age=gp_utility,
        p_death_gp_by_age=p_death_gp,
        p_death_ulcer_by_age=p_death_ulcer,
        p_death_serious_by_age=p_death_serious,
        p_repeat_event=float(r.cell("Parameters", "M197")),
        p_gi_no_hpe=float(r.cell("Parameters", "M184")),
        p_gi_hpe=float(r.cell("Parameters", "M183")),
        p_ulcer_no_hpe=float(r.cell("Parameters", "M189")),
        p_ulcer_hpe=float(r.cell("Parameters", "M188")),
        p_serious_no_hpe=float(r.cell("Parameters", "M194")),
        p_serious_hpe=float(r.cell("Parameters", "M193")),
        costs_by_state=costs,
        disutility_by_state=disutil,
    )


def transition_matrix(inputs: GIModelInputs, age: float, use_hpe_acquisition: bool, hpe_expired: bool = False) -> np.ndarray:
    p_gp = _age_lookup(age, inputs.p_death_gp_by_age)
    p_du = _age_lookup(age, inputs.p_death_ulcer_by_age)
    p_ds = _age_lookup(age, inputs.p_death_serious_by_age)

    use_hpe_event_risks = use_hpe_acquisition or hpe_expired
    p_gi = inputs.p_gi_hpe if use_hpe_event_risks else inputs.p_gi_no_hpe
    p_ul = inputs.p_ulcer_hpe if use_hpe_event_risks else inputs.p_ulcer_no_hpe
    p_sg = inputs.p_serious_hpe if use_hpe_event_risks else inputs.p_serious_no_hpe

    mat = np.zeros((10, 10), dtype=float)

    # Well no HPE
    mat[0, 0] = 1.0 - p_gp - inputs.p_gi_no_hpe - inputs.p_ulcer_no_hpe - inputs.p_serious_no_hpe
    mat[0, 2] = inputs.p_gi_no_hpe
    mat[0, 4] = inputs.p_ulcer_no_hpe
    mat[0, 6] = inputs.p_serious_no_hpe
    mat[0, 9] = p_gp

    # Well with HPE
    if hpe_expired:
        # Workbook conversion TPM: any residual well-with-HPE mass moves to
        # well-no-HPE, while event risks for this crossing cycle still use
        # the HPE probabilities.
        mat[1, 0] = 1.0 - p_gp - p_gi - p_ul - p_sg
        mat[1, 2] = p_gi
        mat[1, 4] = p_ul
        mat[1, 6] = p_sg
        mat[1, 9] = p_gp
    else:
        mat[1, 1] = 1.0 - p_gp - p_gi - p_ul - p_sg
        mat[1, 2] = p_gi
        mat[1, 4] = p_ul
        mat[1, 6] = p_sg
        mat[1, 9] = p_gp

    # GI discomfort
    mat[2, 3] = inputs.p_repeat_event
    mat[2, 8] = 1.0 - inputs.p_repeat_event - p_gp
    mat[2, 9] = p_gp

    # Unresolved GI discomfort
    mat[3, 8] = 1.0 - p_gp
    mat[3, 9] = p_gp

    # Symptomatic ulcer
    mat[4, 5] = inputs.p_repeat_event
    mat[4, 8] = 1.0 - inputs.p_repeat_event - p_du
    mat[4, 9] = p_du

    # Unresolved ulcer
    mat[5, 8] = 1.0 - p_du
    mat[5, 9] = p_du

    # Serious GI event
    mat[6, 7] = inputs.p_repeat_event
    mat[6, 8] = 1.0 - inputs.p_repeat_event - p_ds
    mat[6, 9] = p_ds

    # Unresolved serious GI event
    mat[7, 8] = 1.0 - p_ds
    mat[7, 9] = p_ds

    # Post-event behaves like well no HPE, but remains in post-event if no new event
    mat[8, 2] = inputs.p_gi_no_hpe
    mat[8, 4] = inputs.p_ulcer_no_hpe
    mat[8, 6] = inputs.p_serious_no_hpe
    mat[8, 8] = 1.0 - p_gp - inputs.p_gi_no_hpe - inputs.p_ulcer_no_hpe - inputs.p_serious_no_hpe
    mat[8, 9] = p_gp

    # Dead
    mat[9, 9] = 1.0
    return mat


def run_markov_trace(inputs: GIModelInputs, arm: str) -> pd.DataFrame:
    n_cycles = int(inputs.time_horizon_years * inputs.cycles_per_year)
    trace = np.zeros((n_cycles + 1, 10), dtype=float)
    if arm == "HPE":
        trace[0, STATE_INDEX["Well with HPE"]] = 1.0
    elif arm == "No HPE":
        trace[0, STATE_INDEX["Well no HPE"]] = 1.0
    else:
        raise ValueError(f"Unknown arm: {arm}")

    ages = [inputs.cohort_age + i * inputs.cycle_length for i in range(n_cycles + 1)]

    for c in range(1, n_cycles + 1):
        age_start = ages[c - 1]
        end_time = c * inputs.cycle_length
        use_hpe = arm == "HPE" and (end_time < inputs.max_hpe_years)
        hpe_expired = arm == "HPE" and (end_time >= inputs.max_hpe_years)
        mat = transition_matrix(inputs, age_start, use_hpe_acquisition=use_hpe, hpe_expired=hpe_expired)
        trace[c] = trace[c - 1] @ mat

    df = pd.DataFrame(trace, columns=STATE_NAMES)
    df.insert(0, "cycle", range(n_cycles + 1))
    df.insert(1, "time_years", [i * inputs.cycle_length for i in range(n_cycles + 1)])
    df.insert(2, "age", ages)
    return df


def summarise_trace(inputs: GIModelInputs, trace: pd.DataFrame) -> Dict[str, float]:
    states = trace[STATE_NAMES].to_numpy(dtype=float)
    n_cycles = len(trace) - 1
    alive_weight = np.ones(10, dtype=float)
    alive_weight[STATE_INDEX["Dead"]] = 0.0

    per_cycle_ly = []
    per_cycle_qaly = []
    per_cycle_cost = []
    per_cycle_dqaly = []
    per_cycle_dcost = []

    for c in range(n_cycles):
        start = states[c]
        end = states[c + 1]
        occ = 0.5 * (start + end) if inputs.half_cycle else start
        age = float(trace.iloc[c]["age"])
        genpop_u = _age_lookup(age, inputs.gp_utility_by_age)
        state_utils = genpop_u + inputs.disutility_by_state
        state_utils[STATE_INDEX["Dead"]] = 0.0
        # The workbook LY formula sums cycle-start survival probabilities
        # directly from A.Markov, without half-cycle correction.
        ly = start @ alive_weight * inputs.cycle_length
        qaly = occ @ state_utils * inputs.cycle_length
        cost = occ @ inputs.costs_by_state
        # Workbook formula discounts with the cycle index in D11:D50, so the
        # first cycle has exponent 0.  The workbook also references DQALYs for
        # both QALYs and costs; the default QALY and cost rates are both 3.5%.
        discount_time = c * inputs.cycle_length
        dqaly = qaly / ((1.0 + inputs.discount_qaly) ** discount_time)
        dcost = cost / ((1.0 + inputs.discount_qaly) ** discount_time)
        per_cycle_ly.append(ly)
        per_cycle_qaly.append(qaly)
        per_cycle_cost.append(cost)
        per_cycle_dqaly.append(dqaly)
        per_cycle_dcost.append(dcost)

    summary = {
        "total_ly": float(np.sum(per_cycle_ly)),
        "total_qaly": float(np.sum(per_cycle_qaly)),
        "discounted_qaly": float(np.sum(per_cycle_dqaly)),
        "total_cost": float(np.sum(per_cycle_cost)),
        "discounted_cost": float(np.sum(per_cycle_dcost)),
    }
    return summary


def workbook_reference_totals(workbook_path: Path, model_id: str) -> Dict[str, Dict[str, float]]:
    model_id = model_id.upper()
    if model_id not in {"A", "B"}:
        raise ValueError(f"Unsupported GI model: {model_id}")
    r = XlsmXmlReader(workbook_path)
    ref = {
        "HPE": {
            "discounted_cost": float(r.cell(f"{model_id}.Costs", "Q5")),
            "total_cost": float(r.cell(f"{model_id}.Costs", "Q4")),
            "discounted_qaly": float(r.cell(f"{model_id}.QALYs", "Q5")),
            "total_qaly": float(r.cell(f"{model_id}.QALYs", "Q4")),
            "total_ly": float(r.cell(f"{model_id}.Markov", "R4")),
        },
        "No HPE": {
            "discounted_cost": float(r.cell(f"{model_id}.Costs", "AC5")),
            "total_cost": float(r.cell(f"{model_id}.Costs", "AC4")),
            "discounted_qaly": float(r.cell(f"{model_id}.QALYs", "AC5")),
            "total_qaly": float(r.cell(f"{model_id}.QALYs", "AC4")),
            "total_ly": float(r.cell(f"{model_id}.Markov", "AE4")),
        },
    }
    return ref



def trace_validation_against_workbook(workbook_path: Path, inputs: GIModelInputs, model_id: str) -> Dict[str, float]:
    """Return the maximum absolute state-occupancy error for each arm."""
    r = XlsmXmlReader(workbook_path)
    columns = {
        "HPE": list("HIJKLMNOPQ"),
        "No HPE": ["U", "V", "W", "X", "Y", "Z", "AA", "AB", "AC", "AD"],
    }
    max_errors: Dict[str, float] = {}
    for arm, cols in columns.items():
        trace = run_markov_trace(inputs, arm)
        max_error = 0.0
        for i in range(len(trace)):
            xlrow = 10 + i
            workbook_vals = np.array([float(r.cell(f"{model_id.upper()}.Markov", f"{col}{xlrow}") or 0.0) for col in cols])
            python_vals = trace.iloc[i][STATE_NAMES].to_numpy(dtype=float)
            max_error = max(max_error, float(np.max(np.abs(python_vals - workbook_vals))))
        max_errors[arm] = max_error
    return max_errors

def run_independent_gi_model(workbook_path: Path, output_dir: Path, model_id: str) -> Dict[str, Dict[str, float]]:
    output_dir.mkdir(parents=True, exist_ok=True)
    model_id = model_id.upper()
    inputs = load_gi_model_inputs(workbook_path, model_id=model_id)
    reference = workbook_reference_totals(workbook_path, model_id=model_id)
    all_results: Dict[str, Dict[str, float]] = {}
    comp_rows = []

    for arm in ["HPE", "No HPE"]:
        trace = run_markov_trace(inputs, arm=arm)
        trace.to_csv(output_dir / f"independent_model_{model_id}_trace_{arm.replace(' ', '_').lower()}.csv", index=False)
        summary = summarise_trace(inputs, trace)
        all_results[arm] = summary
        for metric, value in summary.items():
            ref = reference[arm][metric]
            comp_rows.append({
                "arm": arm,
                "metric": metric,
                "independent_python": value,
                "workbook_cached": ref,
                "absolute_error": value - ref,
                "relative_error": (value - ref) / ref if ref != 0 else math.nan,
            })

    comparison = pd.DataFrame(comp_rows)
    comparison.to_csv(output_dir / f"independent_model_{model_id}_vs_workbook.csv", index=False)

    summary_payload = {arm: {k: float(v) for k, v in vals.items()} for arm, vals in all_results.items()}
    incremental = {
        metric: float(all_results["HPE"][metric] - all_results["No HPE"][metric])
        for metric in all_results["HPE"]
    }
    summary_payload["incremental_HPE_minus_No_HPE"] = incremental
    (output_dir / f"independent_model_{model_id}_summary.json").write_text(json.dumps(summary_payload, indent=2))

    trace_errors = trace_validation_against_workbook(workbook_path, inputs, model_id=model_id)
    validation = {
        "max_absolute_trace_error_HPE": trace_errors["HPE"],
        "max_absolute_trace_error_No_HPE": trace_errors["No HPE"],
        "max_absolute_reward_error": float(comparison["absolute_error"].abs().max()),
        "all_trace_errors_below_1e-12": bool(max(trace_errors.values()) < 1e-12),
        "all_reward_errors_below_1e-10": bool(comparison["absolute_error"].abs().max() < 1e-10),
    }
    (output_dir / f"independent_model_{model_id}_validation_summary.json").write_text(json.dumps(validation, indent=2))
    return summary_payload
