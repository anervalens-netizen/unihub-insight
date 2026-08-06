from unihub_insight_api.api.dependencies import parse_selection, parse_stores
from unihub_insight_api.domain import AnalyticsScope, ComparisonMode
from unihub_insight_api.services import period_last_day, previous_period, scope_label


def test_store_scope_is_ordered_and_deduplicated() -> None:
    assert parse_stores("S001, S002,S001,,") == ("S001", "S002")


def test_multi_scope_is_ordered_and_deduplicated() -> None:
    assert parse_selection("RM Sud, RM Nord,RM Sud,,") == ("RM Sud", "RM Nord")


def test_previous_period_boundaries() -> None:
    assert previous_period("2026-01", ComparisonMode.PREVIOUS_MONTH) == "2025-12"
    assert previous_period("2026-08", ComparisonMode.PREVIOUS_YEAR) == "2025-08"
    assert previous_period("2026-08", ComparisonMode.NONE) is None


def test_period_last_day_handles_leap_year() -> None:
    assert period_last_day("2024-02").isoformat() == "2024-02-29"
    assert period_last_day("2026-02").isoformat() == "2026-02-28"


def test_store_scope_dominates_parent_labels() -> None:
    scope = AnalyticsScope(
        period="2026-08",
        firm="MOBIUP",
        regional="Sud",
        stores=("S001", "S002"),
    )
    assert scope_label(scope) == "2 magazine"


def test_agent_remains_visible_inside_store_scope() -> None:
    scope = AnalyticsScope(period="2026-08", stores=("S001",), agent="Agent 01")
    assert scope_label(scope) == "Magazin S001 · Agent 01"


def test_multiple_regionals_and_agents_have_readable_scope_label() -> None:
    scope = AnalyticsScope(
        period="2026-08",
        regional=("RM Sud", "RM Nord"),
        agent=("Agent 01", "Agent 02"),
    )
    assert scope_label(scope) == "2 RM · 2 agenți"
