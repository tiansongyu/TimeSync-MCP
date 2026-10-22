from pathlib import Path

from timesync_mcp.collectors.chrony import parse_sources, parse_tracking
from timesync_mcp.collectors.ethtool import parse_capabilities
from timesync_mcp.collectors.ptp import parse_pmc

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


def fixture(name):
    return (FIXTURES / name).read_text()


def test_documented_chrony_formats():
    for name in ["tracking_4_2.csv", "tracking_4_5_leap.csv"]:
        result = parse_tracking(fixture("chrony/" + name))
        assert result.status == "valid"
        assert result.data["synchronized"]
        assert result.measurements[0].reference_domain == "system:realtime"
        assert "positive means system slow" in result.measurements[0].sign_convention
    assert parse_tracking(fixture("chrony/unsynchronized.csv")).data["synchronized"] is False
    assert parse_sources(fixture("chrony/sources.csv"))[1]["last_rx_s"] is None
    assert parse_sources(fixture("chrony/sourcestats.csv"), True)[0]["samples"] == 16


def test_documented_ptp_formats():
    assert parse_pmc(fixture("ptp/normal.txt"), "TIME_STATUS_NP").measurements[0].value == -1250
    assert parse_pmc(fixture("ptp/current.txt"), "CURRENT_DATA_SET").measurements[0].unit == "ns"
    assert parse_pmc(fixture("ptp/error.txt"), "TIME_STATUS_NP").status == "invalid"
    parent = parse_pmc(fixture("ptp/parent.txt"), "PARENT_DATA_SET")
    assert parent.data["records"][0]["gm.ClockClass"] == "6"


def test_documented_ethtool():
    assert parse_capabilities(fixture("ethtool/phc.txt"), "eth0").data["hardware_timestamping"]
    assert not parse_capabilities(fixture("ethtool/software.txt"), "lo").data[
        "hardware_timestamping"
    ]
