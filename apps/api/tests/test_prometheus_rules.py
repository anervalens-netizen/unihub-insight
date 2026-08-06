from pathlib import Path


def test_prometheus_alerts_match_release_sli_budgets() -> None:
    rules = (Path(__file__).parents[3] / "ops" / "prometheus" / "unihub-insight.rules.yml").read_text()

    assert 'surface="overview"' in rules
    assert ") > 1" in rules
    assert 'surface!="overview"' in rules
    assert ") > 2" in rules
    assert rules.count("histogram_quantile(") >= 4
    assert 'metric="LCP"' in rules
    assert ") > 2500" in rules
    assert 'metric="INP"' in rules
    assert ") > 200" in rules
