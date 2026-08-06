#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
import re
import time
import urllib.parse
import urllib.request
from urllib.error import HTTPError
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

SOURCE_SHA_PATTERN: Final[re.Pattern[str]] = re.compile(r"^[0-9a-f]{40}$")
DEFAULT_SURFACES: Final[tuple[str, ...]] = (
    "overview",
    "monthly-review",
    "module-sales",
    "module-performance",
    "module-campaigns",
    "module-workforce",
    "module-compensation",
    "module-finance",
    "module-planning",
    "custom-dashboards",
)
RUM_BUDGETS_MS: Final[dict[str, float]] = {"LCP": 2500.0, "INP": 200.0}


@dataclass(frozen=True)
class Evidence:
    build_samples: tuple[float, ...]
    request_counts: dict[str, float]
    http_p95_seconds: dict[str, float]
    real_5xx: float
    rum_counts: dict[str, float]
    rum_p75_ms: dict[str, float]


class PrometheusClient:
    def __init__(self, base_url: str, timeout_seconds: float = 10.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds

    def _get(self, path: str, params: dict[str, str]) -> dict[str, Any]:
        url = f"{self.base_url}{path}?{urllib.parse.urlencode(params)}"
        try:
            with urllib.request.urlopen(url, timeout=self.timeout_seconds) as response:  # noqa: S310
                payload = json.load(response)
        except HTTPError as error:
            detail = error.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Prometheus HTTP {error.code}: {detail}") from error
        if payload.get("status") != "success":
            raise RuntimeError(f"Prometheus query failed: {payload}")
        return payload

    def instant(self, query: str, at: float) -> dict[str, Any]:
        return self._get("/api/v1/query", {"query": query, "time": str(at)})

    def range(self, query: str, start: float, end: float, step: int) -> dict[str, Any]:
        return self._get(
            "/api/v1/query_range",
            {"query": query, "start": str(start), "end": str(end), "step": str(step)},
        )


def _result(payload: dict[str, Any]) -> list[dict[str, Any]]:
    data = payload.get("data", {})
    result = data.get("result", []) if isinstance(data, dict) else []
    return result if isinstance(result, list) else []


def _vector(payload: dict[str, Any], label: str) -> dict[str, float]:
    values: dict[str, float] = {}
    for item in _result(payload):
        metric = item.get("metric", {})
        value = item.get("value", [])
        if (
            not isinstance(metric, dict)
            or not isinstance(value, list)
            or len(value) != 2
        ):
            continue
        name = metric.get(label)
        if isinstance(name, str):
            values[name] = float(value[1])
    return values


def _scalar(payload: dict[str, Any]) -> float:
    result = _result(payload)
    if not result:
        return 0.0
    value = result[0].get("value", [])
    return float(value[1]) if isinstance(value, list) and len(value) == 2 else 0.0


def _build_samples(payload: dict[str, Any]) -> tuple[float, ...]:
    samples: list[float] = []
    for item in _result(payload):
        values = item.get("values", [])
        if not isinstance(values, list):
            continue
        samples.extend(
            float(value[0])
            for value in values
            if len(value) == 2 and float(value[1]) > 0.0
        )
    return tuple(sorted(set(samples)))


def collect_evidence(
    client: PrometheusClient,
    *,
    source_sha: str,
    surfaces: tuple[str, ...],
    start: float,
    end: float,
    step: int,
    max_gap_seconds: int,
) -> Evidence:
    window = f"{int(end - start)}s"
    surface_regex = "^(?:" + "|".join(surfaces) + ")$"
    labels = (
        f'source_sha="{source_sha}",traffic_class="real",surface=~"{surface_regex}"'
    )
    build = client.range(
        "count_over_time("
        f'unihub_insight_build_info{{source_sha="{source_sha}"}}[{max_gap_seconds}s])',
        start,
        end,
        step,
    )
    request_counts = client.instant(
        "sum by (surface) (increase(unihub_insight_http_requests_total"
        f'{{{labels},status_class=~"2xx|3xx"}}[{window}]))',
        end,
    )
    http_p95 = client.instant(
        "histogram_quantile(0.95, sum by (le, surface) "
        f"(increase(unihub_insight_http_request_duration_seconds_bucket{{{labels}}}[{window}])))",
        end,
    )
    real_5xx = client.instant(
        "sum(increase(unihub_insight_http_requests_total"
        f'{{source_sha="{source_sha}",traffic_class="real",status_class="5xx"}}[{window}])) or vector(0)',
        end,
    )
    rum_counts = client.instant(
        "sum by (metric) (increase(unihub_insight_web_vital_milliseconds_count"
        f'{{source_sha="{source_sha}",traffic_class="real"}}[{window}]))',
        end,
    )
    rum_p75 = client.instant(
        "histogram_quantile(0.75, sum by (le, metric) "
        "(increase(unihub_insight_web_vital_milliseconds_bucket"
        f'{{source_sha="{source_sha}",traffic_class="real"}}[{window}])))',
        end,
    )
    return Evidence(
        build_samples=_build_samples(build),
        request_counts=_vector(request_counts, "surface"),
        http_p95_seconds=_vector(http_p95, "surface"),
        real_5xx=_scalar(real_5xx),
        rum_counts=_vector(rum_counts, "metric"),
        rum_p75_ms=_vector(rum_p75, "metric"),
    )


def evaluate(
    evidence: Evidence,
    *,
    source_sha: str,
    surfaces: tuple[str, ...],
    start: float,
    end: float,
    step: int,
    max_gap_seconds: int,
    min_requests: int,
    min_rum_samples: int,
) -> dict[str, Any]:
    pending: list[str] = []
    failed: list[str] = []
    samples = evidence.build_samples
    gaps = [right - left for left, right in zip(samples, samples[1:], strict=False)]
    max_gap = max(gaps, default=math.inf)
    coverage_passed = bool(
        samples
        and samples[0] <= start + step
        and samples[-1] >= end - step
        and max_gap <= max_gap_seconds
    )
    if not coverage_passed:
        pending.append(
            "Exact SHA does not yet have seven continuous clean days of scrape coverage."
        )

    request_gates: dict[str, dict[str, Any]] = {}
    for surface in surfaces:
        count = evidence.request_counts.get(surface, 0.0)
        p95 = evidence.http_p95_seconds.get(surface)
        budget = 1.0 if surface == "overview" else 2.0
        request_gates[surface] = {
            "real_requests": round(count, 3),
            "minimum": min_requests,
            "p95_seconds": round(p95, 6)
            if p95 is not None and math.isfinite(p95)
            else None,
            "budget_seconds": budget,
            "passed": count >= min_requests and p95 is not None and p95 < budget,
        }
        if count < min_requests:
            pending.append(f"{surface} has {count:.3f}/{min_requests} real requests.")
        elif p95 is None:
            pending.append(f"{surface} has no real latency histogram.")
        elif not math.isfinite(p95) or p95 >= budget:
            failed.append(f"{surface} p95 {p95:.3f}s exceeds {budget:.3f}s.")

    if evidence.real_5xx > 0:
        failed.append(f"Exact SHA recorded {evidence.real_5xx:.3f} real 5xx responses.")

    rum_gates: dict[str, dict[str, Any]] = {}
    for metric, budget in RUM_BUDGETS_MS.items():
        count = evidence.rum_counts.get(metric, 0.0)
        p75 = evidence.rum_p75_ms.get(metric)
        rum_gates[metric] = {
            "real_samples": round(count, 3),
            "minimum": min_rum_samples,
            "p75_ms": round(p75, 3) if p75 is not None and math.isfinite(p75) else None,
            "budget_ms": budget,
            "passed": count >= min_rum_samples and p75 is not None and p75 < budget,
        }
        if count < min_rum_samples:
            pending.append(
                f"{metric} has {count:.3f}/{min_rum_samples} real RUM samples."
            )
        elif p75 is None:
            pending.append(f"{metric} has no real RUM histogram.")
        elif not math.isfinite(p75) or p75 >= budget:
            failed.append(f"{metric} p75 {p75:.3f}ms exceeds {budget:.3f}ms.")

    verdict = "failed" if failed else "pending" if pending else "passed"
    return {
        "verdict": verdict,
        "source_sha": source_sha,
        "window": {
            "start_epoch": start,
            "end_epoch": end,
            "seconds": end - start,
            "build_samples": len(samples),
            "first_sample_epoch": samples[0] if samples else None,
            "last_sample_epoch": samples[-1] if samples else None,
            "max_gap_seconds": round(max_gap, 3) if math.isfinite(max_gap) else None,
            "gap_budget_seconds": max_gap_seconds,
            "passed": coverage_passed,
        },
        "http": {
            "real_5xx": round(evidence.real_5xx, 3),
            "surfaces": request_gates,
        },
        "rum": rum_gates,
        "pending_reasons": pending,
        "failure_reasons": failed,
    }


def _source_sha(value: str | None) -> str:
    resolved = value
    if resolved is None:
        path = Path("/opt/unihub-insight/current/SOURCE_SHA")
        resolved = path.read_text(encoding="utf-8").strip() if path.is_file() else ""
    if not SOURCE_SHA_PATTERN.fullmatch(resolved):
        raise ValueError("source SHA must be an exact 40-character lowercase Git SHA")
    return resolved


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Evaluate the exact-SHA seven-day real-traffic SLI gate"
    )
    parser.add_argument("--prometheus-url", default="http://127.0.0.1:9090")
    parser.add_argument("--source-sha")
    parser.add_argument("--window-days", type=float, default=7.0)
    parser.add_argument("--min-requests", type=int, default=100)
    parser.add_argument("--min-rum-samples", type=int, default=1)
    parser.add_argument("--step-seconds", type=int, default=60)
    parser.add_argument("--max-gap-seconds", type=int, default=90)
    parser.add_argument("--surfaces", default=",".join(DEFAULT_SURFACES))
    arguments = parser.parse_args()

    source_sha = _source_sha(arguments.source_sha)
    surfaces = tuple(
        dict.fromkeys(
            item.strip() for item in arguments.surfaces.split(",") if item.strip()
        )
    )
    unknown = set(surfaces) - set(DEFAULT_SURFACES)
    if not surfaces or unknown:
        raise ValueError(
            f"surfaces must be selected from {', '.join(DEFAULT_SURFACES)}"
        )
    if (
        arguments.window_days <= 0
        or arguments.min_requests <= 0
        or arguments.min_rum_samples <= 0
    ):
        raise ValueError("window and minimum sample counts must be positive")
    end = time.time()
    start = end - arguments.window_days * 86_400
    client = PrometheusClient(arguments.prometheus_url)
    evidence = collect_evidence(
        client,
        source_sha=source_sha,
        surfaces=surfaces,
        start=start,
        end=end,
        step=arguments.step_seconds,
        max_gap_seconds=arguments.max_gap_seconds,
    )
    result = evaluate(
        evidence,
        source_sha=source_sha,
        surfaces=surfaces,
        start=start,
        end=end,
        step=arguments.step_seconds,
        max_gap_seconds=arguments.max_gap_seconds,
        min_requests=arguments.min_requests,
        min_rum_samples=arguments.min_rum_samples,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(
        0
        if result["verdict"] == "passed"
        else 2
        if result["verdict"] == "pending"
        else 1
    )


if __name__ == "__main__":
    main()
