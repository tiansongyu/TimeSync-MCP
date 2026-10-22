import asyncio
import os

import pytest
from timesync_ros_bridge.bridge import BridgeServer, validate_request

from timesync_mcp.collectors.journal import normalize_window
from timesync_mcp.ros2.client import BridgeClient
from timesync_mcp.security.command_runner import CommandRunner
from timesync_mcp.security.validation import redact


def test_redaction_and_window():
    redacted = redact(
        "token=SECRET password:ABC Authorization: Bearer eyJ123.abc user@example.org /home/alice/file"
    )
    assert "SECRET" not in redacted and "ABC" not in redacted and "eyJ123" not in redacted
    assert "user@example.org" not in redacted and "alice" not in redacted
    assert normalize_window(None, None)[0].endswith("UTC")
    for since, until in [
        ("yesterday", None),
        ("2026-01-01T00:00:00", None),
        ("2026-01-01T00:00:00Z", "2026-02-01T00:00:00Z"),
    ]:
        with pytest.raises(ValueError):
            normalize_window(since, until)


async def test_subprocess_deadline_output_and_cancellation(tmp_path):
    script = tmp_path / "ethtool"
    script.write_text("#!/usr/bin/python3\nimport time\ntime.sleep(5)\n")
    script.chmod(0o700)
    runner = CommandRunner(timeout_s=0.05, output_bytes=1024, concurrency=1)
    runner.executables["ethtool"] = str(script)
    assert (await runner.run("ethtool", "-T", "eth0")).status == "timeout"
    script.write_text('#!/usr/bin/python3\nprint("X"*10000)\n')
    assert (await runner.run("ethtool", "-T", "eth0")).status == "invalid"
    script.write_text("#!/usr/bin/python3\nimport time\ntime.sleep(5)\n")
    runner.timeout_s = 10
    task = asyncio.create_task(runner.run("ethtool", "-T", "eth0"))
    await asyncio.sleep(0.05)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert not runner._slots.locked()


async def test_command_concurrency():
    class FakeRunner(CommandRunner):
        active = 0
        maximum = 0

        async def _execute(self, exe, argv):
            from timesync_mcp.security.command_runner import CommandOutput

            self.active += 1
            self.maximum = max(self.maximum, self.active)
            try:
                await asyncio.sleep(0.01)
                return CommandOutput(argv, "valid")
            finally:
                self.active -= 1

    runner = FakeRunner(concurrency=2)
    runner.executables["ethtool"] = "/fake"
    await asyncio.gather(*(runner.run("ethtool", "-T", "eth0") for _ in range(12)))
    assert runner.maximum == 2


@pytest.mark.parametrize(
    "method,params",
    [
        ("execute_shell", {}),
        ("sample", {"topics": ["/x"], "duration_s": float("nan"), "max_samples": 10}),
        ("sample", {"topics": ["/x;date"], "duration_s": 1, "max_samples": 10}),
        ("sample", {"topics": ["/x"], "duration_s": 1, "max_samples": 1_000_001}),
        ("ping", {"unknown": 1}),
    ],
)
def test_bridge_validation(method, params):
    with pytest.raises((ValueError, TypeError)):
        validate_request({"version": 1, "method": method, "params": params})


async def test_bridge_private_socket_and_protocol(tmp_path):
    import time

    class Fake:
        active = 0
        maximum = 0
        cancelled = False

        def spin(self, seconds=0.02):
            time.sleep(0.002)

        def topics(self):
            return {"topics": [], "synthetic": True}

        def sample(self, topics, duration_s, max_samples, cancel):
            self.active += 1
            self.maximum = max(self.maximum, self.active)
            try:
                end = time.monotonic() + duration_s
                while time.monotonic() < end and not cancel.is_set():
                    time.sleep(0.002)
                self.cancelled = cancel.is_set()
                return {"synthetic": True}
            finally:
                self.active -= 1

    fake = Fake()
    path = tmp_path / "bridge.sock"
    server = BridgeServer(fake, str(path))
    listener = await asyncio.start_unix_server(server.handle, path=str(path))
    path.chmod(0o600)
    client = BridgeClient(str(path))
    try:
        assert (await client.request("list_topics")).status == "valid"
        path.chmod(0o666)
        assert (await client.request("ping")).status == "permission_denied"
        path.chmod(0o600)
        assert (await client.request("execute_shell", command="date")).status == "invalid"
        results = await asyncio.gather(
            *(
                client.request("sample", topics=["/x"], duration_s=0.2, max_samples=10)
                for _ in range(5)
            )
        )
        assert any(r.status == "unavailable" for r in results)
        assert fake.maximum == 1
        task = asyncio.create_task(
            client.request("sample", topics=["/x"], duration_s=5, max_samples=10)
        )
        await asyncio.sleep(0.25)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        for _ in range(50):
            if server.active == 0:
                break
            await asyncio.sleep(0.01)
        assert fake.cancelled and server.active == 0
    finally:
        listener.close()
        await listener.wait_closed()
        await asyncio.gather(*server.handlers, return_exceptions=True)
        server.pool.shutdown(wait=True)


@pytest.mark.parametrize("stall_phase", ["drain", "close"])
async def test_bridge_slow_peer_cleanup_deadlines(tmp_path, monkeypatch, stall_phase):
    import struct

    import timesync_ros_bridge.bridge as bridge_module

    monkeypatch.setattr(bridge_module, "WRITE_TIMEOUT_S", 0.01)
    monkeypatch.setattr(bridge_module, "CLOSE_TIMEOUT_S", 0.01)

    class Peer:
        def getsockopt(self, *args):
            return struct.pack("3i", os.getpid(), os.getuid(), os.getgid())

    class Reader:
        async def readline(self):
            return b'{"version":1,"method":"ping","params":{}}\n'

    class Writer:
        transport = None
        closed = False
        aborted = False

        def __init__(self):
            self.transport = self

        def get_extra_info(self, name):
            return Peer()

        def write(self, data):
            assert b"protocol_version" in data

        async def drain(self):
            if stall_phase == "drain":
                await asyncio.Event().wait()

        def close(self):
            self.closed = True

        async def wait_closed(self):
            if stall_phase == "close":
                await asyncio.Event().wait()

        def abort(self):
            self.aborted = True

    server = BridgeServer(None, str(tmp_path / "bridge.sock"))
    writer = Writer()
    try:
        await asyncio.wait_for(server.handle(Reader(), writer), timeout=0.5)
        assert writer.closed and server.active == 0 and not server.handlers
        if stall_phase == "close":
            assert writer.aborted
    finally:
        server.pool.shutdown(wait=True)
