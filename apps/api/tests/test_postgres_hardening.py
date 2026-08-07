from decimal import Decimal

from unihub_insight_api.repositories.postgres_hardened import (
    salary_statistics,
)


def test_salary_average_includes_every_visible_person() -> None:
    stats = salary_statistics([Decimal("1500"), Decimal("2500"), Decimal("3500")])

    assert stats.total == Decimal("7500.00")
    assert stats.average == Decimal("2500.00")
    assert stats.median == Decimal("2500.00")
    assert stats.eligible_average_count == 3
