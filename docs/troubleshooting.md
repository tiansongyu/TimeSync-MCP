# 故障排查

| 现象 | 证据含义与处理 |
| --- | --- |
| pmc/chronyc executable not found | 可选系统工具未安装；其他诊断仍有效。由用户按平台既有流程安装，本项目不提权。 |
| PTP daemon unreachable / no usable dataset | socket、权限、daemon、domain、管理 ID 均可能导致。先核对配置，不自动启动 ptp4l。 |
| MANAGEMENT_ERROR_STATUS | 守护进程返回管理错误；pmc 未提供明确码时不能断言“不支持”。 |
| PTP partial | 部分 dataset 可用；保留可用字段，不为未响应项补零。 |
| ethtool 无 PHC | 能力报告缺失 PHC；不直接断言硬件损坏或时钟未同步。 |
| systemctl unavailable | 容器或非 systemd 环境常见；不影响统计和其他 collector。 |
| journal 为空 | 没有匹配数据或用户可见性受限；不是“从未发生异常”的证明。 |
| Bridge unavailable | 确认发行版 Python、source ROS、socket 路径和 UID；核心不要导入 Humble rclpy。 |
| Bridge permission denied | socket 父目录必须当前用户所有且 0700，socket 0600；不建议放宽为全局可读。 |
| Socket path exists | 确认旧 Bridge 已停止再人工处理 stale socket，工具不会覆盖。 |
| Topic 存在但没有样本 | 检查 Publisher、消息包、DDS domain、安全策略与 QoS。无样本不证明物理设备未采样。 |
| Header analysis 为 null | 消息缺 Header、Header 无效或没有收到消息，不能执行采样时间分析。 |
| Cannot establish trusted mapping | 配置并验证 Header 来源/时间域或测量变换；不要靠时间戳近似绕过检查。 |
| truncated=true | 提高 max_samples（不超过 100000）或缩短窗口；注意 IPC 总响应仍限 8 MB。 |
| pytest 导入 ROS 插件报错 | 核心使用 `env -u PYTHONPATH uv run pytest`。不要把 ROS Python 3.10 插件装进 3.12 venv。 |
| Claude Pending approval | 在 Claude 客户端批准项目 MCP；这不是 TimeSync 协议错误。 |
| 客户端找不到 uv | 使用客户端能访问的 uv 绝对路径；先用同一 launcher 执行 doctor。 |

诊断快照只包含实际可获取数据。UNKNOWN、unavailable、unsupported 和 suspected 不能改写为已确认的硬件故障。
