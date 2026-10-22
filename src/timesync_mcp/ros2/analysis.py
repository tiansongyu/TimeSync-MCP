from typing import Any, Literal

from ..analysis.clock_domains import map_series
from ..analysis.correlation import compare
from ..analysis.periodicity import analyze
from ..config import Settings
from ..models.measurement import Result, Source, json_data


def topic_record(raw: Result, topic: str) -> dict[str, Any]:
    data = raw.data.get("topics")
    if not isinstance(data, dict) or not isinstance(data.get(topic), dict):
        raise ValueError("No topic sampling evidence")
    row = data[topic]
    assert isinstance(row, dict)
    return row


def inspect_topic(raw: Result, topic: str, expected_rate_hz: float | None = None) -> Result:
    if raw.status != "valid":
        return raw
    record = topic_record(raw, topic)
    headers = record.get("header_ns", [])
    arrivals = record.get("arrival_monotonic_ns", [])
    header = analyze(headers, expected_rate_hz) if headers else None
    arrival = analyze(arrivals, object="subscriber callback CLOCK_MONOTONIC intervals")
    duration = raw.data.get("observation_duration_ns")
    result = Result(
        measurement_kind="calculated",
        status="valid" if headers and arrivals else "partial",
        source=Source(collector="ros2_timestamp_analysis"),
        data=json_data(
            {
                "topic": topic,
                "received_count": record["received_count"],
                "retained_count": record["retained_count"],
                "truncated": record["truncated"],
                "invalid_header_count": record.get("invalid_header_count", 0),
                "topic_info": record["topic_info"],
                "qos_checks": record["qos_checks"],
                "publisher_clock_parameters": raw.data.get("publisher_clock_parameters"),
                "observation_duration_ns": duration,
                "received_rate_hz": record["received_count"] * 1e9 / duration
                if isinstance(duration, int) and duration > 0
                else None,
                "header_analysis": header.model_dump(mode="json") if header else None,
                "arrival_analysis": arrival.model_dump(mode="json"),
                "latency_ns": None,
                "clock_domain": "unknown",
            }
        ),
        warnings=[
            "Header stamp source is unknown; no Header-to-arrival latency is calculated.",
            "Subscriber callback jitter does not prove hardware sampling jitter.",
        ],
    )
    if not headers:
        result.warnings.append(
            "No usable Header timestamps: message may lack Header, or no messages were received."
        )
    if record["truncated"]:
        result.warnings.append(
            "Sample cap reached; retained timestamps cover only the beginning of the window."
        )
    return result


def compare_topics(
    raw: Result,
    topic_a: str,
    topic_b: str,
    settings: Settings,
    strategy: Literal["exact", "tolerance"],
    tolerance_ns: int,
) -> Result:
    if raw.status != "valid":
        return raw
    a, b = topic_record(raw, topic_a), topic_record(raw, topic_b)
    if not a["header_ns"] or not b["header_ns"]:
        raise ValueError("Both topics need usable Header timestamps")
    source, target = (
        settings.topic_clock_domains.get(topic_a),
        settings.topic_clock_domains.get(topic_b),
    )
    sim_values = raw.data.get("publisher_clock_parameters", [])
    # A graph containing known simulation-time publishers cannot silently map to UTC/system time.
    if isinstance(sim_values, list) and any(
        isinstance(p, dict) and p.get("use_sim_time") is True for p in sim_values
    ):
        domains = {d.id: d for d in settings.graph.domains}
        if not all(
            d in domains and domains[d].clock_type.value == "ROS_SIM_TIME" for d in (source, target)
        ):
            raise ValueError("Simulation-time publisher conflicts with configured clock domains")
    mapped = map_series(a["header_ns"], source, target, settings.graph)
    result = compare(mapped, b["header_ns"], strategy=strategy, tolerance_ns=tolerance_ns)
    result.data.update(
        json_data(
            {
                "source_domain": source,
                "target_domain": target,
                "domain_evidence": "operator configuration",
                "sample_count_a": a["received_count"],
                "sample_count_b": b["received_count"],
                "retained_count_a": a["retained_count"],
                "retained_count_b": b["retained_count"],
                "truncated_a": a["truncated"],
                "truncated_b": b["truncated"],
                "publisher_clock_parameters": sim_values,
                "transformation_paths": [
                    e.model_dump(mode="json") for e in settings.graph.transformations
                ],
            }
        )
    )
    return result
