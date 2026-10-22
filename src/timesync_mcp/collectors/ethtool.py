import re

from ..models.measurement import Result, Source, json_data
from ..security.command_runner import Runner
from ..security.validation import interface_name
from .base import command_result


def parse_capabilities(text: str, interface: str) -> Result:
    result = Result(source=Source(collector="ethtool", interface=interface))
    if "Time stamping parameters for" not in text:
        return result.model_copy(
            update={"status": "invalid", "error": "Unrecognized ethtool -T output"}
        )
    sections: dict[str, list[str]] = {"capabilities": [], "tx_modes": [], "rx_filters": []}
    section: str | None = None
    phc: int | None = None
    phc_reported = False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped == "Capabilities:":
            section = "capabilities"
        elif stripped == "Hardware Transmit Timestamp Modes:":
            section = "tx_modes"
        elif stripped == "Hardware Receive Filter Modes:":
            section = "rx_filters"
        elif stripped.startswith("PTP Hardware Clock:"):
            phc_reported = True
            value = stripped.split(":", 1)[1].strip()
            phc = int(value) if value.isdigit() else None
            section = None
        elif section and stripped:
            sections[section].append(stripped)
    hardware = any(x in sections["capabilities"] for x in ("hardware-transmit", "hardware-receive"))
    result.data = json_data(
        {
            **sections,
            "interface": interface,
            "hardware_timestamping": hardware,
            "phc_index": phc,
            "phc_reported": phc_reported,
            "synchronization_established": None,
        }
    )
    result.warnings = ["Hardware capabilities do not establish active PTP synchronization."]
    return result


class EthtoolCollector:
    def __init__(self, runner: Runner) -> None:
        self.runner = runner

    async def capabilities(self, interface: str) -> Result:
        interface_name(interface)
        output = await self.runner.run("ethtool", "-T", interface)
        if output.status != "valid":
            return command_result(output, "ethtool")
        result = parse_capabilities(output.stdout, interface)
        result.source.command = list(output.argv)
        return result

    async def driver(self, interface: str) -> str | None:
        output = await self.runner.run("ethtool", "-i", interface_name(interface))
        if output.status != "valid":
            return None
        match = re.search(r"^driver:\s*(.+)$", output.stdout, re.MULTILINE)
        return match[1] if match else None
