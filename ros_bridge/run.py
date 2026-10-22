"""Run with the ROS distribution's system Python, never with the MCP virtualenv."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))
from timesync_ros_bridge.bridge import main  # noqa: E402

main()
