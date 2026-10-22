"""Versioned, provenance-bearing output shared by all collectors and tools."""

from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, JsonValue, model_validator

Status = Literal[
    "valid", "partial", "unavailable", "unsupported", "invalid", "timeout", "permission_denied"
]
Kind = Literal["observed", "calculated", "estimated", "inferred"]


def utc_now() -> datetime:
    return datetime.now(UTC)


class Model(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class Source(Model):
    collector: str
    command: list[str] | None = None
    interface: str | None = None
    path: str | None = None
    synthetic: bool = False


class Measurement(Model):
    schema_version: Literal["1.0"] = "1.0"
    metric: str
    value: int | float | str | bool | None = None
    unit: str
    clock_domain: str | None = None
    reference_domain: str | None = None
    measurement_kind: Kind = "observed"
    observed_at_utc: datetime = Field(default_factory=utc_now)
    sample_count: int = Field(default=1, ge=0)
    uncertainty_ns: int | None = Field(default=None, ge=0)
    status: Status = "valid"
    source: Source
    evidence: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    sign_convention: str | None = None


class Result(Model):
    measurement_kind: Kind = "observed"
    schema_version: Literal["1.0"] = "1.0"
    status: Status = "valid"
    observed_at_utc: datetime = Field(default_factory=utc_now)
    source: Source
    data: dict[str, JsonValue] = Field(default_factory=dict)
    measurements: list[Measurement] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    error: str | None = None


def json_data(value: Any) -> dict[str, JsonValue]:
    """Convert nested typed models to JSON-compatible data at module boundaries."""
    from pydantic import TypeAdapter

    adapter: TypeAdapter[dict[str, JsonValue]] = TypeAdapter(dict[str, JsonValue])
    return adapter.validate_python(adapter.dump_python(value, mode="json"))


class Int64Series(Model):
    timestamps_ns: list[int] = Field(min_length=1, max_length=100_000)

    @model_validator(mode="after")
    def int64(self) -> "Int64Series":
        if any(isinstance(v, bool) or not -(2**63) <= v < 2**63 for v in self.timestamps_ns):
            raise ValueError("timestamps must be signed int64 nanoseconds")
        return self
