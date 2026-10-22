# 接口依据与版本核对

2026-10-22 开发时读取官方文档、已安装包接口与官方源码。以下不是对未来版本的兼容承诺。依赖实际解析版本锁定在 uv.lock。

| 组件 | 已核对内容 | 官方来源 |
| --- | --- | --- |
| MCP Python SDK 2.3.0 | MCPServer/Client、结构化工具、stdio、modern/legacy；requires-python >=3.10 | [文档](https://py.sdk.modelcontextprotocol.io/)、[v2.3.0 源码](https://github.com/modelcontextprotocol/python-sdk/tree/v2.3.0) |
| Chrony 4.2/4.5 | tracking 14 列；sources 10；sourcestats 8；CSV 单位与 System time 符号 | [4.2 手册](https://chrony-project.org/doc/4.2/chronyc.html)、[4.5 client.c](https://github.com/mlichvar/chrony/blob/4.5/client.c)、[4.2 client.c](https://github.com/mlichvar/chrony/blob/4.2/client.c) |
| LinuxPTP | pmc -u/-b/-d/-s/-i；五种 GET、响应/错误文本；offset local-minus-master | [pmc 手册](https://linuxptp.nwtime.org/documentation/pmc/)、[pmc.c](https://github.com/richardcochran/linuxptp/blob/master/pmc.c)、[tsproc.c](https://github.com/richardcochran/linuxptp/blob/master/tsproc.c) |
| Linux PHC/HTE | 独立 PHC 与事件功能；HTE 是独立内核接口，当前无采集器 | [PHC](https://docs.kernel.org/driver-api/ptp.html)、[HTE](https://docs.kernel.org/driver-api/hte/index.html) |
| ROS 2 Humble/Jazzy | Topic endpoint、消息类型、QoS、GetParameters、ROS Time | [Humble Node](https://github.com/ros2/rclpy/blob/humble/rclpy/rclpy/node.py)、[Jazzy Node](https://github.com/ros2/rclpy/blob/jazzy/rclpy/rclpy/node.py)、[QoS](https://github.com/ros2/rclpy/blob/humble/rclpy/rclpy/qos.py)、[时间设计](https://design.ros2.org/articles/clock_and_time.html) |
| 标准 Header | stamp/frame_id，无 seq | [Header.msg](https://github.com/ros2/common_interfaces/blob/humble/std_msgs/msg/Header.msg) |
| Codex | 实际 CLI add/get 与 stdio 配置 | [OpenAI 文档](https://learn.chatgpt.com/docs/extend/mcp) |
| Claude Code | project stdio add/list、项目批准流程 | [官方文档](https://code.claude.com/docs/en/mcp) |
| OpenCode | local command array 配置 | [官方文档](https://opencode.ai/docs/mcp-servers/) |

核心技术取舍：不用旧 FastMCP v1 导入；不在同一环境混装 Humble rclpy 与 MCP 运行依赖；不以 daemon 状态建立未测量的时钟变换；用 stdlib/Decimal 支持确定性统计，避免不必要的 NumPy 运行依赖。未创建额外逐组件 skill 或未经批准的 ADR。
