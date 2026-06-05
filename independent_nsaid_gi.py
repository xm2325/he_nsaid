"""Independent deterministic reconstruction of NSAID Model E (chronic kidney disease)."""
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
    "No event no NSAID",
    "No event + NSAID",
    "Primary care AKI",
    "Secondary care AKI (no RRT)",
    "Secondary care AKI (with RRT)",
    "Post-event CKD stage 3b-4",
    "ESRD",
    "ESRD+RRT",
    "Transplant",
    "Post-transplant",
    "Dead (AKI)",
    "Dead (other)",
]
STATE_INDEX = {name: i for i, name in enumerate(STATE_NAMES)}


@dataclass(frozen=True)
class ModelEInputs:
    discount_qaly: float
    discount_cost: float
    time_horizon_years: float
    half_cycle: bool
    cycle_length: float
    cycles_per_year: int
    max_hpe_years: float
    cohort_age: float
    genpop_utility_by_age: List[Tuple[float, float]]
    aki_primary_no_nsaid_by_age: List[Tuple[float, float]]
    aki_primary_with_nsaid_by_age: List[Tuple[float, float]]
    aki_secondary_no_rrt_no_nsaid_by_age: List[Tuple[float, float]]
    aki_secondary_no_rrt_with_nsaid_by_age: List[Tuple[float, float]]
    aki_secondary_rrt_no_nsaid_by_age: List[Tuple[float, float]]
    aki_secondary_rrt_with_nsaid_by_age: List[Tuple[float, float]]
    death_primary_aki_by_age: List[Tuple[float, float]]
    death_secondary_no_rrt_by_age: List[Tuple[float, float]]
    death_secondary_rrt_by_age: List[Tuple[float, float]]
    death_other_by_age_state: Dict[Tuple[float, str], float]
    p_ckd5_from_3b4: float
    p_ckd5d_from_3b4: float
    p_ckd5d_from_5: float
    p_tx_from_3b4: float
    p_tx_from_5: float
    p_tx_from_5d: float
    p_tx_graft_failure: float
    p_ckd5_post_primary_aki: float
    p_ckd5_post_secondary_aki: float
    p_ckd5d_post_secondary_aki: float
    p_ckd5_post_secondary_aki_no_rrt: float
    costs_by_state: np.ndarray
    disutility_by_state: np.ndarray


def _lookup_lower_bound(age: float, values: List[Tuple[float, float]]) -> float:
    """Excel MATCH(age, lower_bounds, 1): largest lower bound <= age."""
    result = float(values[0][1])
    for lower, value in values:
        if age < lower:
            break
        result = float(value)
    return result


def _age_group(age: float) -> float:
    if age >= 85.0:
        return 85.0
    if age >= 80.0:
        return 80.0
    if age >= 75.0:
        return 75.0
    return 70.0


def load_model_e_inputs(workbook_path: Path) -> ModelEInputs:
    r = XlsmXmlReader(workbook_path)
    cycles_per_year = int(float(r.cell("Parameters", "M742")))

    def rows_to_age_values(rows: range) -> List[Tuple[float, float]]:
        return [(float(r.cell("Parameters", f"D{row}")), float(r.cell("Parameters", f"M{row}"))) for row in rows]

    death_other: Dict[Tuple[float, str], float] = {}
    for row in range(891, 914):
        age = r.cell("Parameters", f"D{row}")
        state = r.cell("Parameters", f"E{row}")
        value = r.cell("Parameters", f"M{row}")
        if age is None or state is None or value is None:
            continue
        stage = str(int(float(state))) if isinstance(state, (int, float)) and float(state).is_integer() else str(state)
        death_other[(float(age), stage)] = float(value)

    return ModelEInputs(
        discount_qaly=float(r.cell("Parameters", "M7")),
        discount_cost=float(r.cell("Parameters", "M8")),
        time_horizon_years=float(r.cell("Parameters", "M9")),
        half_cycle=bool(int(float(r.cell("Parameters", "M10")))),
        cycle_length=1.0 / cycles_per_year,
        cycles_per_year=cycles_per_year,
        max_hpe_years=float(r.cell("Parameters", "M743")),
        cohort_age=float(r.cell("Parameters", "M740")),
        genpop_utility_by_age=rows_to_age_values(range(71, 79)),
        aki_primary_no_nsaid_by_age=rows_to_age_values(range(817, 821)),
        aki_primary_with_nsaid_by_age=rows_to_age_values(range(833, 837)),
        aki_secondary_no_rrt_no_nsaid_by_age=rows_to_age_values(range(822, 826)),
        aki_secondary_no_rrt_with_nsaid_by_age=rows_to_age_values(range(838, 842)),
        aki_secondary_rrt_no_nsaid_by_age=rows_to_age_values(range(827, 831)),
        aki_secondary_rrt_with_nsaid_by_age=rows_to_age_values(range(843, 847)),
        death_primary_aki_by_age=rows_to_age_values(range(864, 868)),
        death_secondary_no_rrt_by_age=rows_to_age_values(range(869, 873)),
        death_secondary_rrt_by_age=rows_to_age_values(range(874, 878)),
        death_other_by_age_state=death_other,
        p_ckd5_from_3b4=float(r.cell("Parameters", "M755")),
        p_ckd5d_from_3b4=float(r.cell("Parameters", "M763")),
        p_ckd5d_from_5=float(r.cell("Parameters", "M764")),
        p_tx_from_3b4=float(r.cell("Parameters", "M771")),
        p_tx_from_5=float(r.cell("Parameters", "M772")),
        p_tx_from_5d=float(r.cell("Parameters", "M773")),
        p_tx_graft_failure=float(r.cell("Parameters", "M776")),
        p_ckd5_post_primary_aki=float(r.cell("Parameters", "M881")),
        p_ckd5_post_secondary_aki=float(r.cell("Parameters", "M878")),
        p_ckd5d_post_secondary_aki=float(r.cell("Parameters", "M879")),
        p_ckd5_post_secondary_aki_no_rrt=float(r.cell("Parameters", "M880")),
        costs_by_state=np.array([float(r.cell("Parameters", f"M{row}")) for row in range(1035, 1047)], dtype=float),
        disutility_by_state=np.array([float(r.cell("Parameters", f"M{row}")) for row in range(1074, 1086)], dtype=float),
    )


def _death_other(inputs: ModelEInputs, age: float, stage: str) -> float:
    return float(inputs.death_other_by_age_state[(_age_group(age), stage)])


def transition_matrix(inputs: ModelEInputs, age: float, crossing_hpe_duration: bool = False) -> np.ndarray:
    """Build the 12-state CKD matrix for one quarter.

    The boundary-crossing matrix matches the workbook correction matrix: in the
    correction cycle, a patient who remains free of an acute event moves from
    ``No event + NSAID`` to ``No event no NSAID`` while acute-event risks remain
    those of the NSAID-exposed row for that cycle.
    """
    m = np.zeros((12, 12), dtype=float)
    death_3b4 = _death_other(inputs, age, "3B-4")
    death_5 = _death_other(inputs, age, "5")
    death_5d = _death_other(inputs, age, "5D")
    death_gp = _death_other(inputs, age, "GP")

    # State 1: no event, no NSAID.
    m[0, 2] = _lookup_lower_bound(age, inputs.aki_primary_no_nsaid_by_age)
    m[0, 3] = _lookup_lower_bound(age, inputs.aki_secondary_no_rrt_no_nsaid_by_age)
    m[0, 4] = _lookup_lower_bound(age, inputs.aki_secondary_rrt_no_nsaid_by_age)
    m[0, 6] = inputs.p_ckd5_from_3b4
    m[0, 7] = inputs.p_ckd5d_from_3b4
    m[0, 11] = death_3b4
    m[0, 0] = 1.0 - float(m[0].sum())

    # State 2: no event, NSAID exposed.
    m[1, 2] = _lookup_lower_bound(age, inputs.aki_primary_with_nsaid_by_age)
    m[1, 3] = _lookup_lower_bound(age, inputs.aki_secondary_no_rrt_with_nsaid_by_age)
    m[1, 4] = _lookup_lower_bound(age, inputs.aki_secondary_rrt_with_nsaid_by_age)
    m[1, 6] = inputs.p_ckd5_from_3b4
    m[1, 7] = inputs.p_ckd5d_from_3b4
    m[1, 11] = death_3b4
    m[1, 0 if crossing_hpe_duration else 1] = 1.0 - float(m[1].sum())

    # State 3: primary-care AKI.
    m[2, 6] = inputs.p_ckd5_post_primary_aki
    m[2, 10] = _lookup_lower_bound(age, inputs.death_primary_aki_by_age)
    m[2, 5] = 1.0 - float(m[2].sum())

    # State 4: secondary-care AKI without renal replacement therapy (RRT).
    m[3, 6] = inputs.p_ckd5_post_secondary_aki
    m[3, 10] = _lookup_lower_bound(age, inputs.death_secondary_no_rrt_by_age)
    m[3, 5] = 1.0 - float(m[3].sum())

    # State 5: secondary-care AKI with RRT.
    m[4, 6] = inputs.p_ckd5_post_secondary_aki_no_rrt
    m[4, 7] = inputs.p_ckd5d_post_secondary_aki
    m[4, 10] = _lookup_lower_bound(age, inputs.death_secondary_rrt_by_age)
    m[4, 5] = 1.0 - float(m[4].sum())

    # State 6: post-event CKD stage 3b-4.
    m[5, 2] = _lookup_lower_bound(age, inputs.aki_primary_no_nsaid_by_age)
    m[5, 3] = _lookup_lower_bound(age, inputs.aki_secondary_no_rrt_no_nsaid_by_age)
    m[5, 4] = _lookup_lower_bound(age, inputs.aki_secondary_rrt_no_nsaid_by_age)
    m[5, 6] = inputs.p_ckd5_from_3b4
    m[5, 7] = inputs.p_ckd5d_from_3b4
    m[5, 8] = inputs.p_tx_from_3b4
    m[5, 11] = death_3b4
    m[5, 5] = 1.0 - float(m[5].sum())

    # State 7: end-stage renal disease (ESRD).
    m[6, 7] = inputs.p_ckd5d_from_5
    m[6, 8] = inputs.p_tx_from_5
    m[6, 11] = death_5
    m[6, 6] = 1.0 - float(m[6].sum())

    # State 8: ESRD with RRT.
    m[7, 8] = inputs.p_tx_from_5d
    m[7, 11] = death_5d
    m[7, 7] = 1.0 - float(m[7].sum())

    # States 9 and 10: transplant and post-transplant.
    for from_idx in [8, 9]:
        m[from_idx, 7] = inputs.p_tx_graft_failure
        m[from_idx, 11] = death_gp
        m[from_idx, 9] = 1.0 - float(m[from_idx].sum())

    # Death states.
    m[10, 10] = 1.0
    m[11, 11] = 1.0
    return m


def run_markov_trace(inputs: ModelEInputs, arm: str) -> pd.DataFrame:
    n_cycles = int(inputs.time_horizon_years * inputs.cycles_per_year)
    trace = np.zeros((n_cycles + 1, len(STATE_NAMES)), dtype=float)
    if arm == "HPE":
        trace[0, STATE_INDEX["No event + NSAID"]] = 1.0
    elif arm == "No HPE":
        trace[0, STATE_INDEX["No event no NSAID"]] = 1.0
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


def summarise_trace(inputs: ModelEInputs, trace: pd.DataFrame) -> Dict[str, float]:
    states = trace[STATE_NAMES].to_numpy(dtype=float)
    alive = np.ones(len(STATE_NAMES), dtype=float)
    alive[STATE_INDEX["Dead (AKI)"]] = 0.0
    alive[STATE_INDEX["Dead (other)"]] = 0.0
    totals = {"total_ly": 0.0, "discounted_ly": 0.0, "total_qaly": 0.0, "discounted_qaly": 0.0, "total_cost": 0.0, "discounted_cost": 0.0}

    for c in range(len(trace) - 1):
        start, end = states[c], states[c + 1]
        occupancy = 0.5 * (start + end) if inputs.half_cycle else start
        genpop_u = _lookup_lower_bound(float(trace.iloc[c]["age"]), inputs.genpop_utility_by_age)
        utility = genpop_u + inputs.disutility_by_state
        utility[STATE_INDEX["Dead (AKI)"]] = 0.0
        utility[STATE_INDEX["Dead (other)"]] = 0.0
        ly = float(start @ alive * inputs.cycle_length)
        qaly = float(occupancy @ utility * inputs.cycle_length)
        cost = float(occupancy @ inputs.costs_by_state)
        discount_time = c * inputs.cycle_length
        discount = (1.0 + inputs.discount_qaly) ** discount_time
        totals["total_ly"] += ly
        totals["discounted_ly"] += ly / discount
        totals["total_qaly"] += qaly
        totals["discounted_qaly"] += qaly / discount
        totals["total_cost"] += cost
        # E.Costs mirrors the workbook formula and therefore references DQALYs.
        totals["discounted_cost"] += cost / discount
    return totals


def workbook_reference_totals(workbook_path: Path) -> Dict[str, Dict[str, float]]:
    r = XlsmXmlReader(workbook_path)
    return {
        "HPE": {
            "total_ly": float(r.cell("E.Markov", "U4")),
            "discounted_ly": float(r.cell("E.Markov", "U5")),
            "total_qaly": float(r.cell("E.QALYs", "T4")),
            "discounted_qaly": float(r.cell("E.QALYs", "T5")),
            "total_cost": float(r.cell("E.Costs", "T4")),
            "discounted_cost": float(r.cell("E.Costs", "T5")),
        },
        "No HPE": {
            "total_ly": float(r.cell("E.Markov", "AO4")),
            "discounted_ly": float(r.cell("E.Markov", "AO5")),
            "total_qaly": float(r.cell("E.QALYs", "AH4")),
            "discounted_qaly": float(r.cell("E.QALYs", "AH5")),
            "total_cost": float(r.cell("E.Costs", "AH4")),
            "discounted_cost": float(r.cell("E.Costs", "AH5")),
        },
    }


def trace_validation_against_workbook(workbook_path: Path, inputs: ModelEInputs) -> Dict[str, float]:
    r = XlsmXmlReader(workbook_path)
    columns = {
        "HPE": ["H", "I", "J", "K", "L", "M", "N", "O", "P", "Q", "R", "S"],
        "No HPE": ["AB", "AC", "AD", "AE", "AF", "AG", "AH", "AI", "AJ", "AK", "AL", "AM"],
    }
    result: Dict[str, float] = {}
    for arm, cols in columns.items():
        trace = run_markov_trace(inputs, arm)
        max_error = 0.0
        for i in range(len(trace)):
            row = 11 + i
            workbook_vals = np.array([float(r.cell("E.Markov", f"{col}{row}") or 0.0) for col in cols], dtype=float)
            python_vals = trace.iloc[i][STATE_NAMES].to_numpy(dtype=float)
            max_error = max(max_error, float(np.max(np.abs(python_vals - workbook_vals))))
        result[arm] = max_error
    return result


def run_independent_model_e(workbook_path: Path, output_dir: Path) -> Dict[str, Dict[str, float]]:
    output_dir.mkdir(parents=True, exist_ok=True)
    inputs = load_model_e_inputs(workbook_path)
    reference = workbook_reference_totals(workbook_path)
    summaries: Dict[str, Dict[str, float]] = {}
    rows = []
    for arm in ["HPE", "No HPE"]:
        trace = run_markov_trace(inputs, arm)
        trace.to_csv(output_dir / f"independent_model_E_trace_{arm.replace(' ', '_').lower()}.csv", index=False)
        summary = summarise_trace(inputs, trace)
        summaries[arm] = summary
        for metric, value in summary.items():
            ref = reference[arm][metric]
            rows.append({"arm": arm, "metric": metric, "independent_python": value, "workbook_cached": ref, "absolute_error": value - ref, "relative_error": (value - ref) / ref if ref else math.nan})
    comparison = pd.DataFrame(rows)
    comparison.to_csv(output_dir / "independent_model_E_vs_workbook.csv", index=False)
    payload = {**summaries, "incremental_HPE_minus_No_HPE": {metric: summaries["HPE"][metric] - summaries["No HPE"][metric] for metric in summaries["HPE"]}}
    (output_dir / "independent_model_E_summary.json").write_text(json.dumps(payload, indent=2))
    trace_errors = trace_validation_against_workbook(workbook_path, inputs)
    validation = {
        "max_absolute_trace_error_HPE": trace_errors["HPE"],
        "max_absolute_trace_error_No_HPE": trace_errors["No HPE"],
        "max_absolute_reward_error": float(comparison["absolute_error"].abs().max()),
        "all_trace_errors_below_1e-12": bool(max(trace_errors.values()) < 1e-12),
        "all_reward_errors_below_1e-10": bool(comparison["absolute_error"].abs().max() < 1e-10),
    }
    (output_dir / "independent_model_E_validation_summary.json").write_text(json.dumps(validation, indent=2))
    return payload


def with_hpe_duration(inputs: ModelEInputs, years: float) -> ModelEInputs:
    return replace(inputs, max_hpe_years=float(years))
