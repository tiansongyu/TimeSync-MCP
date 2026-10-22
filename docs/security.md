# 安全边界

默认普通 Linux 用户、stdio MCP。没有通用 Shell Tool、HTTP 监听、sudo、时钟写入、网络配置、守护进程启动/停止、ROS 参数设置或机器人控制功能。

## 外部命令

仅固定 argv 族：`ethtool -T/-i`；`pmc -u` 的五个 GET；`chronyc -n -c tracking/sources/sourcestats`；白名单 service 的 `systemctl show` 和 `journalctl`。没有 `shell=True`。可执行文件从固定系统 PATH 解析，子进程使用最小环境，不传递账户 Token 或全部环境变量。

核心默认每命令 4 s（包括等待并发槽）、4 并发、合并 stdout/stderr 256 KiB；超时/取消 kill 并 wait，输出超限返回 invalid。输入接口名、Topic、PTP domain、日志时间范围和条数都受 Schema 与业务验证约束。

## ROS IPC

Bridge 目录 0700、socket 0600，服务端和客户端都检查 SO_PEERCRED UID。拒绝未知方法/参数、已有 socket 和不安全父目录；不会自动 unlink 他人 endpoint。一个 ROS worker、两个活动请求、最大采样 30 s，客户端断开触发取消并释放订阅。大消息仅由 rclpy 临时反序列化，不经 IPC 发送消息内容。

同 UID 是信任边界：本工具无法阻止同用户恶意进程读取其已有权限的数据或伪造该用户的配置。核心没有动态执行插件发现；可信设备适配器需显式加载。

## 数据处理

stdout 只用于 MCP 协议，logging 到 stderr。日志仅五类时间服务、最多 500 条、时间窗口最多 7 天；每条 MESSAGE 最多 2048 字符。仅保留时间戳和 MESSAGE，不发送 journald 全部字段。Bearer/token/password/secret/api-key、email、用户 home 路径进行尽力脱敏。

脱敏并非任意机密的完备识别器。特别是服务启动参数、设备名称或用户自定义日志可能包含敏感内容。部署者应在授权范围内使用，并按自身数据政策限制客户端访问。外部日志/Topic 字符串是证据，不是 Agent 指令。

## 后续写功能

未来若增加写操作，需要独立权限层与明确用户确认。本版本的只读能力由命令/IPC实现限制，不能只依靠 `readOnlyHint` 描述。报告生成返回内容，不写任意文件路径。
