"""Only typed, read-only command families. No shell or arbitrary executable tool."""

import asyncio
import re
import shutil
from dataclasses import dataclass
from typing import Protocol

from ..models.measurement import Status
from .validation import SERVICES, redact


@dataclass(frozen=True)
class CommandOutput:
    argv: tuple[str, ...]
    status: Status
    stdout: str = ""
    stderr: str = ""
    returncode: int | None = None


class Runner(Protocol):
    async def run(self, *argv: str) -> CommandOutput: ...


def allowed(argv: tuple[str, ...]) -> bool:
    if not argv:
        return False
    exe, *args = argv
    if exe == "ethtool":
        return (
            len(args) == 2
            and args[0] in ("-T", "-i")
            and bool(re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,14}", args[1]))
        )
    if exe == "chronyc":
        return (
            len(args) == 3
            and args[:2] == ["-n", "-c"]
            and args[2] in ("tracking", "sources", "sourcestats")
        )
    if exe == "pmc":
        return (
            len(args) == 10
            and args[:3] == ["-u", "-b", "0"]
            and args[3] == "-d"
            and args[4].isdigit()
            and 0 <= int(args[4]) <= 127
            and args[5] == "-s"
            and args[6].startswith("/")
            and args[7] == "-i"
            and args[8].startswith("/")
            and args[9]
            in {
                "GET TIME_STATUS_NP",
                "GET PORT_DATA_SET",
                "GET CURRENT_DATA_SET",
                "GET PARENT_DATA_SET",
                "GET DEFAULT_DATA_SET",
            }
        )
    units = {s + ".service" for s in SERVICES}
    if exe == "systemctl":
        return (
            len(args) == 4
            and args[:2] == ["show", "--no-pager"]
            and args[2] == "--property=Id,LoadState,ActiveState,SubState,ExecStart,NRestarts"
            and args[3] in units
        )
    if exe == "journalctl":
        return (
            len(args) == 12
            and args[:4] == ["--no-pager", "--output=json", "-u", args[3]]
            and args[3] in units
            and args[4] == "--since"
            and args[6] == "--until"
            and args[8] == "-n"
            and args[9].isdigit()
            and 1 <= int(args[9]) <= 500
            and args[10:] == ["--quiet", "--utc"]
        )
    return False


class CommandRunner:
    def __init__(
        self, timeout_s: float = 4, output_bytes: int = 262_144, concurrency: int = 4
    ) -> None:
        self.timeout_s = timeout_s
        self.output_bytes = output_bytes
        self._slots = asyncio.Semaphore(concurrency)
        # Resolve executables once, before handling any untrusted tool inputs.
        self.executables = {
            name: shutil.which(name, path="/usr/sbin:/usr/bin:/sbin:/bin")
            for name in ("ethtool", "pmc", "chronyc", "systemctl", "journalctl")
        }

    async def run(self, *argv: str) -> CommandOutput:
        if not allowed(argv):
            raise ValueError("Command rejected by read-only allowlist")
        exe = self.executables[argv[0]]
        if exe is None:
            return CommandOutput(argv, "unavailable", stderr=f"{argv[0]} executable not found")
        try:
            async with asyncio.timeout(self.timeout_s):
                async with self._slots:
                    return await self._execute(exe, argv)
        except TimeoutError:
            return CommandOutput(argv, "timeout", stderr="Read-only command deadline exceeded")
        except ValueError:
            return CommandOutput(argv, "invalid", stderr="Command output limit exceeded")
        except PermissionError:
            return CommandOutput(argv, "permission_denied", stderr="Permission denied")
        except OSError as exc:
            return CommandOutput(argv, "unavailable", stderr=redact(str(exc)))

    async def _execute(self, exe: str, argv: tuple[str, ...]) -> CommandOutput:
        proc = await asyncio.create_subprocess_exec(
            exe,
            *argv[1:],
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env={
                "PATH": "/usr/sbin:/usr/bin:/sbin:/bin",
                "LC_ALL": "C",
                "LANG": "C",
                "HOME": "/nonexistent",
                "TZ": "UTC",
            },
        )
        used = 0

        async def bounded(stream: asyncio.StreamReader | None) -> bytes:
            nonlocal used
            assert stream is not None
            chunks = []
            while chunk := await stream.read(4096):
                used += len(chunk)
                if used > self.output_bytes:
                    raise ValueError("Command output limit exceeded")
                chunks.append(chunk)
            return b"".join(chunks)

        tasks = [
            asyncio.create_task(bounded(proc.stdout)),
            asyncio.create_task(bounded(proc.stderr)),
        ]
        try:
            out, err = await asyncio.gather(*tasks)
            code = await proc.wait()
        except BaseException:
            for task in tasks:
                task.cancel()
            if proc.returncode is None:
                proc.kill()
            await proc.wait()
            await asyncio.gather(*tasks, return_exceptions=True)
            raise
        stdout, stderr = (redact(x.decode("utf-8", errors="replace")) for x in (out, err))
        status: Status = "valid" if code == 0 else "unavailable"
        if "permission denied" in (stdout + stderr).lower():
            status = "permission_denied"
        return CommandOutput(argv, status, stdout, stderr, code)
