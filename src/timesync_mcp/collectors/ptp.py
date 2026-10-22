import re
import tempfile
from decimal import Decimal, InvalidOperation

from ..models.measurement import Measurement, Result, Source, json_data
from ..security.command_runner import Runner
from ..security.validation import interface_name
from .base import command_result

IDS = ("TIME_STATUS_NP", "PORT_DATA_SET", "CURRENT_DATA_SET", "PARENT_DATA_SET", "DEFAULT_DATA_SET")


def parse_pmc(text: str, management_id: str) -> Result:
    result = Result(source=Source(collector="linuxptp"))
    if re.search(r"NOT_SUPPORTED|NOT_SUPPORTED_MANAGEMENT_ID|WRONG_VALUE|NO_SUCH_ID", text):
        result.status, result.error = "unsupported", f"Unsupported management ID: {management_id}"
        return result
    if "MANAGEMENT_ERROR_STATUS" in text:
        result.status, result.error = (
            "invalid",
            "PTP management error response; specific cause not reported by pmc",
        )
        return result
    records: list[dict[str, str]] = []
    current: dict[str, str] | None = None
    for line in text.splitlines():
        if re.search(r"\bRESPONSE\s+MANAGEMENT\s+" + management_id + r"\b", line):
            current = {"responding_port": line.strip().split()[0]}
            records.append(current)
        elif current is not None:
            match = re.fullmatch(r"\s*([A-Za-z][A-Za-z0-9_.]*)\s+(\S+)\s*", line)
            if match:
                current[match[1]] = match[2]
    if not records or not any(len(r) > 1 for r in records):
        result.status, result.error = (
            "unavailable",
            f"No usable {management_id} response; PTP daemon unreachable, wrong domain, or ID unsupported",
        )
        return result
    result.data = json_data({"management_id": management_id, "records": records})
    try:
        for record in records:
            for field, metric in [
                ("master_offset", "ptp_master_offset"),
                ("offsetFromMaster", "ptp_offset_from_master"),
                ("meanPathDelay", "ptp_mean_path_delay"),
            ]:
                if field not in record:
                    continue
                value = Decimal(record[field])
                if not value.is_finite() or abs(value) >= 2**63:
                    raise ValueError("Invalid PTP nanoseconds")
                result.measurements.append(
                    Measurement(
                        metric=metric,
                        value=round(value),
                        unit="ns",
                        clock_domain="ptp:local",
                        reference_domain="ptp:master",
                        measurement_kind="estimated",
                        source=result.source,
                        evidence=[f"{management_id}:{record['responding_port']}:{field}"],
                        sign_convention="local clock minus master (positive means local ahead)"
                        if field != "meanPathDelay"
                        else "estimated one-way mean path delay",
                    )
                )
    except (ValueError, InvalidOperation):
        result.status, result.error = "invalid", "Malformed PTP numeric field"
        result.measurements = []
    return result


class PTPCollector:
    def __init__(self, runner: Runner, socket: str) -> None:
        self.runner, self.socket = runner, socket

    async def status(self, interface: str, domain: int = 0) -> Result:
        interface_name(interface)
        if not 0 <= domain <= 127:
            raise ValueError("Invalid PTP domain")
        results: list[Result] = []
        with tempfile.TemporaryDirectory(prefix="timesync-pmc-") as directory:
            for management_id in IDS:
                output = await self.runner.run(
                    "pmc",
                    "-u",
                    "-b",
                    "0",
                    "-d",
                    str(domain),
                    "-s",
                    self.socket,
                    "-i",
                    directory + "/client",
                    "GET " + management_id,
                )
                if output.status != "valid":
                    error = command_result(output, "linuxptp")
                    error.warnings.append(
                        "PTP socket unavailable or daemon unreachable; check permissions. No daemon was started."
                    )
                    return error
                parsed = parse_pmc(output.stdout, management_id)
                parsed.source.command = list(output.argv[:9]) + [
                    "<private-client-socket>",
                    output.argv[-1],
                ]
                results.append(parsed)
        usable = [r for r in results if r.status == "valid"]
        result = Result(
            status="valid" if len(usable) == len(IDS) else "partial" if usable else "unavailable",
            source=Source(collector="linuxptp", interface=interface, path=self.socket),
            data=json_data(
                {
                    "requested_domain": domain,
                    "requested_interface": interface,
                    "interface_association_verified": False,
                    "datasets": [r.model_dump(mode="json") for r in results],
                }
            ),
            measurements=[m for r in results for m in r.measurements],
            warnings=[
                "UDS queries address a daemon, not a network interface. Verify portIdentity/interface association before attributing offsets.",
                "A single offset observation does not establish sustained synchronization.",
            ],
        )
        if not usable:
            result.error = "PTP daemon unreachable, socket unavailable, domain mismatch, or unsupported management IDs"
        return result
