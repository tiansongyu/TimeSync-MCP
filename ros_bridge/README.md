# TimeSync ROS Bridge

Standalone Python 3.10+ read-only ROS 2 Unix socket bridge. Requires the ROS distribution's rclpy, rosidl_runtime_py, rcl_interfaces and rosgraph_msgs, supplied by that ROS installation. No pip runtime dependencies; do not install MCP into Humble Python 3.10.

From the main checkout, source your ROS environment and run `/usr/bin/python3 ros_bridge/run.py`. To build the independent package, use `uv build ros_bridge`; the installed entry point is `timesync-ros-bridge --socket PATH`.

Socket parent must be private (0700), socket 0600, same UID. Methods: ping, list_topics, sample, inspect_clock. No publishing, parameter writes, shell commands, clock adjustment or robot control. See the main project's ROS integration and security documentation.

Apache-2.0, see LICENSE and NOTICE. ROS packages retain their own upstream licenses.
