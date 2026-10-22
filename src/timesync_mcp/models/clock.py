from decimal import Decimal, localcontext
from enum import StrEnum
from typing import Literal

from pydantic import Field, JsonValue, model_validator

from .measurement import Model


class ClockType(StrEnum):
    SYSTEM_REALTIME = "SYSTEM_REALTIME"
    SYSTEM_MONOTONIC = "SYSTEM_MONOTONIC"
    SYSTEM_MONOTONIC_RAW = "SYSTEM_MONOTONIC_RAW"
    PTP_HARDWARE_CLOCK = "PTP_HARDWARE_CLOCK"
    PTP_GRANDMASTER = "PTP_GRANDMASTER"
    NTP_REFERENCE = "NTP_REFERENCE"
    ROS_TIME = "ROS_TIME"
    ROS_SIM_TIME = "ROS_SIM_TIME"
    DEVICE_HARDWARE_CLOCK = "DEVICE_HARDWARE_CLOCK"
    ETHERCAT_DC = "ETHERCAT_DC"
    UNKNOWN = "UNKNOWN"


class ClockDomain(Model):
    id: str = Field(min_length=1, max_length=128)
    name: str
    clock_type: ClockType = ClockType.UNKNOWN
    timescale: str = "unknown"
    origin: str = "unknown"
    host_id: str | None = None
    device_id: str | None = None
    is_monotonic: bool | None = None
    is_adjustable: bool | None = None
    sync_mechanism: str = "unknown"
    reference_domain_id: str | None = None
    metadata: dict[str, JsonValue] = Field(default_factory=dict)


class ClockTransformation(Model):
    source_domain: str
    target_domain: str
    relative_rate: Decimal = Field(gt=0)
    source_anchor_ns: int
    target_anchor_ns: int
    method: str
    evidence: list[str] = Field(min_length=1)
    kind: Literal["measured", "configuration_inference"]
    valid_from_ns: int
    valid_until_ns: int
    sample_count: int = Field(ge=1)
    residual_rms_ns: float | None = Field(default=None, ge=0)
    uncertainty_ns: int | None = Field(default=None, ge=0)
    hardware_verified: bool = False
    timescale: str = "unknown"

    @model_validator(mode="after")
    def bounds(self) -> "ClockTransformation":
        if self.valid_until_ns < self.valid_from_ns:
            raise ValueError("invalid transformation interval")
        return self

    def apply(self, timestamp_ns: int) -> int:
        if self.kind != "measured":
            raise ValueError("Cannot establish trusted mapping from configuration inference")
        if not self.valid_from_ns <= timestamp_ns <= self.valid_until_ns:
            raise ValueError("Timestamp outside mapping validity interval")
        with localcontext() as ctx:
            ctx.prec = 40
            return self.target_anchor_ns + round(
                self.relative_rate * Decimal(timestamp_ns - self.source_anchor_ns)
            )


class ClockGraph(Model):
    domains: list[ClockDomain] = Field(default_factory=list, max_length=128)
    transformations: list[ClockTransformation] = Field(default_factory=list, max_length=256)

    @model_validator(mode="after")
    def references(self) -> "ClockGraph":
        ids = {d.id for d in self.domains}
        if len(ids) != len(self.domains):
            raise ValueError("Clock domain IDs must be unique")
        for domain in self.domains:
            if domain.reference_domain_id and domain.reference_domain_id not in ids:
                raise ValueError("Unknown reference domain")
        for edge in self.transformations:
            if edge.source_domain not in ids or edge.target_domain not in ids:
                raise ValueError("Transformation references unknown clock domain")
        return self
