"""Independent deterministic reconstruction of NSAID Model D (heart failure)."""
from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path
from typing import Dict, Tuple
import json
import math

import numpy as np
import pandas as pd

from .xlsm_reader import XlsmXmlReader

STATE_NAMES = [
    "HF no HPE",
    "PCE no HPE",
    "SCE no HPE",
    "HF w HPE",
    "PCE w HPE",
    "SCE w HPE",
    "HF post event no HPE",
    "HF post event w HPE",
    "Dead",
]
STATE_INDEX = {name: i for i, name in enumerate(STATE_NAMES)}


@dataclass(frozen=True)
class ModelDInputs:
    discount_qaly: float
    discount_cost: float
    time_horizon_years: float
    half_cycle: bool
    cycle_length: float
    cycles_per_year: int
    max_hpe_years: float
    cohort_age: float
    transition_params: Dict[Tuple[float, int, int], float]
    costs_by_state: np.ndarray
    utility_by_state: np.ndarray


def _age_group(age: float) -> float:
    """Match the workbook's D.TPM age-category selection."""
    capped = min(float(age), 95.0)
    if capped >= 85.0:
        return 85.0
    if capped >= 75.0:
        return 75.0
    return 65.0


def load_model_d_inputs(workbook_path: Path) -> ModelDInputs:
    r = XlsmXmlReader(workbook_path)
    transition_params: Dict[Tuple[float, int, int], float] = {}
    for row in range(523, 607):
        age = r.cell("Parameters", f"D{row}")
        from_state = r.cell("Parameters", f"E{row}")
        to_state = r.cell("Parameters", f"F{row}")
        value = r.cell("Parameters", f"M{row}")
        if age is None or from_state is None or to_state is None or value is None:
            continue
        transition_params[(float(age), int(float(from_state)), int(float(to_state)))] = float(value)
    cycles_per_year = int(float(r.cell("Parameters", "M457")))
    return ModelDInputs(
        discount_qaly=float(r.cell("Parameters", "M7")),
        discount_cost=float(r.cell("Parameters", "M8")),
        time_horizon_years=float(r.cell("Parameters", "M9")),
        half_cycle=bool(int(float(r.cell("Parameters", "M10")))),
        cycle_length=1.0 / cycles_per_year,
        cycles_per_year=cycles_per_year,
        max_hpe_years=float(r.cell("Parameters", "M458")),
        cohort_age=float(r.cell("Parameters", "M455")),
        transition_params=transition_params,
        costs_by_state=np.array([float(r.cell("Parameters", f"M{row}")) for row in range(692, 701)], dtype=float),
        utility_by_state=np.array([float(r.cell("Parameters", f"M{row}")) for row in range(727, 736)], dtype=float),
    )


def _param(inputs: ModelDInputs, age: float, from_state: int, to_state: int) -> float:
    return float(inputs.transition_params.get((_age_group(age), from_state, to_state), 0.0))


def transition_matrix(inputs: ModelDInputs, age: float, crossing_hpe_duration: bool = False) -> np.ndarray:
    """Build a 9-state heart-failure transition matrix for one cycle."""
    m = np.zeros((9, 9), dtype=float)

    # Base matrix from active workbook transition parameters. State identifiers
    # are one-indexed in the Parameters sheet.
    specified_targets = {
        0: [1, 2, 8],
        1: [1, 2, 6, 8],
        2: [1, 2, 6, 8],
        3: [1, 2, 4, 5, 6, 7, 8],
        4: [4, 5, 7, 8],
        5: [4, 5, 7, 8],
        6: [1, 2, 6, 8],
        7: [1, 2, 6, 7, 8],
    }
    residual_target = {0: 0, 1: 6, 2: 6, 3: 3, 4: 7, 5: 7, 6: 6, 7: 7}

    for from_idx, targets in specified_targets.items():
        # Workbook rows for post-event states reuse the HF no-HPE or HF-with-HPE
        # transition parameters rather than storing a separate parameter block.
        parameter_from_state = 1 if from_idx == 6 else 4 if from_idx == 7 else from_idx + 1
        for to_idx in targets:
            m[from_idx, to_idx] = _param(inputs, age, parameter_from_state, to_idx + 1)
        m[from_idx, residual_target[from_idx]] += 1.0 - float(m[from_idx].sum())
    m[8, 8] = 1.0

    if not crossing_hpe_duration:
        return m

    # Workbook correction matrix for the one boundary-crossing cycle.
    corrected = m.copy()
    # HF with HPE: event transitions route to no-HPE states; residual goes to HF no HPE.
    corrected[3] = 0.0
    corrected[3, 1] = _param(inputs, age, 4, 2)
    corrected[3, 2] = _param(inputs, age, 4, 3)
    corrected[3, 6] = _param(inputs, age, 4, 7)
    corrected[3, 7] = _param(inputs, age, 4, 8)
    corrected[3, 8] = _param(inputs, age, 4, 9)
    corrected[3, 0] = 1.0 - float(corrected[3].sum())
    # Post-exacerbation HPE states move to the post-event no-HPE state.
    for from_idx in [4, 5, 7]:
        corrected[from_idx] = 0.0
        corrected[from_idx, 6] = 1.0 - _param(inputs, age, from_idx + 1, 9)
        corrected[from_idx, 8] = _param(inputs, age, from_idx + 1, 9)
    return corrected


def run_markov_trace(inputs: ModelDInputs, arm: str) -> pd.DataFrame:
    n_cycles = int(inputs.time_horizon_years * inputs.cycles_per_year)
    trace = np.zeros((n_cycles + 1, len(STATE_NAMES)), dtype=float)
    if arm == "HPE":
        trace[0, STATE_INDEX["HF w HPE"]] = 1.0
    elif arm == "No HPE":
        trace[0, STATE_INDEX["HF no HPE"]] = 1.0
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


def summarise_trace(inputs: ModelDInputs, trace: pd.DataFrame) -> Dict[str, float]:
    states = trace[STATE_NAMES].to_numpy(dtype=float)
    alive = np.ones(len(STATE_NAMES), dtype=float)
    alive[STATE_INDEX["Dead"]] = 0.0
    totals = {"total_ly": 0.0, "total_qaly": 0.0, "discounted_qaly": 0.0, "total_cost": 0.0, "discounted_cost": 0.0}

    for c in range(len(trace) - 1):
        start, end = states[c], states[c + 1]
        occupancy = 0.5 * (start + end) if inputs.half_cycle else start
        ly = start @ alive * inputs.cycle_length
        qaly = occupancy @ inputs.utility_by_state * inputs.cycle_length
        cost = occupancy @ inputs.costs_by_state
        # D.QALYs and D.Costs both use mid-cycle discounting and DQALYs.
        discount_time = c * inputs.cycle_length + inputs.cycle_length / 2.0
        totals["total_ly"] += float(ly)
        totals["total_qaly"] += float(qaly)
        totals["discounted_qaly"] += float(qaly / ((1.0 + inputs.discount_qaly) ** discount_time))
        totals["total_cost"] += float(cost)
        totals["discounted_cost"] += float(cost / ((1.0 + inputs.discount_qaly) ** discount_time))
    return totals


def workbook_reference_totals(workbook_path: Path) -> Dict[str, Dict[str, float]]:
    r = XlsmXmlReader(workbook_path)
    return {
        "HPE": {
            "discounted_cost": float(r.cell("D.Costs", "P6")),
            "total_cost": float(r.cell("D.Costs", "P5")),
            "discounted_qaly": float(r.cell("D.QALYs", "P6")),
            "total_qaly": float(r.cell("D.QALYs", "P5")),
            "total_ly": float(r.cell("D.Markov", "S4")),
        },
        "No HPE": {
            "discounted_cost": float(r.cell("D.Costs", "AA6")),
            "total_cost": float(r.cell("D.Costs", "AA5")),
            "discounted_qaly": float(r.cell("D.QALYs", "AA6")),
            "total_qaly": float(r.cell("D.QALYs", "AA5")),
            "total_ly": float(r.cell("D.Markov", "AI4")),
        },
    }


def trace_validation_against_workbook(workbook_path: Path, inputs: ModelDInputs) -> Dict[str, float]:
    r = XlsmXmlReader(workbook_path)
    columns = {
        "HPE": ["I", "J", "K", "L", "M", "N", "O", "P", "Q"],
        "No HPE": ["Y", "Z", "AA", "AB", "AC", "AD", "AE", "AF", "AG"],
    }
    result: Dict[str, float] = {}
    for arm, cols in columns.items():
        trace = run_markov_trace(inputs, arm)
        max_error = 0.0
        for i in range(len(trace)):
            row = 10 + i
            workbook_vals = np.array([float(r.cell("D.Markov", f"{col}{row}") or 0.0) for col in cols], dtype=float)
            python_vals = trace.iloc[i][STATE_NAMES].to_numpy(dtype=float)
            max_error = max(max_error, float(np.max(np.abs(python_vals - workbook_vals))))
        result[arm] = max_error
    return result


def run_independent_model_d(workbook_path: Path, output_dir: Path) -> Dict[str, Dict[str, float]]:
    output_dir.mkdir(parents=True, exist_ok=True)
    inputs = load_model_d_inputs(workbook_path)
    reference = workbook_reference_totals(workbook_path)
    summaries: Dict[str, Dict[str, float]] = {}
    rows = []
    for arm in ["HPE", "No HPE"]:
        trace = run_markov_trace(inputs, arm)
        trace.to_csv(output_dir / f"independent_model_D_trace_{arm.replace(' ', '_').lower()}.csv", index=False)
        summary = summarise_trace(inputs, trace)
        summaries[arm] = summary
        for metric, value in summary.items():
            ref = reference[arm][metric]
            rows.append({"arm": arm, "metric": metric, "independent_python": value, "workbook_cached": ref, "absolute_error": value - ref, "relative_error": (value - ref) / ref if ref else math.nan})
    comparison = pd.DataFrame(rows)
    comparison.to_csv(output_dir / "independent_model_D_vs_workbook.csv", index=False)
    payload = {**summaries, "incremental_HPE_minus_No_HPE": {metric: summaries["HPE"][metric] - summaries["No HPE"][metric] for metric in summaries["HPE"]}}
    (output_dir / "independent_model_D_summary.json").write_text(json.dumps(payload, indent=2))
    trace_errors = trace_validation_against_workbook(workbook_path, inputs)
    validation = {
        "max_absolute_trace_error_HPE": trace_errors["HPE"],
        "max_absolute_trace_error_No_HPE": trace_errors["No HPE"],
        "max_absolute_reward_error": float(comparison["absolute_error"].abs().max()),
        "all_trace_errors_below_1e-12": bool(max(trace_errors.values()) < 1e-12),
        "all_reward_errors_below_1e-10": bool(comparison["absolute_error"].abs().max() < 1e-10),
    }
    (output_dir / "independent_model_D_validation_summary.json").write_text(json.dumps(validation, indent=2))
    return payload


def with_hpe_duration(inputs: ModelDInputs, years: float) -> ModelDInputs:
    return replace(inputs, max_hpe_years=float(years))
