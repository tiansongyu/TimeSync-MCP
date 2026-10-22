"""Actual DDS integration; the data source is explicitly Synthetic, not hardware."""

import asyncio
import os
import subprocess
from pathlib import Path

import pytest

from timesync_mcp.config import Settings
from timesync_mcp.models.clock import ClockDomain, ClockGraph, ClockType
from timesync_mcp.ros2.analysis import compare_topics, inspect_topic
from timesync_mcp.ros2.client import BridgeClient

ROOT = Path(__file__).resolve().parents[2]


def ros_env() -> dict[str, str]:
    env = os.environ.copy()
    ros = Path("/opt/ros") / env.get("ROS_DISTRO", "humble")
    if not ros.exists():
        pytest.fail("ROS required but missing") if env.get("TIMESYNC_REQUIRE_ROS") else pytest.skip(
            "ROS distribution not installed; actual DDS integration not verified"
        )
    paths = [str(p) for p in ros.glob("**/python3.*/dist-packages")]
    paths += [str(p) for p in ros.glob("**/python3.*/site-packages")]
    env["PYTHONPATH"] = os.pathsep.join(paths)
    env["LD_LIBRARY_PATH"] = str(ros / "lib") + ":" + env.get("LD_LIBRARY_PATH", "")
    env["ROS_DOMAIN_ID"] = "87"
    env["ROS_LOCALHOST_ONLY"] = "1"
    probe = subprocess.run(
        ["/usr/bin/python3", "-c", "import rclpy; from sensor_msgs.msg import Imu"],
        env=env,
        capture_output=True,
    )
    if probe.returncode:
        pytest.fail("ROS system Python required but unavailable") if env.get(
            "TIMESYNC_REQUIRE_ROS"
        ) else pytest.skip("ROS system Python unavailable: " + probe.stderr.decode()[-200:])
    return env


@pytest.mark.ros
@pytest.mark.parametrize("sim", [False, True])
async def test_real_dds(tmp_path, sim):
    env = ros_env()
    socket = str(tmp_path / "bridge.sock")
    with (
        (tmp_path / "bridge.log").open("w") as bridge_log,
        (tmp_path / "pub.log").open("w") as pub_log,
    ):
        publisher = subprocess.Popen(
            [
                "/usr/bin/python3",
                str(ROOT / "tests/integration/ros_publisher.py"),
                *(["--sim-time"] if sim else []),
                "--jump",
            ],
            env=env,
            stdout=pub_log,
            stderr=pub_log,
        )
        bridge = subprocess.Popen(
            ["/usr/bin/python3", str(ROOT / "ros_bridge/run.py"), "--socket", socket],
            env=env,
            stdout=bridge_log,
            stderr=bridge_log,
        )
        try:
            for _ in range(150):
                if Path(socket).exists():
                    break
                if bridge.poll() is not None:
                    pytest.fail((tmp_path / "bridge.log").read_text())
                await asyncio.sleep(0.05)
            client = BridgeClient(socket)
            await asyncio.sleep(1)
            ping = await client.request("ping")
            assert ping.status == "valid", ping.model_dump_json()
            assert ping.data["python"].startswith(("3.10", "3.12"))
            topics = await client.request("list_topics")
            assert any(
                t["name"] == "/timesync_test/imu" and t["has_header"] for t in topics.data["topics"]
            )
            raw = await client.request(
                "sample", topics=["/timesync_test/imu"], duration_s=1.5, max_samples=2000
            )
            assert raw.status == "valid", raw.model_dump_json()
            analyzed = inspect_topic(raw, "/timesync_test/imu", 400)
            assert analyzed.data["received_count"] > 100
            assert (
                analyzed.data["header_analysis"]["data"]["interval_statistics"]["median"]
                == 2_500_125
            )
            assert analyzed.data["header_analysis"]["data"]["backwards_count"] >= 1
            assert analyzed.data["latency_ns"] is None
            plain = await client.request(
                "sample", topics=["/timesync_test/plain"], duration_s=0.3, max_samples=50
            )
            assert inspect_topic(plain, "/timesync_test/plain").data["header_analysis"] is None
            pair = await client.request(
                "sample",
                topics=["/timesync_test/left", "/timesync_test/right"],
                duration_s=0.5,
                max_samples=100,
            )
            with pytest.raises(ValueError, match="clock domains"):
                compare_topics(
                    pair, "/timesync_test/left", "/timesync_test/right", Settings(), "exact", 0
                )
            domain = ClockDomain(
                id="synthetic",
                name="Synthetic shared publisher clock",
                clock_type=ClockType.ROS_SIM_TIME if sim else ClockType.ROS_TIME,
                timescale="simulation" if sim else "UTC",
            )
            settings = Settings(
                graph=ClockGraph(domains=[domain]),
                topic_clock_domains={
                    "/timesync_test/left": "synthetic",
                    "/timesync_test/right": "synthetic",
                },
            )
            compared = compare_topics(
                pair, "/timesync_test/left", "/timesync_test/right", settings, "exact", 0
            )
            assert compared.data["paired_count"] > 5
            assert compared.data["absolute_difference_statistics"]["maximum"] == 0
            clock = await client.request("inspect_clock", duration_s=0.5)
            if sim:
                assert clock.data["clock_advancing"] is True
                assert any(p["use_sim_time"] is True for p in clock.data["node_parameters"])
            bounded = await client.request(
                "sample", topics=["/timesync_test/imu"], duration_s=0.2, max_samples=10
            )
            assert bounded.data["topics"]["/timesync_test/imu"]["retained_count"] == 10
            assert bounded.data["topics"]["/timesync_test/imu"]["truncated"] is True
            missing = await client.request(
                "sample", topics=["/timesync_test/missing"], duration_s=0.1, max_samples=10
            )
            assert missing.status == "invalid"
        finally:
            for proc in (publisher, bridge):
                proc.terminate()
            for proc in (publisher, bridge):
                try:
                    proc.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait()


@pytest.mark.ros
def test_actual_qos_incompatibility():
    import json

    completed = subprocess.run(
        ["/usr/bin/python3", str(ROOT / "tests/integration/ros_qos_probe.py")],
        env=ros_env(),
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert completed.returncode == 0, completed.stderr
    output = json.loads(completed.stdout)
    assert output["synthetic"] and output["compatibility"] == "ERROR"
    assert output["received_count"] == 0
