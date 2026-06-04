"""Independent Python reconstruction for NSAID Model A.

Model A represents NSAIDs in older people without gastroprotection.  It reuses
the validated gastrointestinal state-transition engine shared with Model B.
"""
from __future__ import annotations
from pathlib import Path
from typing import Dict

from .independent_nsaid_gi import *  # noqa: F401,F403
from .independent_nsaid_gi import (
    GIModelInputs,
    load_gi_model_inputs,
    run_independent_gi_model,
    workbook_reference_totals as _generic_reference_totals,
    trace_validation_against_workbook as _generic_trace_validation,
)

ModelAInputs = GIModelInputs


def load_model_a_inputs(workbook_path: Path) -> GIModelInputs:
    return load_gi_model_inputs(workbook_path, model_id="A")


def workbook_reference_totals(workbook_path: Path):
    return _generic_reference_totals(workbook_path, model_id="A")


def trace_validation_against_workbook(workbook_path: Path, inputs: GIModelInputs):
    return _generic_trace_validation(workbook_path, inputs, model_id="A")


def run_independent_model_a(workbook_path: Path, output_dir: Path) -> Dict[str, Dict[str, float]]:
    return run_independent_gi_model(workbook_path, output_dir, model_id="A")
