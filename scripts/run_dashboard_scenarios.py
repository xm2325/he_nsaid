#!/usr/bin/env python3
"""Run standard dashboard scenarios through the Python contract engine."""
from __future__ import annotations

from pathlib import Path
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from medsid_repro.dashboard_scenario import EVENT_SLUGS, calculate_scenario_from_contract


def main() -> None:
    contract = pd.read_csv(ROOT / "dashboard" / "data" / "dashboard_scenario_contract.csv")
    cases = pd.read_csv(ROOT / "dashboard" / "data" / "dashboard_cross_language_cases.csv")
    defaults = (
        contract.sort_values(["duration_years", "model_id"])
        .drop_duplicates("model_id")
        .set_index("model_id")["default_england_hpe_count"]
        .to_dict()
    )
    rows = []
    for case in cases.itertuples(index=False):
        selected_models = str(case.selected_models).split("|")
        counts = {model_id: float(defaults[model_id]) * float(case.scale) for model_id in defaults}
        metrics, _, events = calculate_scenario_from_contract(
            contract,
            duration_years=float(case.duration_years),
            selected_models=selected_models,
            model_counts=counts,
            uptake=float(case.uptake),
            effectiveness=float(case.effectiveness),
            implementation_cost_per_approached_hpe_gbp=float(case.implementation_cost_per_approached_hpe_gbp),
        )
        row = {"scenario_id": case.scenario_id, **metrics}
        event_map = dict(zip(events["event"], events["events_avoided"]))
        for label, slug in EVENT_SLUGS.items():
            row[f"events_avoided_{slug}"] = float(event_map[label])
        rows.append(row)
    out = ROOT / "outputs" / "dashboard_crosscheck"
    out.mkdir(parents=True, exist_ok=True)
    result = pd.DataFrame(rows)
    result.to_csv(out / "python_dashboard_scenarios.csv", index=False)
    print(result.to_csv(index=False))


if __name__ == "__main__":
    main()
