"""Version 1 JSON-lines IPC with permission, peer UID and workload bounds."""

import argparse
import asyncio
import concurrent.futures
import json
import math
import os
import re
import signal
import socket
import stat
import struct
import threading
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .backend import ROSBackend

MAX_REQUEST = 16_384
MAX_RESPONSE = 8_000_000
WRITE_TIMEOUT_S = 2.0
CLOSE_TIMEOUT_S = 1.0


@asynccontextmanager
async def deadline(seconds: float) -> AsyncIterator[None]:
    """Python 3.10-compatible cancellation deadline."""
    task = asyncio.current_task()
    assert task is not None
    expired = False

    def expire() -> None:
        nonlocal expired
        expired = True
        task.cancel()

    handle = asyncio.get_running_loop().call_later(seconds, expire)
    try:
        yield
    except asyncio.CancelledError:
        if expired:
            raise TimeoutError("Bridge deadline exceeded") from None
        raise
    finally:
        handle.cancel()


def result(
    data: dict[str, Any] | None = None, status: str = "valid", error: str | None = None
) -> dict[str, Any]:
    return {
        "schema_version": "1.0",
        "status": status,
        "observed_at_utc": datetime.now(timezone.utc).isoformat(),
        "source": {"collector": "ros2_bridge", "synthetic": False},
        "data": data or {},
        "measurements": [],
        "warnings": [],
        "error": error,
    }


def validate_request(request: Any) -> tuple[str, dict[str, Any]]:
    if (
        not isinstance(request, dict)
        or set(request) != {"version", "method", "params"}
        or request["version"] != 1
    ):
        raise ValueError("Expected IPC v1 request")
    method, params = request["method"], request["params"]
    if method not in ("ping", "list_topics", "sample", "inspect_clock") or not isinstance(
        params, dict
    ):
        raise ValueError("Unsupported read-only bridge method")
    allowed = {
        "ping": set(),
        "list_topics": set(),
        "sample": {"topics", "duration_s", "max_samples"},
        "inspect_clock": {"duration_s"},
    }[method]
    if set(params) != allowed:
        raise ValueError("Unexpected or missing method parameters")
    if "duration_s" in params:
        duration = params["duration_s"]
        if (
            isinstance(duration, bool)
            or not isinstance(duration, (int, float))
            or not math.isfinite(duration)
            or not 0.1 <= duration <= 30
        ):
            raise ValueError("duration_s must be finite and 0.1..30")
    if method == "sample":
        topics, count = params["topics"], params["max_samples"]
        if (
            not isinstance(topics, list)
            or not 1 <= len(topics) <= 2
            or len(set(topics)) != len(topics)
        ):
            raise ValueError("Need 1..2 unique topics")
        if any(
            not isinstance(t, str)
            or len(t) > 256
            or not re.fullmatch(r"/(?:[A-Za-z_][A-Za-z0-9_]*)(?:/[A-Za-z_][A-Za-z0-9_]*)*", t)
            for t in topics
        ):
            raise ValueError("Invalid topic name")
        if type(count) is not int or not 2 <= count <= 100_000:
            raise ValueError("max_samples must be 2..100000")
    return method, params


class BridgeServer:
    def __init__(self, backend: ROSBackend, path: str) -> None:
        self.backend, self.path = backend, Path(path)
        self.pool = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        self.active = 0
        self.handlers: set[asyncio.Task[Any]] = set()

    def dispatch(
        self, method: str, params: dict[str, Any], cancel: threading.Event
    ) -> dict[str, Any]:
        # Give DDS discovery a bounded opportunity to update before reading the graph.
        deadline = __import__("time").monotonic() + 0.2
        while __import__("time").monotonic() < deadline and not cancel.is_set():
            self.backend.spin()
        if method == "list_topics":
            return self.backend.topics()
        if method == "sample":
            return self.backend.sample(cancel=cancel, **params)
        return self.backend.clock(cancel=cancel, **params)

    async def handle(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        task = asyncio.current_task()
        assert task is not None
        self.handlers.add(task)
        admitted = False
        cancel = threading.Event()
        work: asyncio.Future[dict[str, Any]] | None = None
        disconnect: asyncio.Task[bytes] | None = None
        response = result(status="unavailable", error="Bridge workload limit reached")
        try:
            sock = writer.get_extra_info("socket")
            uid = struct.unpack("3i", sock.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12))[1]
            if uid != os.getuid():
                response = result(status="permission_denied", error="Peer UID mismatch")
            elif self.active < 2:
                self.active += 1
                admitted = True
                async with deadline(40):
                    raw = await reader.readline()
                    if len(raw) > MAX_REQUEST:
                        raise ValueError("Request too large")
                    method, params = validate_request(json.loads(raw))
                    if method == "ping":
                        response = result(
                            {
                                "protocol_version": 1,
                                "python": __import__("sys").version.split()[0],
                                "ros_distro": os.environ.get("ROS_DISTRO", "unknown"),
                            }
                        )
                    else:
                        work = asyncio.get_running_loop().run_in_executor(
                            self.pool, self.dispatch, method, params, cancel
                        )
                        disconnect = asyncio.create_task(reader.read(1))
                        pending_work: list[asyncio.Future[Any]] = [work, disconnect]
                        done, _ = await asyncio.wait(
                            pending_work, return_when=asyncio.FIRST_COMPLETED
                        )
                        if disconnect in done:
                            cancel.set()
                            # Wait for worker to release subscriptions before releasing workload slot.
                            await asyncio.shield(work)
                            return
                        response = result(await work)
        except (ValueError, TypeError, KeyError):
            response = result(status="invalid", error="Invalid bridge request or topic metadata")
        except TimeoutError:
            response = result(status="timeout", error="Bridge operation timed out")
        except Exception:
            response = result(
                status="unavailable", error="ROS evidence unavailable; verify topic type support"
            )
        finally:
            cancel.set()
            if disconnect:
                disconnect.cancel()
                await asyncio.gather(disconnect, return_exceptions=True)
            if work is not None and not work.done():
                try:
                    await asyncio.shield(work)
                except (Exception, asyncio.CancelledError):
                    pass
            try:
                payload = json.dumps(response, allow_nan=False).encode() + b"\n"
                if len(payload) > MAX_RESPONSE:
                    payload = (
                        json.dumps(
                            result(
                                status="invalid",
                                error="Response exceeds bounded frame size; reduce max_samples",
                            )
                        )
                        + "\n"
                    ).encode()
                writer.write(payload)
                await asyncio.wait_for(writer.drain(), timeout=WRITE_TIMEOUT_S)
            except (ConnectionError, TimeoutError):
                pass
            finally:
                writer.close()
                try:
                    await asyncio.wait_for(writer.wait_closed(), timeout=CLOSE_TIMEOUT_S)
                except (ConnectionError, TimeoutError):
                    writer.transport.abort()
                finally:
                    if admitted:
                        self.active -= 1
                    self.handlers.discard(task)

    async def run(self) -> None:
        self.path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        info = self.path.parent.lstat()
        if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
            raise PermissionError("Socket parent must be a private directory owned by current UID")
        # Never unlink an existing socket or overwrite someone else's endpoint.
        if self.path.exists() or self.path.is_symlink():
            raise FileExistsError("Socket path exists; inspect and remove stale socket manually")
        stop = asyncio.Event()
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(sig, stop.set)
        old_mask = os.umask(0o077)
        try:
            server = await asyncio.start_unix_server(
                self.handle, path=str(self.path), limit=MAX_REQUEST, backlog=8
            )
        finally:
            os.umask(old_mask)
        socket_inode = self.path.stat().st_ino
        try:
            async with server:
                await stop.wait()
        finally:
            for task in list(self.handlers):
                task.cancel()
            await asyncio.gather(*self.handlers, return_exceptions=True)
            self.pool.shutdown(wait=True, cancel_futures=True)
            if self.path.exists() and self.path.stat().st_ino == socket_inode:
                self.path.unlink()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Read-only TimeSync ROS 2 bridge (ROS system Python)"
    )
    parser.add_argument("--socket", default=f"/tmp/timesync-mcp-{os.getuid()}/bridge.sock")
    args = parser.parse_args()
    backend = ROSBackend()
    try:
        asyncio.run(BridgeServer(backend, args.socket).run())
    finally:
        backend.close()
