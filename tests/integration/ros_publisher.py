"""Synthetic ROS DDS publisher; does not represent measured hardware performance."""

import argparse
import time

import rclpy
from rclpy.node import Node
from rclpy.parameter import Parameter
from rclpy.qos import QoSProfile, ReliabilityPolicy
from rosgraph_msgs.msg import Clock
from sensor_msgs.msg import Image, Imu
from std_msgs.msg import String


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sim-time", action="store_true")
    parser.add_argument("--jump", action="store_true")
    parser.add_argument("--drift-ppm", type=float, default=50)
    parser.add_argument("--offset-ns", type=int, default=5_000_000)
    parser.add_argument("--prefix", default="/timesync_test")
    args = parser.parse_args()
    rclpy.init()
    node = Node("timesync_synthetic_publisher")
    if args.sim_time:
        node.set_parameters([Parameter("use_sim_time", value=True)])
    qos = QoSProfile(depth=100, reliability=ReliabilityPolicy.BEST_EFFORT)
    imu_pub = node.create_publisher(Imu, args.prefix + "/imu", qos)
    left = node.create_publisher(Image, args.prefix + "/left", qos)
    right = node.create_publisher(Image, args.prefix + "/right", qos)
    plain = node.create_publisher(String, args.prefix + "/plain", qos)
    clock_pub = node.create_publisher(Clock, "/clock", 10) if args.sim_time else None
    start, base = time.monotonic_ns(), 1_000_000_000 if args.sim_time else time.time_ns()
    imu_count, camera_count = 0, 0
    try:
        while rclpy.ok():
            elapsed = time.monotonic_ns() - start
            if elapsed >= imu_count * 2_500_000:
                stamp = (
                    base
                    + round(imu_count * 2_500_000 * (1 + args.drift_ppm / 1e6))
                    + args.offset_ns
                )
                if args.jump and (imu_count // 200) % 2 == 1:
                    stamp -= 200_000_000
                msg = Imu()
                msg.header.stamp.sec, msg.header.stamp.nanosec = divmod(stamp, 1_000_000_000)
                msg.header.frame_id = "synthetic_imu"
                imu_pub.publish(msg)
                imu_count += 1
            if elapsed >= camera_count * (1_000_000_000 / 30):
                stamp = base + round(camera_count * (1_000_000_000 / 30))
                image = Image()
                image.header.stamp.sec, image.header.stamp.nanosec = divmod(stamp, 1_000_000_000)
                image.header.frame_id = "synthetic_camera"
                left.publish(image)
                right.publish(image)
                plain.publish(String(data="Synthetic"))
                if clock_pub:
                    clock = Clock()
                    clock.clock.sec, clock.clock.nanosec = divmod(stamp, 1_000_000_000)
                    clock_pub.publish(clock)
                camera_count += 1
            rclpy.spin_once(node, timeout_sec=0)
            time.sleep(0.0005)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()
