#!/usr/bin/env python3
"""Check repository files required by the default Streamlit deployment."""
from __future__ import annotations

from pathlib import Path
import importlib
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

required_paths = [
    ROOT / "requirements.txt",
    ROOT / "dashboard" / "streamlit_app.py",
    ROOT / "dashboard" / "data" / "dashboard_scenario_contract.csv",
    ROOT / "dashboard" / "data" / "dashboard_contract_manifest.json",
    ROOT / "dashboard" / "data" / "figure2_cached_psa_cloud.csv",
    ROOT / "dashboard" / "data" / "figure2_cached_psa_ellipse.csv",
    ROOT / "dashboard" / "data" / "figure2_cached_psa_summary.json",
    ROOT / "medsid_repro" / "__init__.py",
    ROOT / "medsid_repro" / "dashboard_scenario.py",
    ROOT / "medsid_repro" / "dashboard_figure2.py",
    ROOT / "sources" / "nsaid_2024_original_workbook_came077880.ww1.xlsm",
    ROOT / "data" / "nsaid_2024_published_table3.csv",
]

missing = [str(path.relative_to(ROOT)) for path in required_paths if not path.exists()]
if missing:
    raise SystemExit("Missing required Streamlit deployment files: " + ", ".join(missing))

module = importlib.import_module("medsid_repro.dashboard_scenario")
figure2_module = importlib.import_module("medsid_repro.dashboard_figure2")
for name in [
    "calculate_article_base_case_live",
    "calculate_article_base_case_from_contract",
    "attach_published_table3_comparison",
]:
    if not hasattr(module, name):
        raise SystemExit(f"Missing required dashboard function: medsid_repro.dashboard_scenario.{name}")

for name in ["load_dashboard_figure2_reference", "make_figure2_dashboard_plot"]:
    if not hasattr(figure2_module, name):
        raise SystemExit(f"Missing required Figure 2 dashboard function: medsid_repro.dashboard_figure2.{name}")

source = (ROOT / "dashboard" / "streamlit_app.py").read_text(encoding="utf-8")
live_label = 'options=["Live Python state-transition models", "Fast validated contract"]'
article_label = 'options=["Article base-case reproduction", "Illustrative intervention scenario"]'
if live_label not in source:
    raise SystemExit("Streamlit calculation-mode order does not select live Python first")
if article_label not in source:
    raise SystemExit("Streamlit analysis-view order does not select the article base case first")
if "Figure 2 PSA cloud" not in source:
    raise SystemExit("Streamlit article view is missing the Figure 2 PSA cloud tab")
if source.count("with figure2_tab:") != 1:
    raise SystemExit("Streamlit app must define exactly one Figure 2 tab block inside the article view")

print("PASS: Streamlit deployment has all files required by the live Python article-default and Figure 2 views.")
