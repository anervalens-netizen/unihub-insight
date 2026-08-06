from ops.scripts.evaluate_sli import Evidence, evaluate

SHA = "a" * 40
SURFACES = ("overview", "module-sales")
START = 1_000_000.0
END = START + 604_800


def evidence(**overrides: object) -> Evidence:
    values: dict[str, object] = {
        "build_samples": tuple(float(value) for value in range(int(START), int(END) + 1, 60)),
        "request_counts": {"overview": 120.0, "module-sales": 140.0},
        "http_p95_seconds": {"overview": 0.75, "module-sales": 1.5},
        "real_5xx": 0.0,
        "rum_counts": {"LCP": 10.0, "INP": 8.0},
        "rum_p75_ms": {"LCP": 2000.0, "INP": 180.0},
    }
    values.update(overrides)
    return Evidence(**values)  # type: ignore[arg-type]


def verdict(candidate: Evidence) -> dict[str, object]:
    return evaluate(
        candidate,
        source_sha=SHA,
        surfaces=SURFACES,
        start=START,
        end=END,
        step=60,
        max_gap_seconds=90,
        min_requests=100,
        min_rum_samples=1,
    )


def test_sli_gate_passes_only_complete_real_evidence() -> None:
    result = verdict(evidence())

    assert result["verdict"] == "passed"


def test_sli_gate_stays_pending_for_short_release_or_missing_real_samples() -> None:
    result = verdict(
        evidence(
            build_samples=(END - 3600, END),
            request_counts={"overview": 99.0},
            rum_counts={},
            rum_p75_ms={},
        )
    )

    assert result["verdict"] == "pending"
    assert result["pending_reasons"]


def test_sli_gate_fails_budget_or_real_5xx_regression() -> None:
    result = verdict(
        evidence(
            http_p95_seconds={"overview": 1.25, "module-sales": 1.5},
            real_5xx=1.0,
        )
    )

    assert result["verdict"] == "failed"
    assert result["failure_reasons"]
