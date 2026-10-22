"""Chrony 4.2/4.5 CSV format, checked against official client.c."""

import asyncio
import csv
import math
from decimal import Decimal, InvalidOperation

from ..models.measurement import Measurement, Result, Source, json_data
from ..security.command_runner import Runner
from .base import command_result


def seconds_ns(text: str) -> int:
    value = Decimal(text)
    if not value.is_finite() or abs(value * 1_000_000_000) >= 2**63:
        raise ValueError("Non-finite or out-of-range chrony nanoseconds")
    return round(value * 1_000_000_000)


def finite(text: str) -> float:
    value = float(text)
    if not math.isfinite(value):
        raise ValueError("Non-finite chrony number")
    return value


def parse_tracking(text: str) -> Result:
    source = Source(collector="chrony", command=["chronyc", "-n", "-c", "tracking"])
    result = Result(source=source)
    try:
        rows = list(csv.reader(text.strip().splitlines()))
        if len(rows) != 1 or len(rows[0]) != 14:
            raise ValueError("Expected 14 tracking CSV fields (including reference address)")
        row = rows[0]
        stratum = int(row[2])
        if not 0 <= stratum <= 16 or row[13] not in (
            "Normal",
            "Insert second",
            "Delete second",
            "Not synchronised",
        ):
            raise ValueError("Invalid stratum or leap status")
        finite(row[3])
        result.data = {
            "reference_id": row[0],
            "reference_address": row[1],
            "stratum": stratum,
            "reference_time_unix_s": row[3],
            "leap_status": row[13],
            "synchronized": row[13] != "Not synchronised" and 0 < stratum < 16,
            "external_utc_reference_verified": False,
            "local_reference_mode": row[0].upper() == "7F7F0101",
        }
        metrics = [
            (4, "system_time", "ns"),
            (5, "last_offset", "ns"),
            (6, "rms_offset", "ns"),
            (7, "frequency", "ppm"),
            (8, "residual_frequency", "ppm"),
            (9, "skew", "ppm"),
            (10, "root_delay", "ns"),
            (11, "root_dispersion", "ns"),
            (12, "update_interval", "ns"),
        ]
        for index, metric, unit in metrics:
            val = seconds_ns(row[index]) if unit == "ns" else finite(row[index])
            result.measurements.append(
                Measurement(
                    metric="chrony_" + metric,
                    value=val,
                    unit=unit,
                    clock_domain="chrony:ntp_clock",
                    reference_domain="system:realtime" if index == 4 else "chrony:reference",
                    measurement_kind="estimated",
                    source=source,
                    sign_convention=(
                        "chronyd NTP clock minus system clock (positive means system slow)"
                        if index == 4
                        else "local NTP clock minus source (positive means local ahead)"
                        if index == 5
                        else None
                    ),
                )
            )
        result.warnings = [
            "chrony estimates are not hardware validation; synchronized status does not independently verify external UTC traceability.",
            "System time is chronyd virtual NTP clock minus CLOCK_REALTIME; Last/RMS offsets describe NTP clock relative to source.",
        ]
    except (ValueError, InvalidOperation, IndexError) as exc:
        result.status, result.error = "invalid", f"Invalid tracking CSV: {exc}"
        result.measurements = []
        result.data = {}
    return result


def parse_sources(text: str, stats: bool = False) -> list[dict[str, object]]:
    output: list[dict[str, object]] = []
    for row in csv.reader(text.strip().splitlines()):
        if not row:
            continue
        if stats:
            if len(row) != 8:
                raise ValueError("Expected 8 sourcestats CSV fields")
            output.append(
                {
                    "source": row[0],
                    "samples": int(row[1]),
                    "runs": int(row[2]),
                    "span_s": finite(row[3]),
                    "frequency_ppm": finite(row[4]),
                    "frequency_skew_ppm": finite(row[5]),
                    "offset_ns": seconds_ns(row[6]),
                    "stddev_ns": seconds_ns(row[7]),
                }
            )
        else:
            if (
                len(row) != 10
                or row[0] not in ("^", "=", "#")
                or row[1] not in ("*", "+", "-", "?", "x", "~")
            ):
                raise ValueError("Expected valid 10-field sources CSV")
            reach = int(row[5], 8)
            last_rx = int(row[6])
            if not 0 <= reach <= 0o377:
                raise ValueError("Invalid reach register")
            output.append(
                {
                    "mode": row[0],
                    "state": row[1],
                    "source": row[2],
                    "stratum": int(row[3]),
                    "poll_log2_seconds": int(row[4]),
                    "reach_octal": row[5],
                    "last_rx_s": None if last_rx == 4294967295 else last_rx,
                    "adjusted_offset_ns": seconds_ns(row[7]),
                    "measured_offset_ns": seconds_ns(row[8]),
                    "estimated_error_ns": seconds_ns(row[9]),
                }
            )
    return output


class ChronyCollector:
    def __init__(self, runner: Runner) -> None:
        self.runner = runner

    async def status(self) -> Result:
        outputs = await asyncio.gather(
            *(
                self.runner.run("chronyc", "-n", "-c", command)
                for command in ("tracking", "sources", "sourcestats")
            )
        )
        if outputs[0].status != "valid":
            return command_result(outputs[0], "chrony")
        result = parse_tracking(outputs[0].stdout)
        for output, key, stats in zip(
            outputs[1:], ("sources", "sourcestats"), (False, True), strict=True
        ):
            if output.status != "valid":
                if result.status == "valid":
                    result.status = "partial"
                result.warnings.append(f"{key}: {output.status}: {output.stderr}")
                continue
            try:
                result.data[key] = json_data({"rows": parse_sources(output.stdout, stats)})["rows"]
            except (ValueError, InvalidOperation) as exc:
                if result.status == "valid":
                    result.status = "partial"
                result.warnings.append(f"{key}: {exc}")
        return result
