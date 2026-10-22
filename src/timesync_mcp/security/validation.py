import re
from typing import Annotated

from pydantic import Field

Interface = Annotated[str, Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,14}$")]
Topic = Annotated[
    str, Field(pattern=r"^/(?:[A-Za-z_][A-Za-z0-9_]*)(?:/[A-Za-z_][A-Za-z0-9_]*)*$", max_length=256)
]
Duration = Annotated[float, Field(ge=0.1, le=30, allow_inf_nan=False)]
Domain = Annotated[int, Field(ge=0, le=127, strict=True)]
Nanoseconds = Annotated[int, Field(ge=-(2**63), lt=2**63, strict=True)]
Series = Annotated[list[Nanoseconds], Field(min_length=1, max_length=100_000)]
SERVICES = ("ptp4l", "phc2sys", "chronyd", "chrony", "systemd-timesyncd")


def interface_name(value: str) -> str:
    if re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,14}", value) is None:
        raise ValueError("Invalid Linux interface name")
    return value


def service_name(value: str) -> str:
    name = value.removesuffix(".service")
    if name not in SERVICES:
        raise ValueError("Service not in time synchronization allowlist")
    return name + ".service"


def redact(value: str) -> str:
    value = re.sub(r"(?i)(bearer\s+)[A-Za-z0-9._~+/=-]+", r"\1[REDACTED]", value)
    value = re.sub(
        r"(?i)((?:token|password|secret|api[_-]?key)\s*[=:]\s*)\S+", r"\1[REDACTED]", value
    )
    value = re.sub(r"\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b", "[EMAIL]", value)
    value = re.sub(r"/home/[^/\s]+", "/home/[USER]", value)
    return "".join(c for c in value if c in "\n\t" or ord(c) >= 32)
