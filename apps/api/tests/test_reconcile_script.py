from __future__ import annotations

import importlib.util
import sys
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace


def load_reconcile_module():
    path = Path(__file__).parents[3] / "ops" / "scripts" / "reconcile.py"
    spec = importlib.util.spec_from_file_location("unihub_insight_reconcile", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_optional_metric_distinguishes_missing_period_from_zero() -> None:
    reconcile = load_reconcile_module()
    metrics = [SimpleNamespace(id="planning.forecast", value=Decimal("0.00"))]

    assert reconcile.optional_metric_value(metrics, "planning.forecast") == Decimal("0.00")
    assert reconcile.optional_metric_value(metrics, "planning.target_gap") is None
