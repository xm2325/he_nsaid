from pathlib import Path

import numpy as np

from medsid_repro.independent_nsaid_b import load_model_b_inputs
from medsid_repro.independent_nsaid_gi import run_markov_trace, summarise_trace
from medsid_repro.xlsm_reader import XlsmXmlReader

ROOT = Path(__file__).resolve().parents[1]
WORKBOOK = ROOT / "sources" / "nsaid_2024_original_workbook_came077880.ww1.xlsm"


def _assert_trace_matches_workbook(arm: str, columns: list[str]) -> None:
    inputs = load_model_b_inputs(WORKBOOK)
    trace = run_markov_trace(inputs, arm)
    reader = XlsmXmlReader(WORKBOOK)
    for i in range(len(trace)):
        xlrow = 10 + i
        workbook_vals = np.array([float(reader.cell("B.Markov", f"{c}{xlrow}") or 0.0) for c in columns])
        ours = trace.iloc[i, 3:].to_numpy(dtype=float)
        assert np.allclose(ours, workbook_vals, atol=1e-12, rtol=0.0)


def test_independent_model_b_hpe_trace_matches_workbook():
    _assert_trace_matches_workbook("HPE", list("HIJKLMNOPQ"))


def test_independent_model_b_no_hpe_trace_matches_workbook():
    _assert_trace_matches_workbook("No HPE", ["U", "V", "W", "X", "Y", "Z", "AA", "AB", "AC", "AD"])


def test_independent_model_b_rewards_match_workbook():
    inputs = load_model_b_inputs(WORKBOOK)
    hpe = summarise_trace(inputs, run_markov_trace(inputs, "HPE"))
    noh = summarise_trace(inputs, run_markov_trace(inputs, "No HPE"))
    reader = XlsmXmlReader(WORKBOOK)

    expected = {
        "HPE": {
            "total_ly": float(reader.cell("B.Markov", "R4")),
            "total_qaly": float(reader.cell("B.QALYs", "Q4")),
            "discounted_qaly": float(reader.cell("B.QALYs", "Q5")),
            "total_cost": float(reader.cell("B.Costs", "Q4")),
            "discounted_cost": float(reader.cell("B.Costs", "Q5")),
        },
        "No HPE": {
            "total_ly": float(reader.cell("B.Markov", "AE4")),
            "total_qaly": float(reader.cell("B.QALYs", "AC4")),
            "discounted_qaly": float(reader.cell("B.QALYs", "AC5")),
            "total_cost": float(reader.cell("B.Costs", "AC4")),
            "discounted_cost": float(reader.cell("B.Costs", "AC5")),
        },
    }
    for arm, actual in [("HPE", hpe), ("No HPE", noh)]:
        for metric, expected_value in expected[arm].items():
            assert abs(actual[metric] - expected_value) < 1e-10
