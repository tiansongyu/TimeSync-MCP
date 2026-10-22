"""Reproducible Synthetic data, never hardware validation."""

import random
from decimal import Decimal

import pytest
from pydantic import ValidationError

from timesync_mcp.analysis.clock_domains import fit_clock, map_series
from timesync_mcp.analysis.correlation import compare
from timesync_mcp.analysis.diagnosis import diagnose, markdown
from timesync_mcp.analysis.periodicity import analyze
from timesync_mcp.analysis.statistics import percentile, summarize
from timesync_mcp.config import Settings
from timesync_mcp.models.clock import ClockDomain, ClockGraph, ClockType
from timesync_mcp.models.measurement import Measurement, Source


def test_statistics():
    stats = summarize([1, 2, 3, 4], object="Synthetic intervals")
    assert stats.mean == stats.median == 2.5
    assert stats.variance == 1.25
    assert stats.mad == 1
    assert stats.rms == pytest.approx((7.5) ** 0.5)
    assert stats.p95 == pytest.approx(3.85)
    assert stats.warnings
    assert summarize([]).mean is None
    assert summarize([4]).standard_deviation == 0
    with pytest.raises(ValueError):
        summarize([float("nan")])
    with pytest.raises(ValueError):
        percentile([1], 101)


def test_periodicity():
    result = analyze([1_000_000_000 + i * 2_500_000 for i in range(4000)], 400, synthetic=True)
    assert result.data["observed_span_rate_hz"] == 400
    assert result.data["interval_statistics"]["standard_deviation"] == 0
    assert result.source.synthetic
    bad = analyze([0, 2_500_000, 5_000_000, 5_000_000, 4_000_000, 100_000_000], 400)
    assert bad.data["backwards_count"] == 1
    assert bad.data["duplicate_count"] == 1
    assert bad.data["potential_abnormal_intervals"] == 1
    assert bad.data["observed_span_rate_hz"] is None
    assert analyze([0]).status == "partial"


def test_synthetic_offset_drift_robust_large_epoch():
    rng = random.Random(42)
    base = 1_800_000_000_000_000_000
    a = [base + i * 2_500_000 for i in range(4000)]
    b = [
        base + 5_000_000 + round(Decimal(x - base) * Decimal("1.00002")) + rng.randint(-100, 100)
        for x in a
    ]
    b[1000] += 10_000  # Outlier below period, so corresponding events remain ordered.
    fit = fit_clock(
        a,
        b,
        source_domain="a",
        target_domain="b",
        correspondence_method="common_events",
        evidence=["Synthetic event counters"],
    )
    # Explicit numerical acceptance: <0.005 ppm rate error, <10 ns anchor offset error.
    assert abs(float((fit.relative_rate - 1) * 1_000_000) - 20) < 0.005
    assert abs(fit.target_anchor_ns - fit.source_anchor_ns - 5_000_000) < 10
    assert fit.residual_rms_ns < 100
    assert fit.sample_count < 4000
    assert fit.uncertainty_ns is None
    assert fit.hardware_verified is False
    assert abs(fit.apply(a[-1]) - b[-1]) < 200
    with pytest.raises(ValueError, match="validity"):
        fit.apply(a[-1] + 1)
    with pytest.raises(ValueError, match="Trusted"):
        fit_clock(
            a, b, source_domain="a", target_domain="b", correspondence_method="nearest", evidence=[]
        )
    graph = ClockGraph(
        domains=[
            ClockDomain(id=n, name=n, clock_type=ClockType.DEVICE_HARDWARE_CLOCK)
            for n in ("a", "b")
        ],
        transformations=[fit],
    )
    assert map_series([a[0]], "a", "b", graph) == [fit.target_anchor_ns]
    graph.transformations[0].kind = "configuration_inference"
    with pytest.raises(ValueError, match="trusted mapping"):
        map_series([a[0]], "a", "b", graph)
    with pytest.raises(ValueError, match="clock domains"):
        map_series([0], None, None, graph)


def test_domain_validation_and_unknown():
    with pytest.raises(ValidationError):
        ClockGraph(domains=[ClockDomain(id="a", name="a")] * 2)
    graph = ClockGraph(domains=[ClockDomain(id="unknown", name="unknown")])
    with pytest.raises(ValueError, match="UNKNOWN"):
        map_series([0], "unknown", "unknown", graph)


def test_pairing():
    assert compare([0, 10, 20], [0, 20], strategy="exact").data["unmatched_a"] == 1
    result = compare([0, 10, 20], [1, 11, 21], strategy="tolerance", tolerance_ns=2)
    assert result.data["paired_count"] == 3
    assert result.data["difference_statistics"]["mean"] == 1
    assert compare([0, 0], [0], strategy="exact").data["paired_count"] == 1
    assert (
        compare(
            [0, 10], [100, 110], strategy="event_id", event_ids_a=["a", "b"], event_ids_b=["a", "b"]
        ).data["difference_statistics"]["mean"]
        == 100
    )
    with pytest.raises(ValueError, match="unique"):
        compare([1, 2], [1, 2], strategy="event_id", event_ids_a=["a", "a"], event_ids_b=["a", "b"])
    with pytest.raises(ValueError, match="nondecreasing"):
        compare([2, 1], [1, 2], strategy="exact")
    assert compare([1], [2], strategy="exact").status == "partial"


def test_diagnosis_evidence():
    result = analyze([0, 0, 1, -1], synthetic=True)
    report = diagnose([result], Settings())
    assert {"ros.header_backwards", "ros.header_zero"} <= {f.rule_id for f in report.findings}
    assert all(f.required_evidence and f.observed_values for f in report.findings)
    assert "Synthetic" not in markdown(report) or result.source.synthetic
    assert "evidence" in markdown(report).lower()


def test_measurement_no_fake_precision():
    value = Measurement(
        metric="offset", value=1, unit="ns", source=Source(collector="Synthetic", synthetic=True)
    )
    assert value.uncertainty_ns is None
    with pytest.raises(ValidationError):
        Measurement(metric="offset", value=float("inf"), unit="ns", source=value.source)


def test_ros_zero_header_and_simulation_mapping_refusal():
    from timesync_mcp.models.measurement import Result, json_data
    from timesync_mcp.ros2.analysis import compare_topics, inspect_topic

    row = {
        "topic_info": {"has_header": True},
        "header_ns": [0, 0, 0],
        "arrival_monotonic_ns": [1, 2, 3],
        "received_count": 3,
        "retained_count": 3,
        "truncated": False,
        "qos_checks": [],
    }
    raw = Result(
        source=Source(collector="Synthetic", synthetic=True),
        data=json_data(
            {
                "topics": {"/a": row, "/b": row},
                "observation_duration_ns": 3,
                "publisher_clock_parameters": [{"node": "/sim", "use_sim_time": True}],
            }
        ),
    )
    inspected = inspect_topic(raw, "/a")
    assert inspected.data["header_analysis"]["data"]["zero_timestamps"] == 3
    assert inspected.data["latency_ns"] is None
    graph = ClockGraph(
        domains=[ClockDomain(id="system", name="system", clock_type=ClockType.SYSTEM_REALTIME)]
    )
    settings = Settings(graph=graph, topic_clock_domains={"/a": "system", "/b": "system"})
    with pytest.raises(ValueError, match="Simulation-time"):
        compare_topics(raw, "/a", "/b", settings, "exact", 0)
