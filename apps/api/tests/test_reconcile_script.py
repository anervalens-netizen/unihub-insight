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


def test_visits_reconcile_the_performance_slice_at_contract_grain() -> None:
    reconcile = load_reconcile_module()
    control = {
        "total_visits": Decimal("15"),
        "distinct_stores": Decimal("11"),
        "avg_completion": Decimal("46.67"),
        "checklist_score": Decimal("92.00"),
    }
    performance = SimpleNamespace(
        visits=SimpleNamespace(
            kpis=[
                SimpleNamespace(id="visits.total", value=Decimal("15")),
                SimpleNamespace(id="visits.distinct_stores", value=Decimal("11")),
                SimpleNamespace(id="visits.avg_completion", value=Decimal("46.67")),
                SimpleNamespace(id="visits.checklist_score", value=Decimal("92.00")),
            ]
        )
    )

    assert reconcile.visit_metric_differences(control, performance) == {
        "visits.presence": Decimal(0),
        "visits.total": Decimal(0),
        "visits.distinct_stores": Decimal(0),
        "visits.avg_completion": Decimal(0),
        "visits.checklist_score": Decimal(0),
    }


def test_visits_fail_reconciliation_when_expected_slice_is_missing() -> None:
    reconcile = load_reconcile_module()

    assert reconcile.visit_metric_differences(
        {
            "total_visits": Decimal("1"),
            "distinct_stores": Decimal("1"),
            "avg_completion": Decimal("50"),
            "checklist_score": Decimal("100"),
        },
        SimpleNamespace(visits=None),
    ) == {"visits.presence": Decimal("-1")}


def test_authoritative_acceptance_refuses_partial_or_unavailable_sources() -> None:
    reconcile = load_reconcile_module()
    result = reconcile.ReconciliationResult(
        sample_case="network",
        scope="Toată rețeaua",
        sales_difference=Decimal(0),
        target_difference=Decimal(0),
        module_difference=Decimal(0),
        cutoff_matches=True,
        domain_differences={"visits.total": Decimal(0)},
        unavailable_domains=("finance",),
        incomplete_domains={"campaigns": "partial", "finance": "unavailable"},
    )

    assert result.numeric_passed is True
    assert result.authoritative_passed is False
    assert result.passed is False


def test_authoritative_acceptance_requires_numeric_reconciliation_too() -> None:
    reconcile = load_reconcile_module()
    result = reconcile.ReconciliationResult(
        sample_case="asm:1",
        scope="ASM Test",
        sales_difference=Decimal("0.02"),
        target_difference=Decimal(0),
        module_difference=Decimal(0),
        cutoff_matches=True,
        domain_differences={},
        unavailable_domains=(),
        incomplete_domains={},
    )

    assert result.numeric_passed is False
    assert result.authoritative_passed is False


def test_authoritative_acceptance_requires_all_matrix_cases() -> None:
    reconcile = load_reconcile_module()
    result = reconcile.ReconciliationResult(
        sample_case="network",
        scope="Toată rețeaua",
        sales_difference=Decimal(0),
        target_difference=Decimal(0),
        module_difference=Decimal(0),
        cutoff_matches=True,
        domain_differences={},
        unavailable_domains=(),
        incomplete_domains={},
        matrix_missing_cases=("historically-transferred-store",),
    )

    assert result.numeric_passed is True
    assert result.authoritative_passed is False
    assert result.passed is False
