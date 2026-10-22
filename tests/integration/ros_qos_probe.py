"""Actual ROS DDS negative-QoS experiment with Synthetic messages."""

import json
import time

import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, qos_check_compatible
from std_msgs.msg import String


def main() -> None:
    rclpy.init()
    node = Node("timesync_synthetic_qos_probe", enable_rosout=False)
    offered = QoSProfile(depth=10, reliability=ReliabilityPolicy.BEST_EFFORT)
    requested = QoSProfile(depth=10, reliability=ReliabilityPolicy.RELIABLE)
    received = []
    pub = node.create_publisher(String, "/timesync_test/qos_negative", offered)
    sub = node.create_subscription(
        String, "/timesync_test/qos_negative", lambda m: received.append(m.data), requested
    )
    try:
        end = time.monotonic() + 0.5
        while time.monotonic() < end:
            pub.publish(String(data="Synthetic"))
            rclpy.spin_once(node, timeout_sec=0.01)
        compatibility, reason = qos_check_compatible(offered, requested)
        print(
            json.dumps(
                {
                    "synthetic": True,
                    "compatibility": compatibility.name,
                    "reason": reason,
                    "received_count": len(received),
                }
            )
        )
    finally:
        node.destroy_subscription(sub)
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()
