#!/usr/bin/env python3
"""Bounded production load probe for the UniHub Insight UDS API.

The probe uses the same trusted-proxy boundary as Caddy without printing the
secret. It measures synthetic concurrency only; it never qualifies the seven
day real-user SLI gate by itself.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import math
import os
import statistics
import time
from collections import defaultdict
from dataclasses import dataclass
from typing import Any

import httpx


@dataclass(frozen=True)
class Probe:
    name: str
    method: str
    path: str
    budget_ms: float
    payload: dict[str, Any] | None = None


def widget(
    widget_id: str,
    module: str,
    metric_id: str,
    visualization: str,
    dimensions: list[str],
) -> dict[str, Any]:
    return {
        "widget_id": widget_id,
        "module": module,
        "metric_id": metric_id,
        "metric_version": 1,
        "query_contract_version": 1,
        "dimensions": dimensions,
        "time_grain": "month",
        "filters": {},
        "comparisons": ["previous-year", "target"],
        "sort": [],
        "limit": 100,
        "visualization": visualization,
    }


def mixed_dashboard() -> dict[str, Any]:
    return {
        "widgets": [
            widget("sales-trend", "sales", "sales.total", "line", ["time"]),
            widget("sales-mix", "sales", "sales.total", "treemap", ["category"]),
            widget(
                "performance-relation",
                "performance",
                "performance.average",
                "scatter",
                ["store"],
            ),
            widget(
                "performance-distribution",
                "performance",
                "performance.average",
                "histogram",
                ["store"],
            ),
            widget(
                "campaigns-mix",
                "campaigns",
                "campaigns.focus_sales",
                "treemap",
                ["category"],
            ),
            widget(
                "workforce-distribution",
                "workforce",
                "workforce.productivity",
                "histogram",
                ["store"],
            ),
            widget(
                "compensation-trend",
                "compensation",
                "compensation.payroll",
                "line",
                ["time"],
            ),
            widget(
                "finance-bridge", "finance", "finance.ebit", "waterfall", ["category"]
            ),
            widget(
                "planning-relation",
                "planning",
                "planning.forecast",
                "scatter",
                ["store"],
            ),
            widget("planning-trend", "planning", "planning.forecast", "line", ["time"]),
        ]
    }


def percentile(values: list[float], fraction: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = max(0, math.ceil(len(ordered) * fraction) - 1)
    return ordered[index]


def probe_catalog(period: str) -> list[Probe]:
    module_groups = {
        "sales": "manager",
        "performance": "manager",
        "campaigns": "manager",
        "workforce": "manager",
        "compensation": "sensitive",
        "finance": "sensitive",
        "planning": "manager",
    }
    probes = [Probe("overview", "GET", f"/api/v1/overview?period={period}", 1_000)]
    probes.extend(
        Probe(
            f"module-{module}",
            "GET",
            f"/api/v1/modules/{module}?period={period}&range=12",
            2_000,
            {"_identity": identity},
        )
        for module, identity in module_groups.items()
    )
    probes.append(
        Probe(
            "dashboard-batch-10",
            "POST",
            f"/api/v1/query/batch?period={period}",
            2_000,
            mixed_dashboard(),
        )
    )
    return probes


def identity_headers(secret: str, identity: str = "sensitive") -> dict[str, str]:
    groups = {
        "manager": "unihub-manager",
        "sensitive": "unihub-manager|unihub-hr|unihub-pnl",
    }[identity]
    return {
        "X-UniHub-Proxy-Secret": secret,
        "X-Authentik-Uid": "insight-load-gate",
        "X-Authentik-Groups": groups,
    }


async def request_once(
    client: httpx.AsyncClient,
    probe: Probe,
    secret: str,
) -> tuple[str, float, dict[str, Any] | None]:
    payload = probe.payload
    identity = "sensitive"
    if payload and "_identity" in payload:
        identity = str(payload["_identity"])
        payload = None
    started = time.perf_counter()
    response = await client.request(
        probe.method,
        probe.path,
        headers=identity_headers(secret, identity),
        json=payload,
    )
    body = await response.aread()
    duration_ms = (time.perf_counter() - started) * 1_000
    if response.status_code != 200:
        raise RuntimeError(f"{probe.name} returned HTTP {response.status_code}")
    parsed: dict[str, Any] | None = None
    if response.headers.get("content-type", "").startswith("application/json"):
        parsed = json.loads(body)
    if probe.name == "dashboard-batch-10" and parsed is not None:
        unexpected = [
            f"{result['widget_id']}:{result['error']['code']}"
            for result in parsed.get("results", [])
            if result.get("error") and result["error"].get("code") != "unavailable"
        ]
        if unexpected:
            raise RuntimeError(f"dashboard batch returned errors: {unexpected}")
    return probe.name, duration_ms, parsed


async def run_probe(
    client: httpx.AsyncClient,
    probe: Probe,
    secret: str,
    iterations: int,
    concurrency: int,
) -> list[float]:
    await request_once(client, probe, secret)
    semaphore = asyncio.Semaphore(concurrency)

    async def one() -> float:
        async with semaphore:
            _name, duration_ms, _payload = await request_once(client, probe, secret)
            return duration_ms

    return list(await asyncio.gather(*(one() for _ in range(iterations))))


async def run_contention(
    client: httpx.AsyncClient,
    period: str,
    secret: str,
    iterations: int,
    concurrency: int,
) -> dict[str, list[float]]:
    batch_probe = Probe(
        "contention-seed",
        "POST",
        f"/api/v1/query/batch?period={period}",
        2_000,
        {
            "widgets": [
                widget("sales-table", "sales", "sales.total", "table", ["store"])
            ]
        },
    )
    _name, _duration, batch = await request_once(client, batch_probe, secret)
    if batch is None:
        raise RuntimeError("contention seed did not return JSON")
    result = batch["results"][0]
    shared = {
        "snapshot_id": batch["snapshot"]["id"],
        "query": result["query"],
        "page": 1,
        "page_size": 100,
    }
    probes = [
        Probe("contention-overview", "GET", f"/api/v1/overview?period={period}", 1_200),
        Probe(
            "contention-inspect",
            "POST",
            f"/api/v1/query/inspect?period={period}",
            2_000,
            shared,
        ),
        Probe(
            "contention-csv",
            "POST",
            f"/api/v1/query/export.csv?period={period}",
            2_000,
            shared,
        ),
        Probe(
            "contention-xlsx",
            "GET",
            f"/api/v1/exports/modules/sales.xlsx?period={period}&range=12",
            8_000,
            {"_identity": "manager"},
        ),
    ]
    semaphore = asyncio.Semaphore(concurrency)
    samples: dict[str, list[float]] = defaultdict(list)

    async def one(probe: Probe) -> None:
        async with semaphore:
            name, duration_ms, _payload = await request_once(client, probe, secret)
            samples[name].append(duration_ms)

    await asyncio.gather(*(one(probe) for _ in range(iterations) for probe in probes))
    return dict(samples)


def summarize(name: str, values: list[float], budget_ms: float) -> dict[str, Any]:
    return {
        "name": name,
        "requests": len(values),
        "median_ms": round(statistics.median(values), 2),
        "p95_ms": round(percentile(values, 0.95), 2),
        "max_ms": round(max(values), 2),
        "budget_ms": budget_ms,
        "passed": percentile(values, 0.95) < budget_ms and max(values) < 8_000,
    }


async def run(arguments: argparse.Namespace) -> int:
    secret = os.environ.get("UNIHUB_INSIGHT_TRUSTED_PROXY_SECRET", "")
    if len(secret) < 32:
        raise RuntimeError("UNIHUB_INSIGHT_TRUSTED_PROXY_SECRET is required")
    transport = httpx.AsyncHTTPTransport(uds=arguments.socket)
    timeout = httpx.Timeout(8.0, connect=2.0)
    results: list[dict[str, Any]] = []
    async with httpx.AsyncClient(
        transport=transport, base_url="http://localhost", timeout=timeout
    ) as client:
        for probe in probe_catalog(arguments.period):
            values = await run_probe(
                client,
                probe,
                secret,
                arguments.iterations,
                arguments.concurrency,
            )
            results.append(summarize(probe.name, values, probe.budget_ms))
        contention = await run_contention(
            client,
            arguments.period,
            secret,
            max(2, arguments.iterations // 2),
            arguments.concurrency,
        )
        budgets = {
            "contention-overview": 1_200,
            "contention-inspect": 2_000,
            "contention-csv": 2_000,
            "contention-xlsx": 8_000,
        }
        results.extend(
            summarize(name, values, budgets[name])
            for name, values in contention.items()
        )
    print(
        json.dumps(
            {"synthetic": True, "period": arguments.period, "results": results},
            indent=2,
        )
    )
    return 0 if all(result["passed"] for result in results) else 1


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run the bounded UniHub Insight production load gate"
    )
    parser.add_argument("--socket", default="/run/unihub-insight/api.sock")
    parser.add_argument("--period", required=True)
    parser.add_argument(
        "--iterations", type=int, default=20, choices=range(2, 101), metavar="[2-100]"
    )
    parser.add_argument(
        "--concurrency", type=int, default=5, choices=range(1, 11), metavar="[1-10]"
    )
    arguments = parser.parse_args()
    raise SystemExit(asyncio.run(run(arguments)))


if __name__ == "__main__":
    main()
