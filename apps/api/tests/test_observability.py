from pathlib import Path

from unihub_insight_api.observability import MetricsRegistry, http_surface, release_source_sha, traffic_class


def test_release_source_sha_is_read_from_immutable_release_root(tmp_path: Path) -> None:
    release = tmp_path / ("b" * 40)
    source = release / "apps/api/src/unihub_insight_api/observability.py"
    source.parent.mkdir(parents=True)
    (release / "SOURCE_SHA").write_text("b" * 40, encoding="utf-8")

    assert release_source_sha(source) == "b" * 40


def test_http_surface_is_finite_and_module_aware() -> None:
    assert http_surface("/api/v1/overview") == "overview"
    assert http_surface("/api/v1/modules/{module}", {"module": "sales"}) == "module-sales"
    assert http_surface("/api/v1/modules/{module}", {"module": "invented"}) == "module-unknown"
    assert http_surface("/api/v1/dashboards/{dashboard_id}") == "custom-dashboards"
    assert http_surface("unmatched") == "other"


def test_traffic_class_separates_real_synthetic_and_system() -> None:
    assert traffic_class(subject="andrei") == "real"
    assert traffic_class(subject="insight-load-gate") == "synthetic"
    assert traffic_class(subject="insight-e2e-browser") == "synthetic"
    assert traffic_class(subject=None) == "unauthenticated"
    assert traffic_class(subject="andrei", system=True) == "system"


def test_metrics_bind_http_and_rum_to_exact_build_and_surface() -> None:
    registry = MetricsRegistry()
    source_sha = "a" * 40
    registry.register_build(source_sha)
    registry.record_http(
        source_sha=source_sha,
        traffic_class="real",
        surface="module-sales",
        route="/api/v1/modules/{module}",
        method="GET",
        status_code=200,
        duration_seconds=0.125,
    )
    registry.record_web_vital(
        source_sha=source_sha,
        traffic_class="real",
        surface="module-sales",
        metric="LCP",
        rating="good",
        navigation_type="navigate",
        value_ms=900,
    )

    rendered = registry.render()
    assert f'unihub_insight_build_info{{source_sha="{source_sha}"}} 1' in rendered
    assert 'traffic_class="real",surface="module-sales"' in rendered
    assert 'metric="LCP",rating="good",navigation_type="navigate"' in rendered
