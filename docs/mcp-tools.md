# MCP 工具参考

本页由 `uv run python scripts/export_tool_reference.py` 从实际 SDK 工具定义生成。精确约束与完整输出定义见 [JSON Schema](mcp-tools.schema.json)。以下 JSON 是调用参数示例，不是实机输出。

## 通用输出与错误语义

每个正常协议结果为 Result：schema_version="1.0"、measurement_kind、status、observed_at_utc、source、data、measurements、warnings、error。source 指明 collector/command/interface/path/synthetic；measurement 指明 metric/value/unit、clock/reference domain、kind、sample_count、uncertainty_ns、evidence、sign_convention。字段未知保持 null，未返回项不补零。

| status | 含义 |
| --- | --- |
| valid | 观测/计算成功，不等同于设备已同步 |
| partial | 保留有效数据，但有缺项、无 Header、无配对或样本不足 |
| unavailable | 可执行文件/daemon/Bridge/证据不可访问 |
| unsupported | 明确证据表明管理 ID 或能力不支持 |
| permission_denied | 普通用户权限不足 |
| timeout | 命令或 IPC 超时 |
| invalid | 内容解析失败、映射不可信、窗口/业务参数无效或超出资源上限 |

JSON Schema 输入错误由 SDK 返回 `is_error=true`；可预期的缺设备/解析/映射错误返回 `is_error=false` 的结构化 Result，客户端必须进一步检查 status。未知内部异常被隔离，Server 保持运行。MCP 取消会传播；命令和 Bridge 负责释放资源。

所有工具使用普通用户。Linux 命令通常默认 4 s、4 并发；日志最多 500 条/7 天；ROS 窗口 0.1–30 s，Bridge 需要安全的同 UID socket。五个 PTP GET 最坏顺序预算约 20 s；ROS IPC 预算 duration+10 s。建议客户端 tool timeout 至少 45 s。

所有统计对象和单位在 Statistics 中：mean/median/population standard_deviation/variance/minimum/maximum/RMS/P95/P99/MAD/count；variance 单位为 object 单位的平方。小于 100 个间隔有小样本警告。

## list_network_interfaces

List local Linux interfaces with sysfs state, link speed, driver and timestamp/PHC capabilities. Ordinary user; partial evidence retained.

**输入**

| 参数 | Schema |
| --- | --- |
| 无 | 空对象 `{}` |

**调用示例**

```json
{}
```

**输出**：data.interfaces: name/mac/state/speed_mbps/driver/timestamp_capabilities。

**失败与权限**：遵循上方通用语义；无对应工具/设备/Bridge 返回 unavailable，权限不足返回 permission_denied；解析或可信映射检查失败返回 invalid。普通用户运行，不自动修复系统。

## get_timestamp_capabilities

Read ethtool -T for one interface. Capabilities do not prove current PTP synchronization.

**输入**

| 参数 | Schema |
| --- | --- |
| `interface` | `{"pattern":"^[A-Za-z0-9][A-Za-z0-9_.-]{0,14}$","title":"Interface","type":"string"}` |

**调用示例**

```json
{
  "interface": "eth0"
}
```

**输出**：data.capabilities/tx_modes/rx_filters/hardware_timestamping/phc_index。

**失败与权限**：遵循上方通用语义；无对应工具/设备/Bridge 返回 unavailable，权限不足返回 permission_denied；解析或可信映射检查失败返回 invalid。普通用户运行，不自动修复系统。

## get_ptp_status

Query five LinuxPTP GET datasets over configured UDS. Domain 0..127; verify interface/port association. Never starts ptp4l.

**输入**

| 参数 | Schema |
| --- | --- |
| `interface` | `{"pattern":"^[A-Za-z0-9][A-Za-z0-9_.-]{0,14}$","title":"Interface","type":"string"}` |
| `domain` | `{"default":0,"maximum":127,"minimum":0,"title":"Domain","type":"integer"}` |

**调用示例**

```json
{
  "interface": "eth0",
  "domain": 0
}
```

**输出**：data.datasets: 每个 GET 的状态和 records；measurements: ns offset/delay；interface_association_verified=false。

**失败与权限**：遵循上方通用语义；无对应工具/设备/Bridge 返回 unavailable，权限不足返回 permission_denied；解析或可信映射检查失败返回 invalid。普通用户运行，不自动修复系统。

## get_chrony_status

Read chronyc CSV tracking, sources and sourcestats, reporting estimated offsets in ns and frequency in ppm.

**输入**

| 参数 | Schema |
| --- | --- |
| 无 | 空对象 `{}` |

**调用示例**

```json
{}
```

**输出**：data.reference_id/reference_address/stratum/leap_status/synchronized/sources/sourcestats；measurements: ns/ppm。

**失败与权限**：遵循上方通用语义；无对应工具/设备/Bridge 返回 unavailable，权限不足返回 permission_denied；解析或可信映射检查失败返回 invalid。普通用户运行，不自动修复系统。

## inspect_time_services

Read systemd states and ExecStart for allowlisted time services. Coexistence alone is not adjustment conflict.

**输入**

| 参数 | Schema |
| --- | --- |
| 无 | 空对象 `{}` |

**调用示例**

```json
{}
```

**输出**：data.services: 每个服务的 status/properties(Id,LoadState,ActiveState,SubState,ExecStart,NRestarts)。

**失败与权限**：遵循上方通用语义；无对应工具/设备/Bridge 返回 unavailable，权限不足返回 permission_denied；解析或可信映射检查失败返回 invalid。普通用户运行，不自动修复系统。

## get_time_sync_logs

Read bounded, redacted journald entries. since/until: timezone-aware ISO8601, at most 7 days; default last hour. Journal permission may restrict evidence.

**输入**

| 参数 | Schema |
| --- | --- |
| `service` | `{"enum":["ptp4l","phc2sys","chronyd","chrony","systemd-timesyncd"],"title":"Service","type":"string"}` |
| `since` | `{"anyOf":[{"type":"string"},{"type":"null"}],"default":null,"title":"Since"}` |
| `until` | `{"anyOf":[{"type":"string"},{"type":"null"}],"default":null,"title":"Until"}` |
| `limit` | `{"default":100,"maximum":500,"minimum":1,"title":"Limit","type":"integer"}` |

**调用示例**

```json
{
  "service": "ptp4l",
  "since": "2026-10-22T01:00:00Z",
  "until": "2026-10-22T02:00:00Z",
  "limit": 50
}
```

**输出**：data.entries: observed_unix_us/message；service/since/until。

**失败与权限**：遵循上方通用语义；无对应工具/设备/Bridge 返回 unavailable，权限不足返回 permission_denied；解析或可信映射检查失败返回 invalid。普通用户运行，不自动修复系统。

## get_diagnostic_capabilities

Report actual runtime dependencies, command availability, optional ROS Bridge and unsupported adapters.

**输入**

| 参数 | Schema |
| --- | --- |
| 无 | 空对象 `{}` |

**调用示例**

```json
{}
```

**输出**：data.python/platform/architecture/dependencies/executables/ros_bridge/hardware_validation/advanced_adapters/thresholds。

**失败与权限**：遵循上方通用语义；无对应工具/设备/Bridge 返回 unavailable，权限不足返回 permission_denied；解析或可信映射检查失败返回 invalid。普通用户运行，不自动修复系统。

## analyze_timestamp_series

Analyze int64 ns intervals, repeats/backwards/jumps. Optional paired events fit offset/rate only with explicit trusted correspondence evidence; user-supplied evidence is an assertion, not independent verification.

**输入**

| 参数 | Schema |
| --- | --- |
| `timestamps_ns` | `{"items":{"exclusiveMaximum":9223372036854775808,"minimum":-9223372036854775808,"type":"integer"},"maxItems":100000,"minItems":1,"title":"Timestamps Ns","type":"array"}` |
| `expected_rate_hz` | `{"anyOf":[{"exclusiveMinimum":0,"maximum":1000000000.0,"type":"number"},{"type":"null"}],"default":null,"title":"Expected Rate Hz"}` |
| `synthetic` | `{"default":false,"title":"Synthetic","type":"boolean"}` |
| `paired_timestamps_ns` | `{"anyOf":[{"items":{"exclusiveMaximum":9223372036854775808,"minimum":-9223372036854775808,"type":"integer"},"maxItems":100000,"minItems":1,"type":"array"},{"type":"null"}],"default":null,"title":"Paired Timestamps Ns"}` |
| `correspondence_method` | `{"anyOf":[{"enum":["common_events","hardware_verified","validated_mapping"],"type":"string"},{"type":"null"}],"default":null,"title":"Correspondence Method"}` |
| `correspondence_evidence` | `{"anyOf":[{"items":{"type":"string"},"maxItems":32,"type":"array"},{"type":"null"}],"default":null,"title":"Correspondence Evidence"}` |

**调用示例**

```json
{
  "timestamps_ns": [
    0,
    2500000,
    5000000
  ],
  "expected_rate_hz": 400,
  "synthetic": true
}
```

**输出**：data.interval_statistics/period_error_statistics/observed_span_rate_hz/zero/backwards/duplicate/异常间隔；可选 transformation/drift_ppm。

**失败与权限**：遵循上方通用语义；无对应工具/设备/Bridge 返回 unavailable，权限不足返回 permission_denied；解析或可信映射检查失败返回 invalid。普通用户运行，不自动修复系统。

## inspect_clock_domains

Return explicitly configured clock graph, directed mappings and validity/uncertainty. No relationship is inferred from sharing a host.

**输入**

| 参数 | Schema |
| --- | --- |
| 无 | 空对象 `{}` |

**调用示例**

```json
{}
```

**输出**：data.graph.domains/transformations/topic_clock_domains/provenance。

**失败与权限**：遵循上方通用语义；无对应工具/设备/Bridge 返回 unavailable，权限不足返回 permission_denied；解析或可信映射检查失败返回 invalid。普通用户运行，不自动修复系统。

## list_ros_topics

Discover ROS topics/types, endpoints, QoS and Header support through the optional distribution-matched Bridge.

**输入**

| 参数 | Schema |
| --- | --- |
| 无 | 空对象 `{}` |

**调用示例**

```json
{}
```

**输出**：data.topics: name/types/publisher_count/subscriber_count/has_header/publishers/subscribers，含 QoS。

**失败与权限**：遵循上方通用语义；无对应工具/设备/Bridge 返回 unavailable，权限不足返回 permission_denied；解析或可信映射检查失败返回 invalid。普通用户运行，不自动修复系统。

## inspect_ros_topic

Sample one topic for 0.1..30 seconds, bounded by configured sample cap; inspect Header and callback-arrival intervals separately.

**输入**

| 参数 | Schema |
| --- | --- |
| `topic` | `{"maxLength":256,"pattern":"^/(?:[A-Za-z_][A-Za-z0-9_]*)(?:/[A-Za-z_][A-Za-z0-9_]*)*$","title":"Topic","type":"string"}` |
| `duration_s` | `{"default":5,"maximum":30,"minimum":0.1,"title":"Duration S","type":"number"}` |

**调用示例**

```json
{
  "topic": "/camera/image_raw",
  "duration_s": 5
}
```

**输出**：data.received_count/retained_count/truncated/topic_info/qos_checks/header_analysis/arrival_analysis；latency_ns=null。

**失败与权限**：遵循上方通用语义；无对应工具/设备/Bridge 返回 unavailable，权限不足返回 permission_denied；解析或可信映射检查失败返回 invalid。普通用户运行，不自动修复系统。

## analyze_ros_timestamps

Analyze Header periodicity and monotonic callback arrival intervals separately. Does not infer DDS latency or physical sample jitter.

**输入**

| 参数 | Schema |
| --- | --- |
| `topic` | `{"maxLength":256,"pattern":"^/(?:[A-Za-z_][A-Za-z0-9_]*)(?:/[A-Za-z_][A-Za-z0-9_]*)*$","title":"Topic","type":"string"}` |
| `duration_s` | `{"default":10,"maximum":30,"minimum":0.1,"title":"Duration S","type":"number"}` |
| `expected_rate_hz` | `{"anyOf":[{"exclusiveMinimum":0,"maximum":1000000000.0,"type":"number"},{"type":"null"}],"default":null,"title":"Expected Rate Hz"}` |

**调用示例**

```json
{
  "topic": "/imu/data",
  "duration_s": 10,
  "expected_rate_hz": 400
}
```

**输出**：Header 与 arrival 独立 analysis：interval_statistics、rate、backwards/duplicate、异常间隔数；received_rate_hz。

**失败与权限**：遵循上方通用语义；无对应工具/设备/Bridge 返回 unavailable，权限不足返回 permission_denied；解析或可信映射检查失败返回 invalid。普通用户运行，不自动修复系统。

## compare_ros_topics

Simultaneously sample two topics, require explicit compatible clock domains, then one-to-one exact/tolerance match. Sampling phase is not physical clock offset.

**输入**

| 参数 | Schema |
| --- | --- |
| `topic_a` | `{"maxLength":256,"pattern":"^/(?:[A-Za-z_][A-Za-z0-9_]*)(?:/[A-Za-z_][A-Za-z0-9_]*)*$","title":"Topic A","type":"string"}` |
| `topic_b` | `{"maxLength":256,"pattern":"^/(?:[A-Za-z_][A-Za-z0-9_]*)(?:/[A-Za-z_][A-Za-z0-9_]*)*$","title":"Topic B","type":"string"}` |
| `duration_s` | `{"default":10,"maximum":30,"minimum":0.1,"title":"Duration S","type":"number"}` |
| `strategy` | `{"default":"exact","enum":["exact","tolerance"],"title":"Strategy","type":"string"}` |
| `tolerance_ns` | `{"default":0,"maximum":1000000000,"minimum":0,"title":"Tolerance Ns","type":"integer"}` |

**调用示例**

```json
{
  "topic_a": "/camera/left/image_raw",
  "topic_b": "/camera/right/image_raw",
  "duration_s": 10,
  "strategy": "tolerance",
  "tolerance_ns": 100000
}
```

**输出**：data.paired_count/match_fraction_a/b/unmatched_a/b；difference_statistics/absolute_difference_statistics；domain evidence。

**失败与权限**：遵循上方通用语义；无对应工具/设备/Bridge 返回 unavailable，权限不足返回 permission_denied；解析或可信映射检查失败返回 invalid。普通用户运行，不自动修复系统。

## inspect_ros_clock

Observe /clock progression/pause/backwards and query per-node use_sim_time read-only. Simulation time is never compared to UTC.

**输入**

| 参数 | Schema |
| --- | --- |
| `duration_s` | `{"default":2,"maximum":30,"minimum":0.1,"title":"Duration S","type":"number"}` |

**调用示例**

```json
{
  "duration_s": 2
}
```

**输出**：data.clock_topic_present/clock_samples/clock_advancing/backwards_count/repeated_count/pause_suspected/node_parameters。

**失败与权限**：遵循上方通用语义；无对应工具/设备/Bridge 返回 unavailable，权限不足返回 permission_denied；解析或可信映射检查失败返回 invalid。普通用户运行，不自动修复系统。

## generate_time_sync_report

Collect live Linux evidence and deterministic findings with configurable thresholds; return JSON or Markdown with JSON evidence. No files or system settings are changed.

**输入**

| 参数 | Schema |
| --- | --- |
| `interface` | `{"anyOf":[{"pattern":"^[A-Za-z0-9][A-Za-z0-9_.-]{0,14}$","type":"string"},{"type":"null"}],"default":null,"title":"Interface"}` |
| `domain` | `{"default":0,"maximum":127,"minimum":0,"title":"Domain","type":"integer"}` |
| `format` | `{"default":"json","enum":["json","markdown"],"title":"Format","type":"string"}` |
| `topics` | `{"anyOf":[{"items":{"maxLength":256,"pattern":"^/(?:[A-Za-z_][A-Za-z0-9_]*)(?:/[A-Za-z_][A-Za-z0-9_]*)*$","type":"string"},"maxItems":2,"minItems":1,"type":"array"},{"type":"null"}],"default":null,"title":"Topics"}` |
| `duration_s` | `{"default":5,"maximum":30,"minimum":0.1,"title":"Duration S","type":"number"}` |

**调用示例**

```json
{
  "interface": "eth0",
  "domain": 0,
  "format": "markdown"
}
```

**输出**：data.report: observations/findings/limitations；data.markdown（json 格式时 null）。

**失败与权限**：遵循上方通用语义；无对应工具/设备/Bridge 返回 unavailable，权限不足返回 permission_denied；解析或可信映射检查失败返回 invalid。普通用户运行，不自动修复系统。

## Prompts 与 Resources

Prompts：diagnose_ptp(interface="eth0")；diagnose_camera_imu_sync(camera_topic, imu_topic)；diagnose_ros_timestamp_jitter(topic)；diagnose_robot_time_sync()。只返回证据优先的编排提示，不替代底层工具。

`timesync://rules` 暴露通用只读/证据/阈值政策，不暴露账户或环境变量。

可用 `uv run python examples/call_tool.py get_diagnostic_capabilities` 通过实际 stdio 调用，结果打印为 JSON。
