import asyncio
import os
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, validate
from mcp import Client, StdioServerParameters

from timesync_mcp.models.measurement import Result
from timesync_mcp.server import create_server

TOOLS = {
    "list_network_interfaces",
    "get_timestamp_capabilities",
    "get_ptp_status",
    "get_chrony_status",
    "inspect_time_services",
    "get_time_sync_logs",
    "list_ros_topics",
    "inspect_ros_topic",
    "analyze_ros_timestamps",
    "compare_ros_topics",
    "inspect_ros_clock",
    "analyze_timestamp_series",
    "inspect_clock_domains",
    "generate_time_sync_report",
    "get_diagnostic_capabilities",
}


async def check_client(client):
    tools = await client.list_tools()
    assert {t.name for t in tools.tools} == TOOLS
    for tool in tools.tools:
        Draft202012Validator.check_schema(tool.input_schema)
        Draft202012Validator.check_schema(tool.output_schema)
        assert tool.annotations.read_only_hint
    prompts = await client.list_prompts()
    assert len(prompts.prompts) == 4
    assert (await client.get_prompt("diagnose_ptp", {})).messages
    resources = await client.list_resources()
    assert resources.resources[0].uri == "timesync://rules"
    assert (await client.read_resource("timesync://rules")).contents
    result = await client.call_tool(
        "analyze_timestamp_series",
        {"timestamps_ns": [0, 2500000, 5000000], "expected_rate_hz": 400, "synthetic": True},
    )
    assert result.is_error is False
    schema = next(t.output_schema for t in tools.tools if t.name == "analyze_timestamp_series")
    validate(result.structured_content, schema)
    output = Result.model_validate(result.structured_content)
    assert output.data["observed_span_rate_hz"] == 400
    error = await client.call_tool("get_timestamp_capabilities", {"interface": "eth0;date"})
    assert error.is_error
    error = await client.call_tool("analyze_timestamp_series", {"timestamps_ns": [1.5, 2]})
    assert error.is_error
    refusal = await client.call_tool(
        "analyze_timestamp_series", {"timestamps_ns": [1, 2, 3], "paired_timestamps_ns": [2, 3, 4]}
    )
    assert refusal.structured_content["status"] == "invalid"
    absent = await client.call_tool("list_ros_topics", {})
    assert absent.structured_content["status"] in ("valid", "unavailable", "permission_denied")


async def test_in_memory():
    async with Client(create_server()) as client:
        await check_client(client)
        responses = await asyncio.gather(
            *(client.call_tool("get_timestamp_capabilities", {"interface": "lo"}) for _ in range(8))
        )
        assert all(not r.is_error for r in responses)


@pytest.mark.parametrize("mode", ["auto", "legacy"])
async def test_stdio_real_sdk(mode):
    # Real subprocess verifies stdout carries only valid protocol frames.
    env = {**os.environ}
    env.pop("PYTHONPATH", None)
    async with Client(
        StdioServerParameters(command="uv", args=["run", "timesync-mcp", "serve"], env=env),
        mode=mode,
    ) as client:
        await check_client(client)
        result = await client.call_tool("list_network_interfaces", {})
        assert result.structured_content["status"] == "valid"
        assert result.structured_content["data"]["interfaces"]
        chrony = await client.call_tool("get_chrony_status", {})
        assert chrony.structured_content["status"] in (
            "valid",
            "partial",
            "unavailable",
            "permission_denied",
            "timeout",
        )


async def test_every_tool_structured_output_with_documented_fixtures(tmp_path):
    from timesync_mcp.collectors.linux import LinuxCollector
    from timesync_mcp.config import Settings
    from timesync_mcp.security.command_runner import CommandOutput
    from timesync_mcp.tools.service import Diagnostics

    fixtures = Path(__file__).resolve().parents[1] / "fixtures"

    class FakeRunner:
        async def run(self, *argv):
            text = ""
            if argv[0] == "chronyc":
                name = {
                    "tracking": "tracking_4_2.csv",
                    "sources": "sources.csv",
                    "sourcestats": "sourcestats.csv",
                }[argv[-1]]
                text = (fixtures / "chrony" / name).read_text()
            elif argv[0] == "ethtool":
                text = (
                    (fixtures / "ethtool/phc.txt").read_text()
                    if argv[1] == "-T"
                    else "driver: synthetic_driver"
                )
            elif argv[0] == "pmc":
                dataset = argv[-1].split()[-1]
                text = f" 001122.fffe.334455-0 seq 0 RESPONSE MANAGEMENT {dataset}\n domainNumber 0\n gmPresent true\n portState SLAVE\n"
            elif argv[0] == "systemctl":
                text = (
                    "Id="
                    + argv[-1]
                    + "\nLoadState=loaded\nActiveState=active\nNRestarts=0\nExecStart=/synthetic\n"
                )
            elif argv[0] == "journalctl":
                text = (
                    '{"__REALTIME_TIMESTAMP":"1792663200000000","MESSAGE":"Synthetic token=SECRET"}'
                )
            return CommandOutput(argv, "valid", stdout=text)

    settings = Settings(bridge_socket=str(tmp_path / "absent.sock"))
    api = Diagnostics(settings, FakeRunner())
    net = tmp_path / "net/eth0"
    net.mkdir(parents=True)
    for key, value in {"address": "00:11:22:33:44:55", "operstate": "up", "speed": "1000"}.items():
        (net / key).write_text(value)
    api.linux = LinuxCollector(api.ethtool, net.parent)
    args = {
        "get_timestamp_capabilities": {"interface": "eth0"},
        "get_ptp_status": {"interface": "eth0"},
        "get_time_sync_logs": {"service": "ptp4l"},
        "inspect_ros_topic": {"topic": "/test", "duration_s": 0.1},
        "analyze_ros_timestamps": {"topic": "/test", "duration_s": 0.1},
        "compare_ros_topics": {"topic_a": "/a", "topic_b": "/b", "duration_s": 0.1},
        "inspect_ros_clock": {"duration_s": 0.1},
        "analyze_timestamp_series": {"timestamps_ns": [0, 2500000, 5000000]},
        "generate_time_sync_report": {"interface": "eth0", "format": "markdown"},
    }
    async with Client(create_server(settings, api)) as client:
        tools = (await client.list_tools()).tools
        for tool in tools:
            response = await client.call_tool(tool.name, args.get(tool.name, {}))
            assert not response.is_error, tool.name
            validate(response.structured_content, tool.output_schema)
            if tool.name == "get_time_sync_logs":
                assert "SECRET" not in str(response.structured_content)
            if tool.name == "generate_time_sync_report":
                assert response.structured_content["data"]["markdown"].startswith("# TimeSync")
