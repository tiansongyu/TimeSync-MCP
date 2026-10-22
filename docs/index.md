# TimeSync MCP 文档

按你要完成的工作选择入口。入门教程、操作指南、接口参考和概念解释保持各自重点，不需要从头阅读全部文档。

## 入门教程

- [运行第一次只读诊断](quickstart.md)：无需 PTP 或 ROS 硬件，完成 doctor、实际 MCP 调用和 Synthetic 周期分析。

## 操作指南

- [安装与客户端配置](installation.md)
- [运行 ROS 2 Bridge 与 DDS 集成测试](ros2-integration.md)
- [故障排查](troubleshooting.md)
- [人工硬件验收](hardware-acceptance.md)
- [发布准备](releasing.md)

## 接口与验证参考

- [MCP Tools、Prompts、Resources](mcp-tools.md) · [实际 JSON Schema](mcp-tools.schema.json)
- [配置项](configuration.md)
- [软件与硬件验证记录](validation.md)
- [官方资料与版本依据](research.md)

## 概念与架构解释

- [现有软件架构](architecture.md)
- [Clock Domain 与可信变换](clock-domains.md)
- [PTP/NTP、Header、FSYNC/DRDY、EtherCAT DC 与不确定度](time-sync-theory.md)
- [安全边界](security.md)

贡献者请阅读 [CONTRIBUTING](../CONTRIBUTING.md)、[社区行为规范](../CODE_OF_CONDUCT.md)、[SECURITY](../SECURITY.md) 和 [CHANGELOG](../CHANGELOG.md)。
