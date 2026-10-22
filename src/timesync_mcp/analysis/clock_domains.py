from decimal import Decimal, localcontext
from statistics import median

from ..models.clock import ClockGraph, ClockTransformation, ClockType


def map_series(
    values: list[int], source: str | None, target: str | None, graph: ClockGraph
) -> list[int]:
    domains = {domain.id: domain for domain in graph.domains}
    if not source or not target or source not in domains or target not in domains:
        raise ValueError("Cannot establish trusted mapping: clock domains are not configured")
    if any(domains[x].clock_type == ClockType.UNKNOWN for x in (source, target)):
        raise ValueError("Cannot compare UNKNOWN clock domains")
    if source == target:
        return values
    # Only explicit forward, measured transformations; no inferred inverse or extrapolation.
    queue = [(source, values, {source})]
    globally_visited = {source}
    while queue:
        current, sequence, visited = queue.pop(0)
        for edge in graph.transformations:
            if (
                edge.source_domain != current
                or edge.target_domain in globally_visited
                or edge.kind != "measured"
            ):
                continue
            try:
                mapped = [edge.apply(v) for v in sequence]
            except ValueError:
                continue
            if edge.target_domain == target:
                return mapped
            globally_visited.add(edge.target_domain)
            queue.append((edge.target_domain, mapped, visited | {edge.target_domain}))
    raise ValueError("Cannot establish trusted mapping: no valid measured transformation path")


def fit_clock(
    a: list[int],
    b: list[int],
    *,
    source_domain: str,
    target_domain: str,
    correspondence_method: str,
    evidence: list[str],
) -> ClockTransformation:
    if (
        correspondence_method not in ("common_events", "hardware_verified", "validated_mapping")
        or not evidence
    ):
        raise ValueError(
            "Trusted corresponding events or validated mapping evidence required for drift estimation"
        )
    if len(a) != len(b) or len(a) < 3 or len(a) > 100_000:
        raise ValueError("Need 3..100000 one-to-one corresponding samples")
    if any(y <= x for x, y in zip(a, a[1:], strict=False)) or any(
        y <= x for x, y in zip(b, b[1:], strict=False)
    ):
        raise ValueError("Paired event timelines must be strictly increasing")
    with localcontext() as ctx:
        ctx.prec = 40
        x = [Decimal(v - a[0]) for v in a]
        y = [Decimal(v - b[0]) for v in b]
        # Robust initial rate from widely separated event pairs; bounded O(n).
        half = len(a) // 2
        stride = max(1, half // 2000)
        slopes = [(y[i + half] - y[i]) / (x[i + half] - x[i]) for i in range(0, half, stride)]
        rate = median(slopes)
        intercept = median([yi - rate * xi for xi, yi in zip(x, y, strict=True)])
        kept = list(range(len(a)))
        for _ in range(3):
            residuals = [yi - rate * xi - intercept for xi, yi in zip(x, y, strict=True)]
            center = median(residuals)
            mad = median([abs(v - center) for v in residuals])
            kept = [
                i for i, v in enumerate(residuals) if abs(v - center) <= max(Decimal(1), 6 * mad)
            ]
            if len(kept) < 3:
                raise ValueError("Insufficient inliers for robust clock fit")
            mx = sum((x[i] for i in kept), Decimal(0)) / len(kept)
            my = sum((y[i] for i in kept), Decimal(0)) / len(kept)
            denominator = sum(((x[i] - mx) ** 2 for i in kept), Decimal(0))
            if not denominator:
                raise ValueError("No event time span for drift estimation")
            rate = sum(((x[i] - mx) * (y[i] - my) for i in kept), Decimal(0)) / denominator
            intercept = my - rate * mx
        rms = (
            sum(((y[i] - rate * x[i] - intercept) ** 2 for i in kept), Decimal(0)) / len(kept)
        ).sqrt()
        return ClockTransformation(
            source_domain=source_domain,
            target_domain=target_domain,
            relative_rate=rate,
            source_anchor_ns=a[0],
            target_anchor_ns=b[0] + round(intercept),
            method=f"centered robust least squares; {correspondence_method}; {len(a) - len(kept)} rejected",
            evidence=evidence,
            kind="measured",
            valid_from_ns=min(a),
            valid_until_ns=max(a),
            sample_count=len(kept),
            residual_rms_ns=float(rms),
            uncertainty_ns=None,
            hardware_verified=correspondence_method == "hardware_verified",
        )
