# 验证记录

记录时间：2026-10-22。下列“通过”均指当前环境实际运行结果；配置了 CI 不等于 CI 已经通过。此页不包含实体传感器或 PTP 精度验收结果。

## 当前环境

Ubuntu 22.04.5 LTS、Linux 6.8、x86_64。核心 Python 3.12.13；兼容环境 Python 3.11.15；ROS 2 Humble rclpy 3.3.21 使用独立系统 Python 3.10.12。官方 MCP SDK 2.3.0、Pydantic 2.14.1、Typer 0.27.3；完整依赖见 uv.lock。

| 验证 | 实际结果 |
| --- | --- |
| Python 3.12 完整 pytest | 39 passed，含 3 项真实 ROS/DDS 集成；核心覆盖率 86%（子进程 CLI 不计入该覆盖率） |
| Python 3.11 非 ROS pytest | 36 passed，3 deselected；独立临时环境 |
| Ruff check / format | src、tests、ros_bridge、scripts、examples 通过 |
| mypy strict 核心 | 34 个源文件通过 |
| mypy Bridge / Python 3.10 target | 3 个源文件通过 |
| 核心与 Bridge build | 两套 sdist/wheel 可构建；核心 wheel 在干净 3.12 环境安装运行 doctor；Bridge wheel 用 3.10 安装并验证 CLI |
| 本机网络接口 | 实际 list_network_interfaces 成功，包含 loopback 和其他可访问接口；不公开本机 MAC 清单 |
| pmc / chronyc 缺失 | 实际返回 unavailable；本环境未安装，不伪造 live PTP/Chrony 数据 |
| MCP official SDK stdio | modern（2026-07-28）和 legacy 路径均通过；15 工具、4 Prompts、Resource、输入错误和输出 Schema 验证 |
| 并发/取消/安全 | 命令并发上限、deadline、输出超限、取消清理；Bridge 同 UID/权限/工作量/断开取消通过 |

## 数据来源分类

- **Synthetic 格式 Fixture**：Chrony 4.2/4.5 CSV、LinuxPTP 响应/错误、ethtool 硬件/软件能力；格式来自官方文档与源码，值为注入测试数据。
- **Synthetic 数值实验**：400 Hz、20 ppm、5 ms、固定 seed jitter 和 outlier。恢复误差验收：drift <0.005 ppm、首源锚点 offset <10 ns。结果不代表硬件计量不确定度。
- **真实 ROS DDS、Synthetic 消息**：独立系统 Python Publisher 与 Bridge，30 Hz 双相机 Header、400 Hz IMU、50 ppm、5 ms、反复时间戳跳变、无 Header、模拟时间、样本截断和不兼容 QoS 的实际订阅实验。
- **真实本机只读观测**：sysfs/ethtool、doctor、MCP 子进程可用性。未启动/停止任何时间服务或改时钟。

## 客户端验证

| 客户端 | 版本 | 实际验证范围 |
| --- | --- | --- |
| Codex CLI | 0.163.0 | 实际执行 add/get 并核对 timesync stdio launcher；官方 SDK Client 验证协议调用；未调用 Codex LLM 做端到端推理 |
| Claude Code | 2.1.308 | 临时项目实际 add 成功、JSON 配置一致；list 显示 Pending approval；连接未验证，须用户在客户端批准 |
| OpenCode | 1.2.27 | 临时项目 local command array 配置，实际 mcp list 显示 connected；未调用 LLM |

客户端检查不声称所有版本都支持相同协议。脚本 `scripts/verify_clients.py` 不绕过 Claude 的项目批准，也不调用云端推理。

## 尚未验证

- Ubuntu 24.04 / ROS Jazzy：已配置单独 GitHub Actions job，本机没有该发行版执行结果。
- ARM64 / NVIDIA Jetson、真实 PHC/Grandmaster、跨主机计量、双目曝光、IMU 物理采样、LiDAR 每点时间、EtherCAT DC：全部 hardware-unverified。
- GMSL、Jetson HTE、SOEM/IgH、rosbag2、历史/多机插件：尚未实现。

远端 CI 的实际运行状态以 [Actions](https://github.com/tiansongyu/TimeSync-MCP/actions) 为准；人工实机记录使用 [验收表](hardware-acceptance.md)，不要用软件测试代填。
