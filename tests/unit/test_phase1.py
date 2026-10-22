import pytest

from timesync_mcp.collectors.chrony import parse_sources, parse_tracking
from timesync_mcp.collectors.ethtool import parse_capabilities
from timesync_mcp.collectors.ptp import PTPCollector, parse_pmc
from timesync_mcp.models.measurement import Result
from timesync_mcp.security.command_runner import CommandOutput, CommandRunner, allowed

TRACKING = "7F010101,192.0.2.1,2,1792663200.0,0.000001,0.000002,0.000003,12.5,0.2,0.3,0.0004,0.0005,64.0,Normal"


def test_chrony():
    result = parse_tracking(TRACKING)
    assert result.status == "valid"
    assert result.measurements[0].value == 1000
    assert result.measurements[3].unit == "ppm"
    assert result.measurements[0].uncertainty_ns is None
    assert (
        parse_tracking(TRACKING.replace("Normal", "Not synchronised")).data["synchronized"] is False
    )
    assert parse_tracking("garbage").status == "invalid"
    assert parse_tracking(TRACKING.replace("12.5", "nan")).status == "invalid"
    assert parse_sources("^,*,192.0.2.1,2,6,377,4,0.000001,0.000002,0.000003")[0]["state"] == "*"


def test_ethtool():
    result = parse_capabilities(
        "Time stamping parameters for eth0:\nCapabilities:\n hardware-transmit\n hardware-receive\n hardware-raw-clock\nPTP Hardware Clock: 0\nHardware Transmit Timestamp Modes:\n off\n on\nHardware Receive Filter Modes:\n none\n all",
        "eth0",
    )
    assert result.data["phc_index"] == 0
    assert result.data["hardware_timestamping"] is True
    result = parse_capabilities(
        "Time stamping parameters for lo:\nCapabilities:\n software-transmit\nPTP Hardware Clock: none",
        "lo",
    )
    assert result.data["hardware_timestamping"] is False
    assert result.data["phc_index"] is None


def test_ptp():
    result = parse_pmc(
        " 001122.fffe.334455-0 seq 0 RESPONSE MANAGEMENT TIME_STATUS_NP\n master_offset -1250\n gmPresent true\n gmIdentity 001122.fffe.334455",
        "TIME_STATUS_NP",
    )
    assert result.measurements[0].value == -1250
    assert parse_pmc("nonsense", "TIME_STATUS_NP").status == "unavailable"
    assert parse_pmc("NOT_SUPPORTED", "TIME_STATUS_NP").status == "unsupported"
    assert (
        parse_pmc(
            " x seq 0 RESPONSE MANAGEMENT TIME_STATUS_NP\n master_offset abc", "TIME_STATUS_NP"
        ).status
        == "invalid"
    )


@pytest.mark.parametrize(
    "argv",
    [
        ("sh", "-c", "date"),
        ("chronyc", "makestep"),
        ("systemctl", "restart", "ptp4l"),
        ("ethtool", "-T", ";reboot"),
        ("journalctl", "-n", "100"),
    ],
)
def test_allowlist(argv):
    assert not allowed(argv)


async def test_missing_command():
    runner = CommandRunner()
    runner.executables["pmc"] = None
    output = await runner.run(
        "pmc",
        "-u",
        "-b",
        "0",
        "-d",
        "0",
        "-s",
        "/run/ptp4l",
        "-i",
        "/tmp/private/client",
        "GET TIME_STATUS_NP",
    )
    assert output.status == "unavailable"


@pytest.mark.parametrize("status", ["timeout", "permission_denied", "unavailable"])
async def test_ptp_failures(status):
    class Fake:
        async def run(self, *argv):
            return CommandOutput(argv, status, stderr="test unavailable evidence")

    result = await PTPCollector(Fake(), "/run/ptp4l").status("eth0")
    assert result.status == status
    Result.model_validate_json(result.model_dump_json())
