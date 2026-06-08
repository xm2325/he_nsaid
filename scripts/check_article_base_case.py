#!/usr/bin/env python3
"""Run the dashboard article base case through live and contract engines.

This check separates three quantities:
1. the independent live deterministic reconstruction;
2. the same deterministic point read from the versioned dashboard contract;
3. the published Table 3 probabilistic sensitivity analysis (PSA) mean.

The first two should match to floating-point precision. The deterministic point
is not expected to equal the published PSA mean because the article mean is the
average of probabilistic simulations.
"""
from __future__ import annotations

import json
from pathlib import Path
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from medsid_repro.dashboard_scenario import (  # noqa: E402
    ARTICLE_BASE_CASE_DEFAULTS,
    MODEL_IDS,
    attach_published_table3_comparison,
    calculate_article_base_case_from_contract,
    calculate_article_base_case_live,
)
from medsid_repro.independent_nsaid_psa import (  # noqa: E402
    aggregate_england_psa,
    extract_england_query_level_psa,
)


def _relative_difference(value: float, reference: float) -> float:
    return float((value - reference) / abs(reference)) if reference != 0 else float("nan")


def main() -> None:
    workbook = ROOT / "sources" / "nsaid_2024_original_workbook_came077880.ww1.xlsm"
    contract_path = ROOT / "dashboard" / "data" / "dashboard_scenario_contract.csv"
    published_table3 = ROOT / "data" / "nsaid_2024_published_table3.csv"
    out = ROOT / "outputs" / "article_base_case_dashboard"
    out.mkdir(parents=True, exist_ok=True)

    contract = pd.read_csv(contract_path)
    live_metrics, live_rows, live_events = calculate_article_base_case_live(
        workbook,
        duration_years=ARTICLE_BASE_CASE_DEFAULTS["hpe_exposure_duration_years"],
        selected_models=MODEL_IDS,
    )
    contract_metrics, _, _ = calculate_article_base_case_from_contract(
        contract,
        duration_years=ARTICLE_BASE_CASE_DEFAULTS["hpe_exposure_duration_years"],
        selected_models=MODEL_IDS,
    )
    comparison = attach_published_table3_comparison(live_rows, published_table3)

    numeric_keys = sorted(set(live_metrics) & set(contract_metrics))
    engine_comparison = pd.DataFrame(
        [
            {
                "metric": key,
                "live_python": float(live_metrics[key]),
                "validated_contract": float(contract_metrics[key]),
                "absolute_error": abs(float(live_metrics[key]) - float(contract_metrics[key])),
            }
            for key in numeric_keys
        ]
    )
    max_abs_engine_error = float(engine_comparison["absolute_error"].max())
    if max_abs_engine_error > 1e-8:
        raise SystemExit(f"Live and contract article base cases differ: max absolute error={max_abs_engine_error}")

    deterministic_cost = float(live_metrics["article_cost_impact_gbp"])
    deterministic_qaly = float(live_metrics["article_qaly_impact"])
    published_cost = float(comparison["published_table3_psa_mean_cost_impact_gbp"].sum())
    published_qaly = float(comparison["published_table3_psa_mean_qaly_impact"].sum())

    cached_psa = aggregate_england_psa(extract_england_query_level_psa(workbook))
    cached_psa_mean_cost = float(cached_psa["incremental_cost_gbp"].mean())
    cached_psa_mean_qaly = float(cached_psa["incremental_qaly"].mean())

    summary = {
        "article_base_case_defaults": ARTICLE_BASE_CASE_DEFAULTS,
        "selected_models": MODEL_IDS,
        "live_deterministic": {
            "total_hpe_count": float(live_metrics["total_hpe_count"]),
            "total_cost_impact_gbp": deterministic_cost,
            "total_qaly_impact": deterministic_qaly,
        },
        "published_table3_psa_mean": {
            "reported_samples": int(ARTICLE_BASE_CASE_DEFAULTS["published_psa_samples"]),
            "total_cost_impact_gbp": published_cost,
            "total_qaly_impact": published_qaly,
        },
        "difference_live_deterministic_minus_published_psa_mean": {
            "total_cost_impact_gbp": deterministic_cost - published_cost,
            "total_cost_impact_relative_to_published": _relative_difference(deterministic_cost, published_cost),
            "total_qaly_impact": deterministic_qaly - published_qaly,
            "total_qaly_impact_relative_to_published_magnitude": _relative_difference(deterministic_qaly, published_qaly),
        },
        "public_workbook_cached_psa_reaggregation": {
            "stored_iterations": int(cached_psa.shape[0]),
            "mean_total_cost_impact_gbp": cached_psa_mean_cost,
            "mean_total_qaly_impact": cached_psa_mean_qaly,
            "note": "The public workbook stores 1,000 PSA iterations. The article reports PSA means from 10,000 samples.",
        },
        "live_vs_validated_contract": {
            "max_absolute_error": max_abs_engine_error,
            "status": "PASS",
        },
        "scientific_interpretation": (
            "The live Python state-transition engines reproduce the deterministic workbook logic at the article base-case inputs. "
            "Their deterministic total is not expected to equal the published Table 3 PSA mean. "
            "The repository does not yet contain an independent parameter-level 10,000-sample PSA sampler."
        ),
    }

    comparison.to_csv(out / "article_base_case_model_comparison.csv", index=False)
    live_events.to_csv(out / "article_base_case_expected_excess_events.csv", index=False)
    engine_comparison.to_csv(out / "article_base_case_live_vs_contract.csv", index=False)
    (out / "article_base_case_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

    print("PASS: article base-case live Python result matches the validated contract output.")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
