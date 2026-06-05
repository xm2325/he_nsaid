"""Independent deterministic reconstruction of NSAID Model C.

Model C represents oral NSAID prescribing in people concurrently taking an
oral anticoagulant.  The implementation rebuilds transition matrices from the
workbook parameter values and uses cached workbook traces only for regression
validation.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
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
    "Post-GI event",
    "Stroke",
    "Recurrent stroke",
    "Post-stroke",
    "Dead",
]
STATE_INDEX = {name: i for i, name in enumerate(STATE_NAMES)}


@dataclass(frozen=True)
class ModelCInputs:
    discount_qaly: float
    discount_cost: float
    time_horizon_years: float
    half_cycle: bool
    cycle_length: float
    cycles_per_year: int
    max_hpe_years: float
    cohort_age: float
    utility_by_age: List[Tuple[float, float]]
    p_gi_no_hpe: float
    p_gi_hpe: float
    p_ulcer_no_hpe: float
    p_ulcer_hpe: float
    p_serious_no_hpe: float
    p_serious_hpe: float
    p_repeat_gi: float
    p_stroke_no_hpe_by_age: List[Tuple[float, float]]
    p_stroke_hpe_by_age: List[Tuple[float, float]]
    p_stroke_repeat_by_age: List[Tuple[float, float]]
    p_stroke_recur_by_age: List[Tuple[float, float]]
    p_death_no_event_by_age: List[Tuple[float, float]]
    p_death_serious_by_age: List[Tuple[float, float]]
    p_death_ulcer_by_age: List[Tuple[float, float]]
    p_death_stroke_by_age: List[Tuple[float, float]]
    p_death_poststroke_by_age: List[Tuple[float, float]]
    costs_by_state: np.ndarray
    disutility_by_state: np.ndarray


def _lower_bound_lookup(age: float, bands: List[Tuple[float, float]]) -> float:
    """Match Excel ``MATCH(age, lower_bounds, 1)`` semantics."""
    eligible = [float(value) for lower, value in bands if float(lower) <= age]
    return eligible[-1] if eligible else float(bands[0][1])


def _pairs(reader: XlsmXmlReader, rows: range) -> List[Tuple[float, float]]:
    return [(float(reader.cell("Parameters", f"D{row}")), float(reader.cell("Parameters", f"M{row}"))) for row in rows]


def load_model_c_inputs(workbook_path: Path) -> ModelCInputs:
    r = XlsmXmlReader(workbook_path)
    cycles_per_year = int(float(r.cell("Parameters", "M251")))
    return ModelCInputs(
        discount_qaly=float(r.cell("Parameters", "M7")),
        discount_cost=float(r.cell("Parameters", "M8")),
        time_horizon_years=float(r.cell("Parameters", "M9")),
        half_cycle=bool(int(float(r.cell("Parameters", "M10")))),
        cycle_length=1.0 / cycles_per_year,
        cycles_per_year=cycles_per_year,
        max_hpe_years=float(r.cell("Parameters", "M252")),
        cohort_age=float(r.cell("Parameters", "M249")),
        utility_by_age=_pairs(r, range(427, 434)),
        p_gi_no_hpe=float(r.cell("Parameters", "M263")),
        p_gi_hpe=float(r.cell("Parameters", "M264")),
        p_ulcer_no_hpe=float(r.cell("Parameters", "M269")),
        p_ulcer_hpe=float(r.cell("Parameters", "M270")),
        p_serious_no_hpe=float(r.cell("Parameters", "M274")),
        p_serious_hpe=float(r.cell("Parameters", "M275")),
        p_repeat_gi=float(r.cell("Parameters", "M278")),
        p_stroke_no_hpe_by_age=_pairs(r, range(284, 287)),
        p_stroke_hpe_by_age=_pairs(r, range(287, 290)),
        p_stroke_repeat_by_age=_pairs(r, range(294, 297)),
        p_stroke_recur_by_age=_pairs(r, range(305, 308)),
        p_death_no_event_by_age=_pairs(r, range(325, 330)),
        p_death_serious_by_age=_pairs(r, range(333, 338)),
        p_death_ulcer_by_age=_pairs(r, range(340, 345)),
        p_death_stroke_by_age=_pairs(r, range(351, 356)),
        p_death_poststroke_by_age=_pairs(r, range(359, 364)),
        costs_by_state=np.array([float(r.cell("Parameters", f"M{row}")) for row in range(411, 424)], dtype=float),
        disutility_by_state=np.array([float(r.cell("Parameters", f"M{row}")) for row in range(438, 451)], dtype=float),
    )


def transition_matrix(inputs: ModelCInputs, age: float, crossing_hpe_duration: bool = False) -> np.ndarray:
    """Build the 13-state transition matrix for one quarterly cycle.

    ``crossing_hpe_duration`` reproduces the workbook conversion matrix used in
    the single cycle where the HPE duration boundary is crossed.  In that cycle,
    residual well-with-HPE mass moves to well-no-HPE while HPE event risks are
    still applied.
    """
    p_death = _lower_bound_lookup(age, inputs.p_death_no_event_by_age)
    p_death_ulcer = _lower_bound_lookup(age, inputs.p_death_ulcer_by_age)
    p_death_serious = _lower_bound_lookup(age, inputs.p_death_serious_by_age)
    p_death_stroke = _lower_bound_lookup(age, inputs.p_death_stroke_by_age)
    p_death_poststroke = _lower_bound_lookup(age, inputs.p_death_poststroke_by_age)
    p_stroke_no_hpe = _lower_bound_lookup(age, inputs.p_stroke_no_hpe_by_age)
    p_stroke_hpe = _lower_bound_lookup(age, inputs.p_stroke_hpe_by_age)
    p_stroke_repeat = _lower_bound_lookup(age, inputs.p_stroke_repeat_by_age)
    p_stroke_recur = _lower_bound_lookup(age, inputs.p_stroke_recur_by_age)

    m = np.zeros((13, 13), dtype=float)

    # Well no HPE
    m[0, 0] = 1.0 - inputs.p_gi_no_hpe - inputs.p_ulcer_no_hpe - inputs.p_serious_no_hpe - p_stroke_no_hpe - p_death
    m[0, 2] = inputs.p_gi_no_hpe
    m[0, 4] = inputs.p_ulcer_no_hpe
    m[0, 6] = inputs.p_serious_no_hpe
    m[0, 9] = p_stroke_no_hpe
    m[0, 12] = p_death

    # Well with HPE
    residual = 1.0 - inputs.p_gi_hpe - inputs.p_ulcer_hpe - inputs.p_serious_hpe - p_stroke_hpe - p_death
    m[1, 0 if crossing_hpe_duration else 1] = residual
    m[1, 2] = inputs.p_gi_hpe
    m[1, 4] = inputs.p_ulcer_hpe
    m[1, 6] = inputs.p_serious_hpe
    m[1, 9] = p_stroke_hpe
    m[1, 12] = p_death

    # GI discomfort and unresolved GI discomfort
    m[2, 3] = inputs.p_repeat_gi
    m[2, 8] = 1.0 - inputs.p_repeat_gi - p_death
    m[2, 12] = p_death
    m[3, 8] = 1.0 - p_death
    m[3, 12] = p_death

    # Symptomatic ulcer and unresolved ulcer
    m[4, 5] = inputs.p_repeat_gi
    m[4, 8] = 1.0 - inputs.p_repeat_gi - p_death_ulcer
    m[4, 12] = p_death_ulcer
    m[5, 8] = 1.0 - p_death_ulcer
    m[5, 12] = p_death_ulcer

    # Serious GI event and unresolved serious GI event
    m[6, 7] = inputs.p_repeat_gi
    m[6, 8] = 1.0 - inputs.p_repeat_gi - p_death_serious
    m[6, 12] = p_death_serious
    m[7, 8] = 1.0 - p_death_serious
    m[7, 12] = p_death_serious

    # Post-GI event follows the no-HPE acquisition risks
    m[8, 2] = inputs.p_gi_no_hpe
    m[8, 4] = inputs.p_ulcer_no_hpe
    m[8, 6] = inputs.p_serious_no_hpe
    m[8, 8] = 1.0 - inputs.p_gi_no_hpe - inputs.p_ulcer_no_hpe - inputs.p_serious_no_hpe - p_stroke_no_hpe - p_death
    m[8, 9] = p_stroke_no_hpe
    m[8, 12] = p_death

    # Stroke paths
    m[9, 10] = p_stroke_repeat
    m[9, 11] = 1.0 - p_stroke_repeat - p_death_stroke
    m[9, 12] = p_death_stroke
    m[10, 11] = 1.0 - p_death_stroke
    m[10, 12] = p_death_stroke
    m[11, 9] = p_stroke_recur
    m[11, 11] = 1.0 - p_stroke_recur - p_death_poststroke
    m[11, 12] = p_death_poststroke

    # Dead
    m[12, 12] = 1.0
    return m


def run_markov_trace(inputs: ModelCInputs, arm: str) -> pd.DataFrame:
    n_cycles = int(inputs.time_horizon_years * inputs.cycles_per_year)
    trace = np.zeros((n_cycles + 1, len(STATE_NAMES)), dtype=float)
    if arm == "HPE":
        trace[0, STATE_INDEX["Well with HPE"]] = 1.0
    elif arm == "No HPE":
        trace[0, STATE_INDEX["Well no HPE"]] = 1.0
    else:
        raise ValueError(f"Unknown arm: {arm}")

    ages = [inputs.cohort_age + i * inputs.cycle_length for i in range(n_cycles + 1)]
    for c in range(1, n_cycles + 1):
        start_time = (c - 1) * inputs.cycle_length
        end_time = c * inputs.cycle_length
        crossing = arm == "HPE" and start_time < inputs.max_hpe_years <= end_time
        trace[c] = trace[c - 1] @ transition_matrix(inputs, age=ages[c - 1], crossing_hpe_duration=crossing)

    df = pd.DataFrame(trace, columns=STATE_NAMES)
    df.insert(0, "cycle", range(n_cycles + 1))
    df.insert(1, "time_years", [i * inputs.cycle_length for i in range(n_cycles + 1)])
    df.insert(2, "age", ages)
    return df


def summarise_trace(inputs: ModelCInputs, trace: pd.DataFrame) -> Dict[str, float]:
    states = trace[STATE_NAMES].to_numpy(dtype=float)
    n_cycles = len(trace) - 1
    alive = np.ones(len(STATE_NAMES), dtype=float)
    alive[STATE_INDEX["Dead"]] = 0.0
    totals = {"total_ly": 0.0, "total_qaly": 0.0, "discounted_qaly": 0.0, "total_cost": 0.0, "discounted_cost": 0.0}

    for c in range(n_cycles):
        start, end = states[c], states[c + 1]
        occupancy = 0.5 * (start + end) if inputs.half_cycle else start
        utility = _lower_bound_lookup(float(trace.iloc[c]["age"]), inputs.utility_by_age) + inputs.disutility_by_state
        utility = utility.copy()
        utility[STATE_INDEX["Dead"]] = 0.0
        ly = start @ alive * inputs.cycle_length
        qaly = occupancy @ utility * inputs.cycle_length
        cost = occupancy @ inputs.costs_by_state
        discount_time = c * inputs.cycle_length
        totals["total_ly"] += float(ly)
        totals["total_qaly"] += float(qaly)
        totals["discounted_qaly"] += float(qaly / ((1.0 + inputs.discount_qaly) ** discount_time))
        totals["total_cost"] += float(cost)
        totals["discounted_cost"] += float(cost / ((1.0 + inputs.discount_cost) ** discount_time))
    return totals


def workbook_reference_totals(workbook_path: Path) -> Dict[str, Dict[str, float]]:
    r = XlsmXmlReader(workbook_path)
    return {
        "HPE": {
            "discounted_cost": float(r.cell("C.Costs", "T5")),
            "total_cost": float(r.cell("C.Costs", "T4")),
            "discounted_qaly": float(r.cell("C.QALYs", "T5")),
            "total_qaly": float(r.cell("C.QALYs", "T4")),
            "total_ly": float(r.cell("C.Markov", "U4")),
        },
        "No HPE": {
            "discounted_cost": float(r.cell("C.Costs", "AI5")),
            "total_cost": float(r.cell("C.Costs", "AI4")),
            "discounted_qaly": float(r.cell("C.QALYs", "AI5")),
            "total_qaly": float(r.cell("C.QALYs", "AI4")),
            "total_ly": float(r.cell("C.Markov", "AL4")),
        },
    }


def trace_validation_against_workbook(workbook_path: Path, inputs: ModelCInputs) -> Dict[str, float]:
    r = XlsmXmlReader(workbook_path)
    columns = {
        "HPE": ["H", "I", "J", "K", "L", "M", "N", "O", "P", "Q", "R", "S", "T"],
        "No HPE": ["Y", "Z", "AA", "AB", "AC", "AD", "AE", "AF", "AG", "AH", "AI", "AJ", "AK"],
    }
    max_errors: Dict[str, float] = {}
    for arm, cols in columns.items():
        trace = run_markov_trace(inputs, arm)
        error = 0.0
        for i in range(len(trace)):
            row = 10 + i
            workbook_vals = np.array([float(r.cell("C.Markov", f"{col}{row}") or 0.0) for col in cols], dtype=float)
            python_vals = trace.iloc[i][STATE_NAMES].to_numpy(dtype=float)
            error = max(error, float(np.max(np.abs(python_vals - workbook_vals))))
        max_errors[arm] = error
    return max_errors


def run_independent_model_c(workbook_path: Path, output_dir: Path) -> Dict[str, Dict[str, float]]:
    output_dir.mkdir(parents=True, exist_ok=True)
    inputs = load_model_c_inputs(workbook_path)
    reference = workbook_reference_totals(workbook_path)
    summaries: Dict[str, Dict[str, float]] = {}
    rows = []

    for arm in ["HPE", "No HPE"]:
        trace = run_markov_trace(inputs, arm)
        trace.to_csv(output_dir / f"independent_model_C_trace_{arm.replace(' ', '_').lower()}.csv", index=False)
        summary = summarise_trace(inputs, trace)
        summaries[arm] = summary
        for metric, value in summary.items():
            ref = reference[arm][metric]
            rows.append({
                "arm": arm,
                "metric": metric,
                "independent_python": value,
                "workbook_cached": ref,
                "absolute_error": value - ref,
                "relative_error": (value - ref) / ref if ref != 0 else math.nan,
            })

    comparison = pd.DataFrame(rows)
    comparison.to_csv(output_dir / "independent_model_C_vs_workbook.csv", index=False)
    payload = {
        **summaries,
        "incremental_HPE_minus_No_HPE": {
            metric: float(summaries["HPE"][metric] - summaries["No HPE"][metric])
            for metric in summaries["HPE"]
        },
    }
    (output_dir / "independent_model_C_summary.json").write_text(json.dumps(payload, indent=2))

    trace_errors = trace_validation_against_workbook(workbook_path, inputs)
    validation = {
        "max_absolute_trace_error_HPE": trace_errors["HPE"],
        "max_absolute_trace_error_No_HPE": trace_errors["No HPE"],
        "max_absolute_reward_error": float(comparison["absolute_error"].abs().max()),
        "all_trace_errors_below_1e-12": bool(max(trace_errors.values()) < 1e-12),
        "all_reward_errors_below_1e-10": bool(comparison["absolute_error"].abs().max() < 1e-10),
    }
    (output_dir / "independent_model_C_validation_summary.json").write_text(json.dumps(validation, indent=2))
    return payload


def with_hpe_duration(inputs: ModelCInputs, years: float) -> ModelCInputs:
    return replace(inputs, max_hpe_years=float(years))
