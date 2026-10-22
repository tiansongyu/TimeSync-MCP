"""Synthetic shared-event experiment: 400 Hz, 20 ppm, 5 ms, seeded jitter.
This is numerical validation, not measured robot or hardware performance.
"""

import json
import random
from decimal import Decimal

from timesync_mcp.analysis.clock_domains import fit_clock


def main() -> None:
    random_source = random.Random(42)
    origin = 1_800_000_000_000_000_000
    a = [origin + i * 2_500_000 for i in range(4000)]
    b = [
        origin
        + 5_000_000
        + round(Decimal(t - origin) * Decimal("1.00002"))
        + random_source.randint(-100, 100)
        for t in a
    ]
    fit = fit_clock(
        a,
        b,
        source_domain="synthetic:a",
        target_domain="synthetic:b",
        correspondence_method="common_events",
        evidence=["Synthetic one-to-one generated event IDs"],
    )
    print(
        json.dumps(
            {
                "synthetic": True,
                "injected_offset_at_anchor_ns": 5_000_000,
                "injected_drift_ppm": 20,
                "estimated_offset_at_anchor_ns": fit.target_anchor_ns - fit.source_anchor_ns,
                "estimated_drift_ppm": float((fit.relative_rate - 1) * 1_000_000),
                "transformation": fit.model_dump(mode="json"),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
