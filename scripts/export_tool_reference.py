"""Export actual SDK-generated schemas and concise Chinese tool reference."""

import asyncio
import json
from pathlib import Path

from mcp import Client

from timesync_mcp.server import create_server

ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = {
    "list_network_interfaces": (
        {},
        "data.interfaces: name/mac/state/speed_mbps/driver/timestamp_capabilities",
    ),
    "get_timestamp_capabilities": (
        {"interface": "eth0"},
        "data.capabilities/tx_modes/rx_filters/hardware_timestamping/phc_index",
    ),
    "get_ptp_status": (
        {"interface": "eth0", "domain": 0},
        "data.datasets: 每个 GET 的状态和 records；measurements: ns offset/delay；interface_association_verified=false",
    ),
    "get_chrony_status": (
        {},
        "data.reference_id/reference_address/stratum/leap_status/synchronized/sources/sourcestats；measurements: ns/ppm",
    ),
    "inspect_time_services": (
        {},
        "data.services: 每个服务的 status/properties(Id,LoadState,ActiveState,SubState,ExecStart,NRestarts)",
    ),
    "get_time_sync_logs": (
        {
            "service": "ptp4l",
            "since": "2026-10-22T01:00:00Z",
            "until": "2026-10-22T02:00:00Z",
            "limit": 50,
        },
        "data.entries: observed_unix_us/message；service/since/until",
    ),
    "list_ros_topics": (
        {},
        "data.topics: name/types/publisher_count/subscriber_count/has_header/publishers/subscribers，含 QoS",
    ),
    "inspect_ros_topic": (
        {"topic": "/camera/image_raw", "duration_s": 5},
        "data.received_count/retained_count/truncated/topic_info/qos_checks/header_analysis/arrival_analysis；latency_ns=null",
    ),
    "analyze_ros_timestamps": (
        {"topic": "/imu/data", "duration_s": 10, "expected_rate_hz": 400},
        "Header 与 arrival 独立 analysis：interval_statistics、rate、backwards/duplicate、异常间隔数；received_rate_hz",
    ),
    "compare_ros_topics": (
        {
            "topic_a": "/camera/left/image_raw",
            "topic_b": "/camera/right/image_raw",
            "duration_s": 10,
            "strategy": "tolerance",
            "tolerance_ns": 100000,
        },
        "data.paired_count/match_fraction_a/b/unmatched_a/b；difference_statistics/absolute_difference_statistics；domain evidence",
    ),
    "inspect_ros_clock": (
        {"duration_s": 2},
        "data.clock_topic_present/clock_samples/clock_advancing/backwards_count/repeated_count/pause_suspected/node_parameters",
    ),
    "analyze_timestamp_series": (
        {"timestamps_ns": [0, 2500000, 5000000], "expected_rate_hz": 400, "synthetic": True},
        "data.interval_statistics/period_error_statistics/observed_span_rate_hz/zero/backwards/duplicate/异常间隔；可选 transformation/drift_ppm",
    ),
    "inspect_clock_domains": (
        {},
        "data.graph.domains/transformations/topic_clock_domains/provenance",
    ),
    "generate_time_sync_report": (
        {"interface": "eth0", "domain": 0, "format": "markdown"},
        "data.report: observations/findings/limitations；data.markdown（json 格式时 null）",
    ),
    "get_diagnostic_capabilities": (
        {},
        "data.python/platform/architecture/dependencies/executables/ros_bridge/hardware_validation/advanced_adapters/thresholds",
    ),
}


async def main() -> None:
    async with Client(create_server()) as client:
        tools = (await client.list_tools()).tools
        schemas = {t.name: {"input": t.input_schema, "output": t.output_schema} for t in tools}
        (ROOT / "docs/mcp-tools.schema.json").write_text(
            json.dumps(schemas, ensure_ascii=False, indent=2) + "\n"
        )
        lines = [
            "# MCP 工具参考",
            "",
            "本页由 `uv run python scripts/export_tool_reference.py` 从实际 SDK 工具定义生成。精确约束与完整输出定义见 [JSON Schema](mcp-tools.schema.json)。以下 JSON 是调用参数示例，不是实机输出。",
            "",
            "## 通用输出与错误语义",
            "",
            '每个正常协议结果为 Result：schema_version="1.0"、measurement_kind、status、observed_at_utc、source、data、measurements、warnings、error。source 指明 collector/command/interface/path/synthetic；measurement 指明 metric/value/unit、clock/reference domain、kind、sample_count、uncertainty_ns、evidence、sign_convention。字段未知保持 null，未返回项不补零。',
            "",
            "| status | 含义 |",
            "| --- | --- |",
            "| valid | 观测/计算成功，不等同于设备已同步 |",
            "| partial | 保留有效数据，但有缺项、无 Header、无配对或样本不足 |",
            "| unavailable | 可执行文件/daemon/Bridge/证据不可访问 |",
            "| unsupported | 明确证据表明管理 ID 或能力不支持 |",
            "| permission_denied | 普通用户权限不足 |",
            "| timeout | 命令或 IPC 超时 |",
            "| invalid | 内容解析失败、映射不可信、窗口/业务参数无效或超出资源上限 |",
            "",
            "JSON Schema 输入错误由 SDK 返回 `is_error=true`；可预期的缺设备/解析/映射错误返回 `is_error=false` 的结构化 Result，客户端必须进一步检查 status。未知内部异常被隔离，Server 保持运行。MCP 取消会传播；命令和 Bridge 负责释放资源。",
            "",
            "所有工具使用普通用户。Linux 命令通常默认 4 s、4 并发；日志最多 500 条/7 天；ROS 窗口 0.1–30 s，Bridge 需要安全的同 UID socket。五个 PTP GET 最坏顺序预算约 20 s；ROS IPC 预算 duration+10 s。建议客户端 tool timeout 至少 45 s。",
            "",
            "所有统计对象和单位在 Statistics 中：mean/median/population standard_deviation/variance/minimum/maximum/RMS/P95/P99/MAD/count；variance 单位为 object 单位的平方。小于 100 个间隔有小样本警告。",
            "",
        ]
        for tool in tools:
            example, output = EXAMPLES[tool.name]
            lines += [
                "## " + tool.name,
                "",
                tool.description or "",
                "",
                "**输入**",
                "",
                "| 参数 | Schema |",
                "| --- | --- |",
            ]
            properties = tool.input_schema.get("properties", {})
            if not properties:
                lines += ["| 无 | 空对象 `{}` |"]
            for name, prop in properties.items():
                lines += [
                    f"| `{name}` | `{json.dumps(prop, ensure_ascii=False, separators=(',', ':'))}` |"
                ]
            lines += [
                "",
                "**调用示例**",
                "",
                "```json",
                json.dumps(example, ensure_ascii=False, indent=2),
                "```",
                "",
                "**输出**：" + output + "。",
                "",
                "**失败与权限**：遵循上方通用语义；无对应工具/设备/Bridge 返回 unavailable，权限不足返回 permission_denied；解析或可信映射检查失败返回 invalid。普通用户运行，不自动修复系统。",
                "",
            ]
        lines += [
            "## Prompts 与 Resources",
            "",
            'Prompts：diagnose_ptp(interface="eth0")；diagnose_camera_imu_sync(camera_topic, imu_topic)；diagnose_ros_timestamp_jitter(topic)；diagnose_robot_time_sync()。只返回证据优先的编排提示，不替代底层工具。',
            "",
            "`timesync://rules` 暴露通用只读/证据/阈值政策，不暴露账户或环境变量。",
            "",
            "可用 `uv run python examples/call_tool.py get_diagnostic_capabilities` 通过实际 stdio 调用，结果打印为 JSON。",
        ]
        (ROOT / "docs/mcp-tools.md").write_text("\n".join(lines) + "\n")


if __name__ == "__main__":
    asyncio.run(main())
