import math
import statistics

from ..models.measurement import Result, Source, json_data
from .statistics import summarize


def analyze(
    timestamps_ns: list[int],
    expected_rate_hz: float | None = None,
    *,
    object: str = "header timestamp intervals",
    synthetic: bool = False,
) -> Result:
    if expected_rate_hz is not None and (
        not math.isfinite(expected_rate_hz) or expected_rate_hz <= 0
    ):
        raise ValueError("expected_rate_hz must be positive and finite")
    deltas = [b - a for a, b in zip(timestamps_ns, timestamps_ns[1:], strict=False)]
    stats = summarize(deltas, object=object)
    positive = [x for x in deltas if x > 0]
    expected = 1e9 / expected_rate_hz if expected_rate_hz else None
    baseline = expected or (statistics.median(positive) if positive else None)
    mad = statistics.median(abs(x - baseline) for x in positive) if baseline and positive else 0
    threshold = max(1.5 * baseline, baseline + 6 * mad) if baseline else None
    abnormal = sum(x > threshold for x in deltas) if threshold is not None else 0
    backwards = sum(x < 0 for x in deltas)
    repeats = sum(x == 0 for x in deltas)
    span = timestamps_ns[-1] - timestamps_ns[0] if len(timestamps_ns) > 1 else 0
    rate = (len(timestamps_ns) - 1) * 1e9 / span if span > 0 and not backwards else None
    result = Result(
        measurement_kind="calculated",
        source=Source(collector="periodicity_analysis", synthetic=synthetic),
        status="valid" if deltas else "partial",
        data=json_data(
            {
                "measurement_kind": "calculated",
                "sample_count": len(timestamps_ns),
                "zero_timestamps": timestamps_ns.count(0),
                "backwards_count": backwards,
                "duplicate_count": repeats,
                "observed_span_rate_hz": rate,
                "interval_statistics": stats.model_dump(mode="json"),
                "expected_period_ns": expected,
                "large_interval_threshold_ns": threshold,
                "potential_abnormal_intervals": abnormal,
                "jitter_definition": "population standard deviation of all observed intervals",
                "period_error_statistics": summarize(
                    [d - expected for d in deltas], object="observed interval minus expected period"
                ).model_dump(mode="json")
                if expected
                else None,
            }
        ),
        warnings=[
            "Intervals describe the supplied timestamp sequence, not verified physical sampling jitter.",
            "Large intervals indicate suspected missing samples or transport/observation anomalies; no physical lost-sample count is inferred.",
            "Large interval threshold is an engineering heuristic: max(1.5*baseline, baseline+6*MAD).",
        ],
    )
    result.warnings.extend(stats.warnings)
    return result
