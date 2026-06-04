from pathlib import Path

import numpy as np

from medsid_repro.independent_nsaid_c import load_model_c_inputs, run_markov_trace, summarise_trace
from medsid_repro.xlsm_reader import XlsmXmlReader

ROOT = Path(__file__).resolve().parents[1]
WORKBOOK = ROOT / "sources" / "nsaid_2024_original_workbook_came077880.ww1.xlsm"


def _assert_trace_matches_workbook(arm: str, columns: list[str]) -> None:
    inputs = load_model_c_inputs(WORKBOOK)
    trace = run_markov_trace(inputs, arm)
    reader = XlsmXmlReader(WORKBOOK)
    for i in range(len(trace)):
        row = 10 + i
        workbook_vals = np.array([float(reader.cell("C.Markov", f"{col}{row}") or 0.0) for col in columns])
        python_vals = trace.iloc[i, 3:].to_numpy(dtype=float)
        assert np.allclose(python_vals, workbook_vals, atol=1e-12, rtol=0.0)


def test_independent_model_c_hpe_trace_matches_workbook():
    _assert_trace_matches_workbook("HPE", ["H", "I", "J", "K", "L", "M", "N", "O", "P", "Q", "R", "S", "T"])


def test_independent_model_c_no_hpe_trace_matches_workbook():
    _assert_trace_matches_workbook("No HPE", ["Y", "Z", "AA", "AB", "AC", "AD", "AE", "AF", "AG", "AH", "AI", "AJ", "AK"])


def test_independent_model_c_rewards_match_workbook():
    inputs = load_model_c_inputs(WORKBOOK)
    reader = XlsmXmlReader(WORKBOOK)
    expected = {
        "HPE": {
            "total_ly": float(reader.cell("C.Markov", "U4")),
            "total_qaly": float(reader.cell("C.QALYs", "T4")),
            "discounted_qaly": float(reader.cell("C.QALYs", "T5")),
            "total_cost": float(reader.cell("C.Costs", "T4")),
            "discounted_cost": float(reader.cell("C.Costs", "T5")),
        },
        "No HPE": {
            "total_ly": float(reader.cell("C.Markov", "AL4")),
            "total_qaly": float(reader.cell("C.QALYs", "AI4")),
            "discounted_qaly": float(reader.cell("C.QALYs", "AI5")),
            "total_cost": float(reader.cell("C.Costs", "AI4")),
            "discounted_cost": float(reader.cell("C.Costs", "AI5")),
        },
    }
    for arm in ["HPE", "No HPE"]:
        actual = summarise_trace(inputs, run_markov_trace(inputs, arm))
        for metric, expected_value in expected[arm].items():
            assert abs(actual[metric] - expected_value) < 1e-10
