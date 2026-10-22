"""Async, bounded, same-UID Unix socket client. Does not import rclpy."""

import asyncio
import json
import os
import socket
import stat
import struct

from ..models.measurement import Result, Source

MAX_FRAME = 8_000_000


class BridgeClient:
    def __init__(self, path: str) -> None:
        self.path = path

    async def request(self, method: str, **params: object) -> Result:
        source = Source(collector="ros2_bridge")
        writer: asyncio.StreamWriter | None = None
        try:
            async with asyncio.timeout(float(str(params.get("duration_s", 0))) + 10):
                info = os.lstat(self.path)
                parent = os.stat(os.path.dirname(self.path))
                if (
                    not stat.S_ISSOCK(info.st_mode)
                    or info.st_uid != os.getuid()
                    or info.st_mode & 0o077
                    or parent.st_uid != os.getuid()
                    or parent.st_mode & 0o077
                ):
                    return Result(
                        status="permission_denied",
                        source=source,
                        error="Bridge socket and parent directory must be private and owned by current UID",
                    )
                reader, writer = await asyncio.open_unix_connection(self.path, limit=MAX_FRAME)
                sock = writer.get_extra_info("socket")
                uid = struct.unpack(
                    "3i", sock.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12)
                )[1]
                if uid != os.getuid():
                    raise PermissionError("Bridge peer UID mismatch")
                writer.write(
                    json.dumps(
                        {"version": 1, "method": method, "params": params}, allow_nan=False
                    ).encode()
                    + b"\n"
                )
                await writer.drain()
                raw = await reader.readline()
                if not raw or len(raw) > MAX_FRAME:
                    raise ValueError("Invalid bridge response frame")
                return Result.model_validate_json(raw)
        except TimeoutError:
            return Result(status="timeout", source=source, error="ROS Bridge deadline exceeded")
        except PermissionError:
            return Result(
                status="permission_denied", source=source, error="ROS Bridge permission denied"
            )
        except (OSError, ValueError) as exc:
            return Result(
                status="unavailable",
                source=source,
                error=f"ROS Bridge unavailable: {type(exc).__name__}",
            )
        finally:
            if writer:
                writer.close()
                await writer.wait_closed()
