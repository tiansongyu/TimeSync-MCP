# Changelog

User-visible changes are recorded here. Version numbers describe the software package; output schema and Bridge IPC versions are documented separately.

## Unreleased — 0.1.0

### Added

- Official MCP Python SDK v2 stdio server with 15 structured tools, four diagnostic prompts and a read-only rules resource.
- Linux sysfs/ethtool, LinuxPTP GET, Chrony CSV, systemd state and bounded journald collectors.
- Separate ROS-distribution-matched Python bridge with private Unix socket IPC, topic/QoS discovery, bounded sampling and ROS clock inspection.
- Clock-domain graph, explicit measured transformations, interval statistics, one-to-one timestamp matching and robust paired-event drift estimation.
- Evidence-backed rule findings and JSON/Markdown reports, including optional ROS topic observations.
- CLI doctor, client examples, Synthetic fixtures, MCP protocol tests, actual Humble DDS Synthetic integration tests and CI definitions.
- Chinese/English documentation, Apache-2.0 licensing, third-party notices and contribution/security templates.

### Validation limits

- Ubuntu 22.04/24.04 and ROS Humble/Jazzy CI passed software/Synthetic DDS validation; no physical timing accuracy is claimed.
- ARM64/Jetson, actual PHC/Grandmaster synchronization, physical exposure/sample timing and device-specific adapters remain hardware-unverified.
- GMSL/HTE, SOEM/IgH, rosbag2, multi-host aggregation and historical monitoring are future extensions.
- No automatic clock, network, service, robot parameter or motion changes are supported.
