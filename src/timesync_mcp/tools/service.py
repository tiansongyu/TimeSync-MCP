import asyncio
import importlib.metadata
import platform
import sys
from pathlib import Path

from ..collectors.chrony import ChronyCollector
from ..collectors.ethtool import EthtoolCollector
from ..collectors.journal import JournalCollector
from ..collectors.linux import LinuxCollector
from ..collectors.ptp import PTPCollector
from ..collectors.services import ServicesCollector
from ..config import Settings
from ..models.measurement import Result, Source, json_data
from ..security.command_runner import CommandRunner, Runner


class Diagnostics:
    def __init__(self, settings: Settings, runner: Runner | None = None) -> None:
        self.settings = settings
        self.runner = runner or CommandRunner(
            settings.command_timeout_s, settings.command_output_bytes, settings.max_commands
        )
        self.ethtool = EthtoolCollector(self.runner)
        self.linux = LinuxCollector(self.ethtool)
        self.ptp = PTPCollector(self.runner, settings.ptp_socket)
        self.chrony = ChronyCollector(self.runner)
        self.services = ServicesCollector(self.runner)
        self.journal = JournalCollector(self.runner)

    async def capabilities(self) -> Result:
        from ..ros2.client import BridgeClient

        runner = self.runner
        executables = runner.executables if isinstance(runner, CommandRunner) else {}
        bridge = await BridgeClient(self.settings.bridge_socket).request("ping")
        return Result(
            source=Source(collector="capabilities"),
            data=json_data(
                {
                    "python": sys.version.split()[0],
                    "platform": platform.system(),
                    "architecture": platform.machine(),
                    "read_only": True,
                    "transport": "stdio",
                    "dependencies": {
                        p: importlib.metadata.version(p) for p in ("mcp", "pydantic", "typer")
                    },
                    "executables": {k: v is not None for k, v in executables.items()},
                    "ros_bridge": bridge.model_dump(mode="json"),
                    "hardware_validation": "not performed",
                    "advanced_adapters": {
                        "gmsl": "unsupported",
                        "jetson_hte": "unsupported",
                        "ethercat_soem": "unsupported",
                        "ethercat_igh": "unsupported",
                        "rosbag2": "unsupported",
                    },
                    "thresholds": {
                        "ptp_offset_warning_ns": self.settings.ptp_offset_warning_ns,
                        "chrony_offset_warning_ns": self.settings.chrony_offset_warning_ns,
                        "origin": "configurable engineering defaults, not universal standards",
                    },
                }
            ),
        )

    async def doctor(self) -> Result:
        caps, interfaces, services = await asyncio.gather(
            self.capabilities(), self.linux.interfaces(), self.services.inspect()
        )
        return Result(
            source=Source(collector="doctor"),
            data=json_data(
                {
                    "capabilities": caps.model_dump(mode="json"),
                    "interfaces": interfaces.model_dump(mode="json"),
                    "services": services.model_dump(mode="json"),
                    "permission_policy": "ordinary user; inaccessible evidence remains unavailable",
                    "project_path": str(Path.cwd()),
                }
            ),
        )
