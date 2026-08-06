from __future__ import annotations

import json
import logging
import re
import threading
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Final

HTTP_BUCKETS: Final[tuple[float, ...]] = (0.1, 0.25, 0.5, 1.0, 2.0, 5.0, 10.0)
WEB_VITAL_BUCKETS_MS: Final[tuple[float, ...]] = (
    100.0,
    200.0,
    500.0,
    1000.0,
    2500.0,
    4000.0,
    8000.0,
    16000.0,
)
SOURCE_SHA_PATTERN: Final[re.Pattern[str]] = re.compile(r"^[0-9a-f]{40}$")
SYNTHETIC_SUBJECTS: Final[frozenset[str]] = frozenset(
    {
        "insight-auth-negative",
        "insight-live-verification",
        "insight-load-gate",
        "insight-smoke",
    }
)
MODULE_IDS: Final[frozenset[str]] = frozenset(
    {"sales", "performance", "campaigns", "workforce", "compensation", "finance", "planning"}
)
SYSTEM_ROUTES: Final[frozenset[str]] = frozenset({"/livez", "/readyz", "/ready-metrics", "/metrics"})


def release_source_sha(start: Path | None = None) -> str:
    """Resolve the immutable release identity without a mutable runtime env value."""
    source = (start or Path(__file__)).resolve()
    for parent in source.parents:
        candidate = parent / "SOURCE_SHA"
        if not candidate.is_file():
            continue
        value = candidate.read_text(encoding="utf-8").strip()
        if SOURCE_SHA_PATTERN.fullmatch(value):
            return value
    return "development"


def traffic_class(*, subject: str | None, system: bool = False, demo: bool = False) -> str:
    if system:
        return "system"
    if demo:
        return "demo"
    if not subject:
        return "unauthenticated"
    if subject in SYNTHETIC_SUBJECTS or subject.startswith("insight-e2e-"):
        return "synthetic"
    return "real"


def http_surface(route: str, path_params: dict[str, object] | None = None) -> str:
    params = path_params or {}
    if route in SYSTEM_ROUTES:
        return "system"
    if route == "/api/v1/overview":
        return "overview"
    if route == "/api/v1/monthly-review":
        return "monthly-review"
    if route == "/api/v1/modules/{module}":
        module = str(params.get("module", ""))
        return f"module-{module}" if module in MODULE_IDS else "module-unknown"
    if route.startswith("/api/v1/dashboards"):
        return "custom-dashboards"
    if route == "/api/v1/query/batch":
        return "query-batch"
    if route.startswith("/api/v1/query/"):
        return "query-tools"
    if route.startswith("/api/v1/exports/"):
        return "exports"
    if route.startswith("/api/v1/telemetry/"):
        return "telemetry"
    if route == "/api/v1/me":
        return "identity"
    if route.startswith("/api/v1/catalog") or route == "/api/v1/filters/options":
        return "catalog"
    return "other"


def _escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace("\n", "\\n").replace('"', '\\"')


def _labels(values: dict[str, str]) -> str:
    return "{" + ",".join(f'{key}="{_escape(value)}"' for key, value in values.items()) + "}"


@dataclass
class HistogramState:
    buckets: tuple[float, ...]
    counts: list[int] = field(init=False)
    count: int = 0
    total: float = 0.0

    def __post_init__(self) -> None:
        self.counts = [0 for _ in self.buckets]

    def observe(self, value: float) -> None:
        self.count += 1
        self.total += value
        for index, boundary in enumerate(self.buckets):
            if value <= boundary:
                self.counts[index] += 1


class MetricsRegistry:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._builds: set[str] = set()
        self._http_counts: dict[tuple[str, str, str, str, str, str], int] = defaultdict(int)
        self._http_durations: dict[tuple[str, str, str, str, str], HistogramState] = {}
        self._web_vitals: dict[tuple[str, str, str, str, str, str], HistogramState] = {}

    def register_build(self, source_sha: str) -> None:
        with self._lock:
            self._builds.add(source_sha)

    def record_http(
        self,
        *,
        source_sha: str,
        traffic_class: str,
        surface: str,
        route: str,
        method: str,
        status_code: int,
        duration_seconds: float,
    ) -> None:
        status_class = f"{status_code // 100}xx"
        key = (source_sha, traffic_class, surface, route, method, status_class)
        duration_key = (source_sha, traffic_class, surface, route, method)
        with self._lock:
            self._http_counts[key] += 1
            histogram = self._http_durations.setdefault(duration_key, HistogramState(HTTP_BUCKETS))
            histogram.observe(duration_seconds)

    def record_web_vital(
        self,
        *,
        source_sha: str,
        traffic_class: str,
        surface: str,
        metric: str,
        rating: str,
        navigation_type: str,
        value_ms: float,
    ) -> None:
        key = (source_sha, traffic_class, surface, metric, rating, navigation_type)
        with self._lock:
            histogram = self._web_vitals.setdefault(key, HistogramState(WEB_VITAL_BUCKETS_MS))
            histogram.observe(value_ms)

    def render(self) -> str:
        lines = [
            "# HELP unihub_insight_build_info Immutable release identity for SLI attribution.",
            "# TYPE unihub_insight_build_info gauge",
        ]
        with self._lock:
            for source_sha in sorted(self._builds):
                lines.append(f"unihub_insight_build_info{_labels({'source_sha': source_sha})} 1")

            lines.extend(
                [
                    "# HELP unihub_insight_http_requests_total HTTP requests by finite route and status class.",
                    "# TYPE unihub_insight_http_requests_total counter",
                ]
            )
            for (source_sha, traffic, surface, route, method, status_class), count in sorted(self._http_counts.items()):
                labels = _labels(
                    {
                        "source_sha": source_sha,
                        "traffic_class": traffic,
                        "surface": surface,
                        "route": route,
                        "method": method,
                        "status_class": status_class,
                    }
                )
                lines.append(f"unihub_insight_http_requests_total{labels} {count}")

            lines.extend(
                [
                    "# HELP unihub_insight_http_request_duration_seconds HTTP request duration.",
                    "# TYPE unihub_insight_http_request_duration_seconds histogram",
                ]
            )
            for (source_sha, traffic, surface, route, method), state in sorted(self._http_durations.items()):
                base = {
                    "source_sha": source_sha,
                    "traffic_class": traffic,
                    "surface": surface,
                    "route": route,
                    "method": method,
                }
                for boundary, count in zip(state.buckets, state.counts, strict=True):
                    labels = _labels({**base, "le": str(boundary)})
                    lines.append(f"unihub_insight_http_request_duration_seconds_bucket{labels} {count}")
                lines.append(
                    "unihub_insight_http_request_duration_seconds_bucket"
                    f"{_labels({**base, 'le': '+Inf'})} {state.count}"
                )
                lines.append(f"unihub_insight_http_request_duration_seconds_sum{_labels(base)} {state.total:.9f}")
                lines.append(f"unihub_insight_http_request_duration_seconds_count{_labels(base)} {state.count}")

            lines.extend(
                [
                    "# HELP unihub_insight_web_vital_milliseconds Browser LCP and INP values.",
                    "# TYPE unihub_insight_web_vital_milliseconds histogram",
                ]
            )
            for (source_sha, traffic, surface, metric, rating, navigation_type), state in sorted(
                self._web_vitals.items()
            ):
                base = {
                    "source_sha": source_sha,
                    "traffic_class": traffic,
                    "surface": surface,
                    "metric": metric,
                    "rating": rating,
                    "navigation_type": navigation_type,
                }
                for boundary, count in zip(state.buckets, state.counts, strict=True):
                    lines.append(
                        f"unihub_insight_web_vital_milliseconds_bucket{_labels({**base, 'le': str(boundary)})} {count}"
                    )
                lines.append(
                    f"unihub_insight_web_vital_milliseconds_bucket{_labels({**base, 'le': '+Inf'})} {state.count}"
                )
                lines.append(f"unihub_insight_web_vital_milliseconds_sum{_labels(base)} {state.total:.6f}")
                lines.append(f"unihub_insight_web_vital_milliseconds_count{_labels(base)} {state.count}")
        return "\n".join(lines) + "\n"


metrics = MetricsRegistry()


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for key in (
            "request_id",
            "route",
            "method",
            "status_code",
            "duration_ms",
            "data_mode",
        ):
            if hasattr(record, key):
                payload[key] = getattr(record, key)
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def configure_logging() -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(logging.INFO)
