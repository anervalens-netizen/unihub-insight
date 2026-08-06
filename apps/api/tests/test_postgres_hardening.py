from decimal import Decimal

from unihub_insight_api.repositories.postgres_hardened import (
    salary_statistics,
)
from unihub_insight_api.repositories.postgres_modules import (
    MIN_COMPENSATION_POPULATION,
    compensation_is_suppressed,
    filter_visible_compensation_rows,
)


def test_salary_average_uses_retail_minimum_only_for_average() -> None:
    stats = salary_statistics([Decimal("1500"), Decimal("2500"), Decimal("3500")])

    assert stats.total == Decimal("7500.00")
    assert stats.average == Decimal("3000.00")
    assert stats.median == Decimal("2500.00")
    assert stats.eligible_average_count == 2


def test_compensation_suppression_boundary() -> None:
    assert compensation_is_suppressed(0) is False
    assert compensation_is_suppressed(MIN_COMPENSATION_POPULATION - 1) is True
    assert compensation_is_suppressed(MIN_COMPENSATION_POPULATION) is False


def test_compensation_rows_apply_fail_closed_population_threshold() -> None:
    rows = [
        {"company_name": "suppressed", "eligible_person_count": 2},
        {"company_name": "visible", "eligible_person_count": 3},
    ]

    visible = filter_visible_compensation_rows(rows)

    assert [row["company_name"] for row in visible] == ["visible"]
