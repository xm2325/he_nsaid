#!/usr/bin/env python3
"""Fail when Python and R dashboard scenario outputs differ beyond tolerance."""
from __future__ import annotations

from pathlib import Path
import json

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
PYTHON_OUT = ROOT / "outputs" / "dashboard_crosscheck" / "python_dashboard_scenarios.csv"
R_OUT = ROOT / "outputs_r" / "dashboard_crosscheck" / "r_dashboard_scenarios.csv"
SUMMARY = ROOT / "outputs" / "dashboard_crosscheck" / "python_r_dashboard_crosscheck_summary.json"
DETAIL = ROOT / "outputs" / "dashboard_crosscheck" / "python_r_dashboard_crosscheck_detail.csv"


def main() -> None:
    py = pd.read_csv(PYTHON_OUT)
    rr = pd.read_csv(R_OUT)
    joined = py.merge(rr, on="scenario_id", suffixes=("_python", "_r"), validate="one_to_one")
    numeric_columns = [column for column in py.columns if column != "scenario_id"]
    rows = []
    for column in numeric_columns:
        py_col = f"{column}_python"
        r_col = f"{column}_r"
        absolute = (joined[py_col] - joined[r_col]).abs()
        scale = np.maximum(1.0, np.maximum(joined[py_col].abs(), joined[r_col].abs()))
        relative = absolute / scale
        for scenario_id, abs_error, rel_error in zip(joined["scenario_id"], absolute, relative):
            rows.append({"scenario_id": scenario_id, "metric": column, "absolute_error": float(abs_error), "scaled_relative_error": float(rel_error)})
    detail = pd.DataFrame(rows)
    DETAIL.parent.mkdir(parents=True, exist_ok=True)
    detail.to_csv(DETAIL, index=False)
    summary = {
        "scenario_count": int(joined.shape[0]),
        "metric_count": int(len(numeric_columns)),
        "max_absolute_error": float(detail["absolute_error"].max()),
        "max_scaled_relative_error": float(detail["scaled_relative_error"].max()),
        "tolerance_scaled_relative_error": 1e-10,
        "passed": bool(detail["scaled_relative_error"].max() < 1e-10),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    if not summary["passed"]:
        raise SystemExit("Python and R dashboard results differ beyond tolerance")


if __name__ == "__main__":
    main()
