# 配置参考

使用 TOML，通过 `timesync-mcp serve --config PATH` 或 `doctor --config PATH` 显式加载。未知键、非法字段和无效时间域引用会被 Pydantic 拒绝。配置不修改系统或机器人参数。

| 配置项 | 默认值 | 约束/含义 |
| --- | --- | --- |
| bridge_socket | /tmp/timesync-mcp-&lt;uid&gt;/bridge.sock | 与 Bridge --socket 一致；父目录与 socket 必须私有且同 UID |
| command_timeout_s | 4.0 | >0，≤15 s；包括等待并发槽 |
| command_output_bytes | 262144 | 1024–1048576；stdout+stderr 总预算 |
| max_commands | 4 | 1–8；外部命令并发 |
| max_samples | 20000 | 2–100000；每 Topic 保留时间戳上限；仍受 8 MB IPC 限制 |
| ptp_socket | /var/run/ptp4l | GET 查询的 daemon UDS；不代表接口归属已核实 |
| ptp_offset_warning_ns | 100000 | >0；工程默认阈值，并非统一标准 |
| chrony_offset_warning_ns | 1000000 | >0；Chrony System time 阈值 |
| graph.domains | [] | 最多 128 个唯一域；字段见 clock-domains.md |
| graph.transformations | [] | 最多 256 条；显式方向、证据、有效范围、不确定度 |
| topic_clock_domains | {} | 完整合法 Topic 名→已声明 domain id；不是从节点自动推断 |

完整可编辑示例：[robot_config.toml](../examples/robot_config.toml)。示例共享相机域仅为操作员声明，使用前必须核对真实驱动时间戳来源。[映射语义与限制](clock-domains.md)

CLI：`serve`、`doctor`，两者仅接受可选 `--config`。Bridge 独立 CLI 只有 `--socket`，其 ROS_DOMAIN_ID/RMW 等由发行版环境继承。
