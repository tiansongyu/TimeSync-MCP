from typing import Literal

from ..models.measurement import Result, Source, json_data
from .statistics import summarize


def compare(
    a: list[int],
    b: list[int],
    *,
    strategy: Literal["exact", "tolerance", "event_id"],
    tolerance_ns: int = 0,
    event_ids_a: list[str] | None = None,
    event_ids_b: list[str] | None = None,
) -> Result:
    if tolerance_ns < 0:
        raise ValueError("tolerance_ns must be nonnegative")
    pairs: list[tuple[int, int]] = []
    if strategy == "event_id":
        if (
            event_ids_a is None
            or event_ids_b is None
            or len(event_ids_a) != len(a)
            or len(event_ids_b) != len(b)
        ):
            raise ValueError("Common event identifiers required for both sequences")
        if len(set(event_ids_a)) != len(a) or len(set(event_ids_b)) != len(b):
            raise ValueError("Event identifiers must be unique per sequence")
        lookup = dict(zip(event_ids_b, b, strict=True))
        pairs = [
            (value, lookup[event])
            for event, value in zip(event_ids_a, a, strict=True)
            if event in lookup
        ]
    else:
        if any(y < x for series in (a, b) for x, y in zip(series, series[1:], strict=False)):
            raise ValueError("Timestamp matching requires nondecreasing sequences")
        tolerance = tolerance_ns if strategy == "tolerance" else 0
        i, j = 0, 0
        while i < len(a) and j < len(b):
            difference = b[j] - a[i]
            if abs(difference) <= tolerance:
                pairs.append((a[i], b[j]))
                i, j = i + 1, j + 1
            elif difference < 0:
                j += 1
            else:
                i += 1
    differences = [y - x for x, y in pairs]
    return Result(
        measurement_kind="calculated",
        status="valid" if pairs else "partial",
        source=Source(collector="topic_comparison"),
        data=json_data(
            {
                "measurement_kind": "calculated",
                "strategy": strategy,
                "matching_algorithm": "unique common event ID"
                if strategy == "event_id"
                else "ordered earliest feasible one-to-one matching",
                "sign_convention": "timestamp B minus timestamp A in target domain",
                "tolerance_ns": tolerance_ns if strategy == "tolerance" else 0,
                "paired_count": len(pairs),
                "sample_count_a": len(a),
                "sample_count_b": len(b),
                "match_fraction_a": len(pairs) / len(a) if a else None,
                "match_fraction_b": len(pairs) / len(b) if b else None,
                "unmatched_a": len(a) - len(pairs),
                "unmatched_b": len(b) - len(pairs),
                "difference_statistics": summarize(
                    differences, object="paired timestamp B minus A"
                ).model_dump(mode="json"),
                "absolute_difference_statistics": summarize(
                    [abs(x) for x in differences], object="absolute paired timestamp difference"
                ).model_dump(mode="json"),
            }
        ),
        warnings=[
            "Header alignment does not establish exposure or physical sample alignment.",
            "Tolerance matching includes sampling phase/rate effects and does not estimate physical clock offset.",
        ],
    )
