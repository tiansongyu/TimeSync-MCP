"""Optional data-only adapters. External plugins are loaded only by explicit application code."""

from typing import Protocol

from ..models.sensor import SensorDescription


class SensorAdapter(Protocol):
    def describe(self) -> SensorDescription: ...


TIMESTAMP_CAVEATS = {
    "camera": [
        "SOF/EOF, exposure start/midpoint/end, driver and arrival timestamps differ.",
        "FSYNC-to-exposure delay requires vendor evidence or measurement.",
    ],
    "imu": [
        "DRDY is data ready, not necessarily physical sample time.",
        "FSYNC direction/meaning is model-specific; FIFO and filter group delay may be unknown.",
    ],
    "lidar": [
        "Packet receive, point time, scan Header are different events.",
        "PTP/PPS support and per-point timestamps require device-specific evidence.",
    ],
    "ethercat": [
        "DC is independent of PTP unless a measured mapping is provided.",
        "SOEM/IgH adapters are not implemented in this release.",
    ],
}
