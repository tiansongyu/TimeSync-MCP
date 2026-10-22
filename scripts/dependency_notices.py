"""Generate installed Python dependency inventory; versions remain in uv.lock."""

from importlib import metadata
from pathlib import Path


def main() -> None:
    lines = [
        "# Third-party dependency notices",
        "",
        "TimeSync MCP code is Apache-2.0. Dependencies retain their own licenses. This inventory is generated from the locked development environment; it includes test/build dependencies. It is not a relicensing of third-party code. Review upstream distribution license files when redistributing wheels or native components. System ethtool/LinuxPTP/Chrony/systemd/ROS are optional, separately installed programs and are not bundled.",
        "",
        "| Python distribution | Version | Declared license (metadata) |",
        "| --- | --- | --- |",
    ]
    for dist in sorted(metadata.distributions(), key=lambda d: (d.metadata["Name"] or "").lower()):
        name = dist.metadata["Name"]
        if name == "timesync-mcp":
            continue
        license = dist.metadata.get("License-Expression") or dist.metadata.get("License")
        if not license:
            license = (
                "; ".join(
                    c.split(" :: ")[-1]
                    for c in dist.metadata.get_all("Classifier", [])
                    if c.startswith("License ::")
                )
                or "See upstream distribution"
            )
        license = license.splitlines()[0][:200].replace("|", "/")
        lines.append(f"| {name} | {dist.version} | {license} |")
    lines += [
        "",
        "Core direct dependencies: mcp 2.3.0 (MIT), Pydantic (MIT), Typer (MIT). The standalone ROS bridge declares no pip runtime dependencies; rclpy and message packages are supplied by the ROS distribution under their upstream licenses.",
        "",
        "Official source references and separately installed system dependencies: [docs/research.md](docs/research.md). This project does not copy third-party source code into its own modules.",
    ]
    Path("THIRD_PARTY_NOTICES.md").write_text("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
