import asyncio
from pathlib import Path

from ..models.measurement import Result, Source
from ..security.validation import interface_name
from .ethtool import EthtoolCollector


class LinuxCollector:
    def __init__(self, ethtool: EthtoolCollector, net_path: Path = Path("/sys/class/net")) -> None:
        self.ethtool, self.net_path = ethtool, net_path

    async def interfaces(self) -> Result:
        result = Result(source=Source(collector="linux_sysfs", path=str(self.net_path)))
        try:
            paths = sorted(self.net_path.iterdir())
        except OSError as exc:
            return result.model_copy(update={"status": "unavailable", "error": str(exc)})

        async def inspect(path: Path) -> dict[str, object]:
            interface_name(path.name)
            values: dict[str, object] = {"name": path.name}
            for filename, key in [
                ("address", "mac"),
                ("operstate", "state"),
                ("speed", "speed_mbps"),
            ]:
                try:
                    value = (path / filename).read_text().strip()
                    values[key] = int(value) if filename == "speed" and value.isdigit() else value
                except OSError:
                    values[key] = None
            caps, driver = await asyncio.gather(
                self.ethtool.capabilities(path.name), self.ethtool.driver(path.name)
            )
            values.update(driver=driver, timestamp_capabilities=caps.model_dump(mode="json"))
            return values

        from ..models.measurement import json_data

        result.data = json_data({"interfaces": await asyncio.gather(*(inspect(p) for p in paths))})
        return result
