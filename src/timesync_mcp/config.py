import os
import tomllib
from pathlib import Path

from pydantic import Field, TypeAdapter, model_validator

from .models.clock import ClockGraph
from .models.measurement import Model


def default_socket() -> str:
    return f"/tmp/timesync-mcp-{os.getuid()}/bridge.sock"


class Settings(Model):
    bridge_socket: str = Field(default_factory=default_socket)
    command_timeout_s: float = Field(default=4, gt=0, le=15)
    command_output_bytes: int = Field(default=262_144, ge=1024, le=1_048_576)
    max_commands: int = Field(default=4, ge=1, le=8)
    max_samples: int = Field(default=20_000, ge=2, le=100_000)
    ptp_socket: str = "/var/run/ptp4l"
    ptp_offset_warning_ns: int = Field(default=100_000, gt=0)
    chrony_offset_warning_ns: int = Field(default=1_000_000, gt=0)
    graph: ClockGraph = Field(default_factory=ClockGraph)
    topic_clock_domains: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_topic_domains(self) -> "Settings":
        from .security.validation import Topic

        ids = {domain.id for domain in self.graph.domains}
        for topic, domain in self.topic_clock_domains.items():
            TypeAdapter(Topic).validate_python(topic)
            if domain not in ids:
                raise ValueError("Topic references unknown configured clock domain")
        return self

    @classmethod
    def load(cls, path: Path | None = None) -> "Settings":
        if path is None:
            return cls()
        with path.open("rb") as stream:
            return cls.model_validate(tomllib.load(stream))
