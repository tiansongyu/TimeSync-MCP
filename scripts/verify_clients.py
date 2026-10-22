"""Verify installed MCP client configuration without invoking an LLM.
Codex: adds the requested `timesync` entry only when absent. Claude/OpenCode use
an isolated temporary project. Never prints other configured servers/credentials.
"""

import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LAUNCH = ["uv", "run", "--directory", str(ROOT), "timesync-mcp", "serve"]


def run(args: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ)
    env.pop("PYTHONPATH", None)
    return subprocess.run(args, cwd=cwd, env=env, capture_output=True, text=True, timeout=60)


def main() -> None:
    codex = shutil.which("codex")
    if codex:
        version = run([codex, "--version"]).stdout.strip()
        present = run([codex, "mcp", "get", "timesync", "--json"])
        if present.returncode:
            added = run([codex, "mcp", "add", "timesync", "--", *LAUNCH])
            if added.returncode:
                raise RuntimeError("Codex registration failed")
        entry = json.loads(run([codex, "mcp", "get", "timesync", "--json"]).stdout)
        transport = entry.get("transport", {})
        assert transport.get("command") == LAUNCH[0] and transport.get("args") == LAUNCH[1:]
        print(version + ": actual add/get configuration verified")
    claude = shutil.which("claude") or "/tmp/timesync-client-verification/node_modules/.bin/claude"
    with tempfile.TemporaryDirectory(prefix="timesync-client-project-") as directory:
        cwd = Path(directory)
        if Path(claude).exists():
            version = run([claude, "--version"]).stdout.strip()
            assert (
                run(
                    [
                        claude,
                        "mcp",
                        "add",
                        "--scope",
                        "project",
                        "--transport",
                        "stdio",
                        "timesync",
                        "--",
                        *LAUNCH,
                    ],
                    cwd,
                ).returncode
                == 0
            )
            data = json.loads((cwd / ".mcp.json").read_text())
            assert data["mcpServers"]["timesync"]["command"] == "uv"
            status = run([claude, "mcp", "list"], cwd)
            lines = [
                line.strip()
                for line in (status.stdout + status.stderr).splitlines()
                if "timesync" in line.lower()
            ]
            print("Claude verification", status.returncode, lines)
            assert status.returncode == 0 and lines, "Claude MCP configuration check failed"
            print(
                version
                + ": configuration verified; "
                + (
                    "connected"
                    if any("connected" in line.lower() for line in lines)
                    else "client project approval required; connection unverified"
                )
            )
        opencode = shutil.which("opencode")
        if opencode:
            (cwd / "opencode.json").write_text(
                json.dumps(
                    {
                        "$schema": "https://opencode.ai/config.json",
                        "mcp": {
                            "timesync": {
                                "type": "local",
                                "command": LAUNCH,
                                "enabled": True,
                                "timeout": 40000,
                            }
                        },
                    }
                )
            )
            status = run([opencode, "mcp", "list"], cwd)
            assert status.returncode == 0 and "connected" in status.stdout.lower(), (
                "OpenCode connection failed"
            )
            print(
                "OpenCode "
                + run([opencode, "--version"]).stdout.strip()
                + ": project JSON/list connected"
            )


if __name__ == "__main__":
    main()
