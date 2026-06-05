#!/usr/bin/env python3
"""Validate exported dashboard contract against live Python formula engines."""
from __future__ import annotations

from pathlib import Path
import json
import sys

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from medsid_repro.dashboard_scenario import calculate_scenario_from_contract, calculate_scenario_live


def main() -> None:
    contract = pd.read_csv(ROOT / "dashboard" / "data" / "dashboard_scenario_contract.csv")
    cases = pd.read_csv(ROOT / "dashboard" / "data" / "dashboard_cross_language_cases.csv")
    defaults = (
        contract.sort_values(["duration_years", "model_id"])
        .drop_duplicates("model_id")
        .set_index("model_id")["default_england_hpe_count"]
        .to_dict()
    )
    workbook = ROOT / "sources" / "nsaid_2024_original_workbook_came077880.ww1.xlsm"
    rows = []
    for case in cases.itertuples(index=False):
        selected = str(case.selected_models).split("|")
        counts = {model_id: float(defaults[model_id]) * float(case.scale) for model_id in defaults}
        contract_metrics, _, _ = calculate_scenario_from_contract(
            contract,
            duration_years=float(case.duration_years),
            selected_models=selected,
            model_counts=counts,
            uptake=float(case.uptake),
            effectiveness=float(case.effectiveness),
            implementation_cost_per_approached_hpe_gbp=float(case.implementation_cost_per_approached_hpe_gbp),
        )
        live_metrics, _, _ = calculate_scenario_live(
            workbook,
            duration_years=float(case.duration_years),
            selected_models=selected,
            model_counts=counts,
            uptake=float(case.uptake),
            effectiveness=float(case.effectiveness),
            implementation_cost_per_approached_hpe_gbp=float(case.implementation_cost_per_approached_hpe_gbp),
        )
        for metric in sorted(contract_metrics):
            absolute = abs(float(contract_metrics[metric]) - float(live_metrics[metric]))
            scale = max(1.0, abs(float(contract_metrics[metric])), abs(float(live_metrics[metric])))
            rows.append({
                "scenario_id": case.scenario_id,
                "metric": metric,
                "contract_value": float(contract_metrics[metric]),
                "live_python_value": float(live_metrics[metric]),
                "absolute_error": absolute,
                "scaled_relative_error": absolute / scale,
            })
    detail = pd.DataFrame(rows)
    out = ROOT / "outputs" / "dashboard_crosscheck"
    out.mkdir(parents=True, exist_ok=True)
    detail.to_csv(out / "contract_vs_live_python_detail.csv", index=False)
    summary = {
        "scenario_count": int(cases.shape[0]),
        "max_absolute_error": float(detail["absolute_error"].max()),
        "max_scaled_relative_error": float(detail["scaled_relative_error"].max()),
        "tolerance_scaled_relative_error": 1e-10,
        "passed": bool(detail["scaled_relative_error"].max() < 1e-10),
    }
    (out / "contract_vs_live_python_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    if not summary["passed"]:
        raise SystemExit("Dashboard contract differs from live Python engines beyond tolerance")


if __name__ == "__main__":
    main()
