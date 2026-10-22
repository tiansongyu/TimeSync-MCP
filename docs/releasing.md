# 发布准备

源仓库为 https://github.com/tiansongyu/TimeSync-MCP 。本版本尚未打 Git tag 或上传 PyPI；源码推送不等于已发布包索引版本。

1. 核对 LICENSE/NOTICE、uv.lock、第三方清单、支持平台与 validation.md。
2. 按 README 运行完整 lint/type/tests/build；分别记录核心和 Bridge 的 Python/ROS 版本。Jazzy/ARM64/硬件结果不得从 Humble 合成测试推断。
3. 运行 `uv run python scripts/export_tool_reference.py` 更新实际工具 Schema，并检查 diff。
4. 运行 `env -u PYTHONPATH uv run python scripts/dependency_notices.py` 更新当前锁定环境的依赖许可证元数据。
5. 用干净虚拟环境安装两个 wheel，验证核心 doctor/stdio 和 Bridge 的发行版 Python 启动。
6. 审查发行包内的源码、测试、文档和许可证；不得包含本机配置、原始日志、Token 或 .venv。
7. 在实际托管服务按维护者既有流程创建 release；如果发布包索引，先确认名称可用性与凭据授权。

核心分发名 `timesync-mcp`，Bridge 分发名 `timesync-ros-bridge`。二者暂同为 0.1.0，核心输出 Schema 1.0，IPC 协议 1；版本变化应分别说明兼容性。
