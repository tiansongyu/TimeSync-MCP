"""One worker owns all rclpy operations. Only timestamps/metadata enter IPC."""

import threading
import time
from typing import Any


class ROSBackend:
    def __init__(self) -> None:
        import rclpy
        from rclpy.node import Node

        rclpy.init()
        self.node = Node("timesync_readonly_bridge", enable_rosout=False)

    def close(self) -> None:
        import rclpy

        self.node.destroy_node()
        rclpy.shutdown()

    def spin(self, seconds: float = 0.02) -> None:
        import rclpy

        rclpy.spin_once(self.node, timeout_sec=seconds)

    def endpoint(self, item: Any) -> dict[str, Any]:
        return {
            "node_name": item.node_name,
            "node_namespace": item.node_namespace,
            "message_type": item.topic_type,
            "qos": {
                "reliability": item.qos_profile.reliability.name,
                "durability": item.qos_profile.durability.name,
                "history": item.qos_profile.history.name,
                "depth": item.qos_profile.depth,
            },
        }

    def topics(self) -> dict[str, Any]:
        from rosidl_runtime_py.utilities import get_message

        output = []
        for name, types in self.node.get_topic_names_and_types()[:512]:
            header: bool | None = None
            if len(types) == 1:
                try:
                    header = (
                        get_message(types[0]).get_fields_and_field_types().get("header")
                        == "std_msgs/Header"
                    )
                except (ImportError, AttributeError, ValueError):
                    pass
            publishers = self.node.get_publishers_info_by_topic(name)[:64]
            subscribers = self.node.get_subscriptions_info_by_topic(name)[:64]
            output.append(
                {
                    "name": name,
                    "types": types,
                    "publisher_count": self.node.count_publishers(name),
                    "subscriber_count": self.node.count_subscribers(name),
                    "has_header": header,
                    "publishers": [self.endpoint(p) for p in publishers],
                    "subscribers": [self.endpoint(p) for p in subscribers],
                }
            )
        return {
            "topics": output,
            "limits": {"topics": 512, "endpoints_per_topic": 64},
            "source": "rclpy DDS graph snapshot",
        }

    def sim_parameters(
        self, nodes: list[tuple[str, str]], cancel: threading.Event
    ) -> list[dict[str, Any]]:
        from rcl_interfaces.srv import GetParameters

        entries = []
        clients = []
        futures = []
        try:
            for name, namespace in sorted(set(nodes))[:32]:
                fqn = namespace.rstrip("/") + "/" + name
                client = self.node.create_client(GetParameters, fqn + "/get_parameters")
                clients.append(client)
                entry = {"node": fqn, "use_sim_time": None}
                entries.append(entry)
                if client.service_is_ready():
                    request = GetParameters.Request()
                    request.names = ["use_sim_time"]
                    futures.append((client.call_async(request), entry))
            deadline = time.monotonic() + 0.5
            while futures and time.monotonic() < deadline and not cancel.is_set():
                self.spin()
                for future, entry in list(futures):
                    if future.done():
                        response = future.result()
                        if response and response.values and response.values[0].type == 1:
                            entry["use_sim_time"] = response.values[0].bool_value
                        futures.remove((future, entry))
            return entries
        finally:
            for client in clients:
                self.node.destroy_client(client)

    def sample(
        self, topics: list[str], duration_s: float, max_samples: int, cancel: threading.Event
    ) -> dict[str, Any]:
        from rclpy.qos import DurabilityPolicy, QoSProfile, ReliabilityPolicy, qos_check_compatible
        from rosidl_runtime_py.utilities import get_message

        qos = QoSProfile(
            depth=100,
            reliability=ReliabilityPolicy.BEST_EFFORT,
            durability=DurabilityPolicy.VOLATILE,
        )
        graph = {item["name"]: item for item in self.topics()["topics"]}
        records: dict[str, Any] = {}
        subscriptions = []
        publishers = []
        try:
            for topic in topics:
                if topic not in graph:
                    raise ValueError("Topic does not exist: " + topic)
                info = graph[topic]
                if len(info["types"]) != 1:
                    raise ValueError("Topic has ambiguous message types: " + topic)
                msg_type = get_message(info["types"][0])
                record: dict[str, Any] = {
                    "topic_info": info,
                    "header_ns": [],
                    "arrival_monotonic_ns": [],
                    "received_count": 0,
                    "retained_count": 0,
                    "truncated": False,
                    "invalid_header_count": 0,
                    "qos_checks": [],
                    "clock_domain": "unknown",
                }
                records[topic] = record
                for endpoint in self.node.get_publishers_info_by_topic(topic)[:64]:
                    compatibility, reason = qos_check_compatible(endpoint.qos_profile, qos)
                    record["qos_checks"].append(
                        {"compatibility": compatibility.name, "reason": reason}
                    )
                    publishers.append((endpoint.node_name, endpoint.node_namespace))

                def callback(msg: Any, row: dict[str, Any] = record) -> None:
                    received = time.monotonic_ns()
                    row["received_count"] += 1
                    if row["retained_count"] >= max_samples:
                        row["truncated"] = True
                        return
                    row["retained_count"] += 1
                    row["arrival_monotonic_ns"].append(received)
                    if hasattr(msg, "header") and hasattr(msg.header, "stamp"):
                        sec, nsec = msg.header.stamp.sec, msg.header.stamp.nanosec
                        stamp = sec * 1_000_000_000 + nsec
                        if 0 <= nsec < 1_000_000_000 and -(2**63) <= stamp < 2**63:
                            row["header_ns"].append(stamp)
                        else:
                            row["invalid_header_count"] += 1

                subscriptions.append(self.node.create_subscription(msg_type, topic, callback, qos))
            start = time.monotonic_ns()
            deadline = time.monotonic() + duration_s
            while time.monotonic() < deadline and not cancel.is_set():
                self.spin(min(0.02, max(0.0, deadline - time.monotonic())))
            end = time.monotonic_ns()
            parameters = self.sim_parameters(publishers, cancel)
            return {
                "topics": records,
                "observation_duration_ns": end - start,
                "publisher_clock_parameters": parameters,
                "cancelled": cancel.is_set(),
                "subscription_qos": {
                    "reliability": "BEST_EFFORT",
                    "durability": "VOLATILE",
                    "depth": 100,
                },
                "limitations": [
                    "Callback arrival timestamps are CLOCK_MONOTONIC, not UTC.",
                    "Header clock source remains unknown even when use_sim_time=false.",
                    "No generic sequence ID: ROS 2 standard Header has no seq.",
                    "Received count is subscriber callbacks, not physical samples.",
                ],
            }
        finally:
            for subscription in subscriptions:
                self.node.destroy_subscription(subscription)

    def clock(self, duration_s: float, cancel: threading.Event) -> dict[str, Any]:
        from rclpy.qos import DurabilityPolicy, QoSProfile, ReliabilityPolicy
        from rosgraph_msgs.msg import Clock

        samples: list[int] = []
        arrivals: list[int] = []

        def callback(msg: Any) -> None:
            if len(samples) < 20_000:
                samples.append(msg.clock.sec * 1_000_000_000 + msg.clock.nanosec)
                arrivals.append(time.monotonic_ns())

        present = any(name == "/clock" for name, _ in self.node.get_topic_names_and_types())
        sub = self.node.create_subscription(
            Clock,
            "/clock",
            callback,
            QoSProfile(
                depth=1,
                reliability=ReliabilityPolicy.BEST_EFFORT,
                durability=DurabilityPolicy.VOLATILE,
            ),
        )
        try:
            deadline = time.monotonic() + duration_s
            while time.monotonic() < deadline and not cancel.is_set():
                self.spin(min(0.02, max(0.0, deadline - time.monotonic())))
            params = self.sim_parameters(self.node.get_node_names_and_namespaces(), cancel)
            deltas = [b - a for a, b in zip(samples, samples[1:], strict=False)]
            return {
                "clock_topic_present": present,
                "clock_samples": len(samples),
                "clock_advancing": any(x > 0 for x in deltas) if deltas else None,
                "backwards_count": sum(x < 0 for x in deltas),
                "large_forward_jump_count": sum(x > 1_000_000_000 for x in deltas),
                "forward_jump_threshold_ns": 1_000_000_000,
                "repeated_count": sum(x == 0 for x in deltas),
                "pause_suspected": bool(samples)
                and (
                    not any(x > 0 for x in deltas)
                    or time.monotonic_ns() - arrivals[-1] > 500_000_000
                ),
                "pause_threshold_ns": 500_000_000,
                "node_parameters": params,
                "limitations": [
                    "use_sim_time is per node; /clock presence does not prove use.",
                    "Low /clock rate and missing delivery can resemble pauses.",
                    "Forward changes over 1 s are heuristic jump candidates; accelerated simulation may be intentional.",
                    "Header-to-ROS-time relationship is unknown without a topic/source mapping.",
                    "Simulation time is never subtracted from UTC.",
                ],
            }
        finally:
            self.node.destroy_subscription(sub)
