"""Deterministic evidence-backed rules; no language model dependency."""

from ..config import Settings
from ..models.measurement import Result
from ..models.report import Finding, Report


def diagnose(observations: list[Result], settings: Settings) -> Report:
    findings: list[Finding] = []

    def add(
        rule: str,
        title: str,
        obs: Result,
        *,
        certainty: str = "CONFIRMED",
        severity: str = "warning",
        description: str,
        actions: list[str],
        limitations: list[str] | None = None,
    ) -> None:
        findings.append(
            Finding.model_validate(
                {
                    "rule_id": rule,
                    "severity": severity,
                    "certainty": certainty,
                    "title": title,
                    "description": description,
                    "required_evidence": [obs.source.collector]
                    + ([obs.source.path] if obs.source.path else []),
                    "observed_values": {
                        "status": obs.status,
                        "data": obs.data,
                        "measurements": [m.model_dump(mode="json") for m in obs.measurements],
                    },
                    "expected_conditions": [
                        "Valid observations in explicitly identified clock domains"
                    ],
                    "possible_causes": ["Review the directly observed condition and configuration"],
                    "recommended_actions": actions,
                    "limitations": limitations
                    or ["Snapshot evidence does not establish hardware failure."],
                }
            )
        )

    for obs in observations:
        collector = obs.source.collector
        if obs.status in ("unavailable", "permission_denied", "timeout", "unsupported", "invalid"):
            add(
                collector + ".unavailable",
                "Evidence source unavailable",
                obs,
                certainty="UNKNOWN",
                description=obs.error or obs.status,
                actions=[
                    "Check executable, read permissions, socket and daemon configuration manually."
                ],
            )
        if collector == "ethtool" and obs.data.get("hardware_timestamping") is False:
            add(
                "ptp.no_hardware_timestamping",
                "No hardware timestamp capabilities reported",
                obs,
                description="ethtool reports no hardware transmit/receive timestamp capabilities.",
                actions=[
                    "Confirm interface/driver and whether software timestamping meets your requirements."
                ],
            )
        if (
            collector == "ethtool"
            and obs.data.get("phc_reported")
            and obs.data.get("phc_index") is None
        ):
            add(
                "ptp.no_phc",
                "No PHC index reported",
                obs,
                description="The requested interface has no reported PHC.",
                actions=["Inspect the device and driver capabilities."],
            )
        if collector == "chrony" and obs.data.get("synchronized") is False:
            add(
                "chrony.unsynchronized",
                "Chrony reports unsynchronized state",
                obs,
                description="Stratum/leap state does not report normal synchronization.",
                actions=["Inspect configured sources and network reachability."],
            )
        for metric in obs.measurements:
            threshold = (
                settings.ptp_offset_warning_ns
                if metric.metric.startswith("ptp_")
                else settings.chrony_offset_warning_ns
            )
            if (
                metric.metric
                in ("ptp_master_offset", "ptp_offset_from_master", "chrony_system_time")
                and isinstance(metric.value, (int, float))
                and abs(metric.value) > threshold
            ):
                add(
                    "offset.exceeds_configured_threshold",
                    "Observed offset exceeds configured threshold",
                    obs,
                    certainty="SUSPECTED",
                    description=f"{metric.metric} exceeds engineering threshold {threshold} ns.",
                    actions=["Collect repeated observations and check reference quality."],
                    limitations=[
                        "One offset is insufficient to establish persistent synchronization failure.",
                        "Threshold is a configurable engineering default, not an industry standard.",
                    ],
                )
        if collector == "periodicity_analysis":
            for key, rule, title in [
                ("backwards_count", "ros.header_backwards", "Header timestamps move backwards"),
                ("zero_timestamps", "ros.header_zero", "Zero timestamps observed"),
            ]:
                value = obs.data.get(key)
                if isinstance(value, int) and value > 0:
                    add(
                        rule,
                        title,
                        obs,
                        description=f"{value} occurrences in supplied sequence.",
                        actions=["Verify timestamp source, simulation mode and driver behavior."],
                    )
            value = obs.data.get("potential_abnormal_intervals")
            if isinstance(value, int) and value > 0:
                add(
                    "ros.abnormal_intervals",
                    "Abnormal observed timestamp intervals",
                    obs,
                    certainty="SUSPECTED",
                    description=f"{value} intervals exceed the reported heuristic threshold.",
                    actions=[
                        "Inspect DDS delivery, sequence counters, driver and physical sampling evidence."
                    ],
                )
        if collector == "ros2_timestamp_analysis":
            info = obs.data.get("topic_info")
            if isinstance(info, dict) and info.get("has_header") is False:
                add(
                    "ros.header_missing",
                    "Message type has no standard Header",
                    obs,
                    description="Discovered message definition lacks std_msgs/Header.",
                    actions=["Use device-specific timestamp evidence or a suitable adapter."],
                    limitations=[
                        "Arrival intervals remain available but do not establish sample time."
                    ],
                )
            qos = obs.data.get("qos_checks")
            if isinstance(qos, list) and any(
                isinstance(q, dict) and q.get("compatibility") == "ERROR" for q in qos
            ):
                add(
                    "ros.qos_incompatible",
                    "Publisher and subscription QoS are incompatible",
                    obs,
                    description="rclpy qos_check_compatible reported ERROR.",
                    actions=[
                        "Review endpoint QoS in the existing ROS deployment; no parameters were changed."
                    ],
                )
            params = obs.data.get("publisher_clock_parameters")
            if isinstance(params, list):
                values = {
                    str(item.get("use_sim_time")) for item in params if isinstance(item, dict)
                }
                if {"True", "False"} <= values:
                    add(
                        "ros.mixed_sim_configuration",
                        "Sampled publishers use mixed simulation settings",
                        obs,
                        certainty="SUSPECTED",
                        description="Publisher parameters include both true and false use_sim_time.",
                        actions=[
                            "Verify each Header clock source before comparing absolute stamps."
                        ],
                        limitations=[
                            "use_sim_time does not independently establish Header clock provenance."
                        ],
                    )
        if collector == "linuxptp":
            datasets = obs.data.get("datasets", [])
            if isinstance(datasets, list):
                for dataset in datasets:
                    if not isinstance(dataset, dict):
                        continue
                    data = dataset.get("data")
                    if not isinstance(data, dict) or not isinstance(data.get("records"), list):
                        continue
                    records = data["records"]
                    assert isinstance(records, list)
                    for record in records:
                        if isinstance(record, dict) and record.get("gmPresent") in ("false", "0"):
                            add(
                                "ptp.no_grandmaster",
                                "Daemon reports no Grandmaster",
                                obs,
                                description="TIME_STATUS_NP gmPresent is false.",
                                actions=[
                                    "Inspect port state, domain and upstream Grandmaster visibility."
                                ],
                            )
    return Report(observations=observations, findings=findings)


def markdown(report: Report) -> str:
    lines = [
        "# TimeSync diagnostic report",
        "",
        "Read-only observations; no system settings changed.",
        "",
    ]
    for obs in report.observations:
        lines += [
            f"- Source `{obs.source.collector}`: **{obs.status}**, observed {obs.observed_at_utc.isoformat()}"
        ]
    for finding in report.findings:
        lines += [
            "",
            f"## {finding.rule_id}: {finding.title}",
            "",
            f"{finding.certainty} / {finding.severity}: {finding.description}",
            "",
            "Evidence: " + ", ".join(finding.required_evidence),
            "",
            *["- " + action for action in finding.recommended_actions],
            "",
            *["- Limitation: " + item for item in finding.limitations],
        ]
    lines += [
        "",
        "## Limitations",
        "",
        *["- " + text for text in report.limitations],
        "",
        "Full evidence values are available in the accompanying structured JSON report.",
    ]
    return "\n".join(lines)
