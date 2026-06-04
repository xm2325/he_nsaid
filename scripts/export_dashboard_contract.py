#!/usr/bin/env python3
"""Export versioned dynamic-dashboard contracts from live Python formula engines."""
from __future__ import annotations

from pathlib import Path
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from medsid_repro.dashboard_scenario import ARTICLE_BASE_CASE_DEFAULTS, build_dashboard_contract


def main() -> None:
    workbook = ROOT / "sources" / "nsaid_2024_original_workbook_came077880.ww1.xlsm"
    contract = build_dashboard_contract(workbook)
    destinations = [
        ROOT / "dashboard" / "data" / "dashboard_scenario_contract.csv",
        ROOT / "r" / "app" / "data" / "dashboard_scenario_contract.csv",
    ]
    for destination in destinations:
        destination.parent.mkdir(parents=True, exist_ok=True)
        contract.to_csv(destination, index=False)
    manifest = {
        "contract_version": "v13",
        "rows": int(contract.shape[0]),
        "models": sorted(contract["model_id"].unique().tolist()),
        "duration_grid": sorted(contract["duration_years"].unique().tolist()),
        "scope": "Python formula-engine outputs for dynamic Python and R dashboard scenario calculations.",
        "streamlit_default_analysis_view": "Article base-case reproduction",
        "streamlit_default_calculation_mode": "Live Python state-transition models",
        "article_base_case_defaults": ARTICLE_BASE_CASE_DEFAULTS,
        "intervention_layer": "Optional transparent proportional avoided-burden scenario calculation: uptake multiplied by effectiveness.",
    }
    for destination in [
        ROOT / "dashboard" / "data" / "dashboard_contract_manifest.json",
        ROOT / "r" / "app" / "data" / "dashboard_contract_manifest.json",
    ]:
        destination.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
