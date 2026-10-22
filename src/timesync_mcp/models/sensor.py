from typing import Literal

from pydantic import Field

from .measurement import Model


class SensorDescription(Model):
    id: str
    kind: Literal["camera", "imu", "lidar", "ethercat", "unknown"]
    transport: str = "unknown"
    timestamp_event: str = "unknown"
    clock_domain: str | None = None
    vendor_evidence: list[str] = Field(default_factory=list)
    unknown_delays: list[str] = Field(default_factory=list)
