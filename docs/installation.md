# 安装与客户端配置

核心支持 Python 3.11+，默认 `.python-version` 为 3.12。Python、uv、系统诊断工具、ROS 都由用户安装；TimeSync 不修改它们的服务配置。

## 从源码安装

从公开仓库克隆：

```bash
git clone https://github.com/tiansongyu/TimeSync-MCP.git timesync-mcp
cd timesync-mcp
uv sync --locked
uv run timesync-mcp doctor
```

`doctor` 输出结构化 JSON：Python/架构、mcp/pydantic/typer 版本、pmc/chronyc/ethtool/systemctl/journalctl 是否存在、各网卡及 PHC 能力、Bridge 状态和权限限制。`status=unavailable` 代表相应数据无法获取，不代表机器人硬件损坏。

ROS-sourced 终端可能继承 Python 3.10 的 `PYTHONPATH`，尤其会污染 pytest 插件发现。核心应使用干净 shell，或：

```bash
env -u PYTHONPATH uv run timesync-mcp doctor
env -u PYTHONPATH uv run timesync-mcp serve
```

配置从显式 `--config PATH` 读取，不自动扫描工作目录。样例见 [robot_config.toml](../examples/robot_config.toml)。路径和阈值只影响诊断进程；不会写系统配置。

```bash
uv run timesync-mcp serve --config /absolute/path/to/robot_config.toml
```

## Wheel 安装

```bash
uv build
uv tool install ./dist/timesync_mcp-0.1.0-py3-none-any.whl
timesync-mcp doctor
```

ROS Bridge 可以直接从源码用发行版系统 Python 运行，无需把核心包装入 Python 3.10。独立 Bridge wheel 可用 `uv build ros_bridge` 构建，再由管理员既有 ROS 环境的安装流程部署；不要用 MCP 虚拟环境的 Python 启动 Humble rclpy。

## MCP 客户端

使用实际 checkout 的绝对路径，确保客户端进程的 PATH 中有 `uv`。可先独立运行 `doctor`。stdio 模式下 `serve` 等待协议消息是正常行为，不应输出欢迎文本。

```bash
codex mcp add timesync -- \
  uv run --directory /absolute/path/to/timesync-mcp timesync-mcp serve
codex mcp get timesync --json
```

官方配置依据：[OpenAI MCP 文档](https://learn.chatgpt.com/docs/extend/mcp)。已按 OpenAI Docs skill 核对文档和安装 CLI。配置样例见 [Codex TOML](../examples/codex/config.toml)，建议工具超时至少 45 s。

```bash
claude mcp add --scope project --transport stdio timesync -- \
  uv run --directory /absolute/path/to/timesync-mcp timesync-mcp serve
claude mcp list
```

Claude project MCP 可能需要在客户端批准。批准属于客户端信任流程；本项目不自动写批准设置。[官方说明](https://code.claude.com/docs/en/mcp)。JSON 见 [Claude 配置](../examples/claude/.mcp.json)。

OpenCode 把 [配置样例](../examples/opencode/opencode.json) 合并到项目 `opencode.json`，然后 `opencode mcp list`；`timeout` 的单位是毫秒。不要把 Codex 的 TOML 直接复制给它。[官方配置](https://opencode.ai/docs/mcp-servers/)

SDK v2 的 Server 同时服务现代与 legacy 协议；本项目测试两条 stdio 路径。特定客户端支持的协议以其实际版本为准，见 [验证记录](validation.md)。

`scripts/verify_clients.py` 是开发者辅助验证，会在缺少 `timesync` 时实际添加 Codex 配置；Claude/OpenCode 使用临时项目。它不调用 LLM，不消耗推理额度。
