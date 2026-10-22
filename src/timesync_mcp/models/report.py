from typing import Literal

from pydantic import Field, JsonValue

from .measurement import Model, Result


class Finding(Model):
    rule_id: str
    severity: Literal["info", "warning", "error"]
    certainty: Literal["CONFIRMED", "SUSPECTED", "UNKNOWN", "NOT_APPLICABLE"]
    title: str
    description: str
    required_evidence: list[str]
    observed_values: dict[str, JsonValue]
    expected_conditions: list[str]
    possible_causes: list[str]
    recommended_actions: list[str]
    limitations: list[str]


class Report(Model):
    schema_version: Literal["1.0"] = "1.0"
    observations: list[Result]
    findings: list[Finding] = Field(default_factory=list)
    limitations: list[str] = Field(
        default_factory=lambda: [
            "Read-only snapshot; hardware exposure/sample alignment has not been verified.",
            "Unknown uncertainty is null, never zero; engineering thresholds are configurable.",
        ]
    )
