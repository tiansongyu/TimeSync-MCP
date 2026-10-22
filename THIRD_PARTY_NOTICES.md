# Third-party dependency notices

TimeSync MCP code is Apache-2.0. Dependencies retain their own licenses. This inventory is generated from the locked development environment; it includes test/build dependencies. It is not a relicensing of third-party code. Review upstream distribution license files when redistributing wheels or native components. System ethtool/LinuxPTP/Chrony/systemd/ROS are optional, separately installed programs and are not bundled.

| Python distribution | Version | Declared license (metadata) |
| --- | --- | --- |
| annotated-doc | 0.0.5 | MIT |
| annotated-types | 0.8.0 | MIT |
| anyio | 4.15.1 | MIT |
| attrs | 26.1.0 | MIT |
| build | 1.6.1 | MIT |
| cffi | 2.1.1 | MIT-0 |
| click | 8.5.0 | BSD-3-Clause |
| coverage | 7.16.2 | Apache-2.0 |
| cryptography | 50.0.2 | Apache-2.0 OR BSD-3-Clause |
| h11 | 0.16.0 | MIT |
| httpcore2 | 2.16.0 | BSD-3-Clause |
| httpx2 | 2.16.0 | BSD-3-Clause |
| idna | 3.20 | BSD-3-Clause |
| iniconfig | 2.3.1 | MIT |
| jsonschema | 4.26.0 | MIT |
| jsonschema-specifications | 2025.9.1 | MIT |
| librt | 0.16.0 | MIT |
| markdown-it-py | 4.2.0 | MIT License |
| mcp | 2.3.0 | MIT |
| mcp-types | 2.3.0 | MIT |
| mdurl | 0.1.2 | MIT License |
| mypy | 1.20.2 | MIT |
| mypy_extensions | 1.1.0 | MIT |
| opentelemetry-api | 1.45.1 | Apache-2.0 |
| packaging | 26.3 | Apache-2.0 OR BSD-2-Clause |
| pathspec | 1.1.1 | Mozilla Public License 2.0 (MPL 2.0) |
| pluggy | 1.7.0 | MIT |
| pycparser | 3.11 | BSD-3-Clause |
| pydantic | 2.14.1 | MIT |
| pydantic_core | 2.50.1 | MIT |
| Pygments | 2.21.0 | BSD-2-Clause |
| PyJWT | 2.15.1 | MIT |
| pyproject_hooks | 1.3.3 | MIT |
| pytest | 9.1.1 | MIT |
| pytest-asyncio | 1.4.0 | Apache-2.0 |
| pytest-cov | 7.1.0 | MIT |
| python-multipart | 0.0.32 | Apache-2.0 |
| referencing | 0.37.0 | MIT |
| rich | 15.0.0 | MIT |
| rpds-py | 2026.9.1 | MIT |
| ruff | 0.17.1 | MIT |
| shellingham | 1.5.4 | ISC License |
| sse-starlette | 3.5.0 | BSD-3-Clause |
| starlette | 1.9.0 | BSD-3-Clause |
| truststore | 0.10.5 | MIT |
| typer | 0.27.3 | MIT |
| types-jsonschema | 4.26.0.20261006 | Apache-2.0 |
| typing-inspection | 0.4.4 | MIT |
| typing_extensions | 4.16.0 | PSF-2.0 |
| uvicorn | 0.54.0 | BSD-3-Clause |

Core direct dependencies: mcp 2.3.0 (MIT), Pydantic (MIT), Typer (MIT). The standalone ROS bridge declares no pip runtime dependencies; rclpy and message packages are supplied by the ROS distribution under their upstream licenses.

Official source references and separately installed system dependencies: [docs/research.md](docs/research.md). This project does not copy third-party source code into its own modules.
