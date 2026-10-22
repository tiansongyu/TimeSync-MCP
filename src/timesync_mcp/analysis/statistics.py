"""Population statistics; linear-interpolated percentiles (type 7)."""

import math
import statistics
from collections.abc import Sequence

from ..models.measurement import Model


class Statistics(Model):
    count: int
    unit: str
    object: str
    mean: float | None = None
    median: float | None = None
    standard_deviation: float | None = None
    variance: float | None = None
    minimum: float | None = None
    maximum: float | None = None
    rms: float | None = None
    p95: float | None = None
    p99: float | None = None
    mad: float | None = None
    warnings: list[str]


def percentile(values: Sequence[int | float], q: float) -> float | None:
    if not 0 <= q <= 100:
        raise ValueError("Percentile must be 0..100")
    if not values:
        return None
    ordered = sorted(values)
    pos = (len(ordered) - 1) * q / 100
    index = int(pos)
    frac = pos - index
    return (
        float(ordered[index])
        if index + 1 == len(ordered)
        else float(ordered[index] + (ordered[index + 1] - ordered[index]) * frac)
    )


def summarize(
    values: Sequence[int | float], *, unit: str = "ns", object: str = "timestamp intervals"
) -> Statistics:
    warnings = []
    if len(values) < 100:
        warnings.append(
            "Small sample: P95/P99 are descriptive, not stable tail estimates (<100 samples)."
        )
    if not values:
        return Statistics(
            count=0, unit=unit, object=object, warnings=warnings + ["Insufficient samples."]
        )
    if not all(math.isfinite(v) for v in values):
        raise ValueError("Statistics require finite values")
    median = statistics.median(values)
    return Statistics(
        count=len(values),
        unit=unit,
        object=object,
        mean=statistics.fmean(values),
        median=float(median),
        standard_deviation=statistics.pstdev(values),
        variance=statistics.pvariance(values),
        minimum=float(min(values)),
        maximum=float(max(values)),
        rms=math.sqrt(statistics.fmean(v * v for v in values)),
        p95=percentile(values, 95),
        p99=percentile(values, 99),
        mad=float(statistics.median(abs(v - median) for v in values)),
        warnings=warnings,
    )
