# ROS 2 Bridge 集成

Bridge 为独立 Python 3.10+ 包，不依赖 MCP/Pydantic。rclpy 必须由匹配的 ROS 发行版提供。Humble 通常是 Ubuntu 22.04/Python 3.10；Jazzy 通常是 Ubuntu 24.04/Python 3.12。当前本机实际验证 Humble，不能把这项结果扩展为 Jazzy 已验证。

## 启动

在 ROS 终端：

```bash
source /opt/ros/humble/setup.bash
/usr/bin/python3 ros_bridge/run.py
```

在核心终端：

```bash
env -u PYTHONPATH uv run timesync-mcp doctor
env -u PYTHONPATH uv run timesync-mcp serve
```

默认 UDS `/tmp/timesync-mcp-<uid>/bridge.sock`，目录仅所有者可访问。自定义 `--socket` 时必须同时修改核心 TOML 的 `bridge_socket`。Bridge 拒绝已有 endpoint，不会自动删除它；确认旧进程退出后由用户处理 stale socket。

不设置或改变已有机器人 DDS domain。Bridge 继承其 ROS 环境；只有集成测试的子进程显式使用独立 domain 87 和 localhost 模式，不写系统配置。

## Topic 与采样

`get_topic_names_and_types` / endpoint API 返回类型和 QoS，按已安装消息定义检查标准 Header；不凭 Topic 名推断设备类型。多类型 Topic 拒绝采样。未知消息包可被发现但无法反序列化时返回不可用。

订阅为 BEST_EFFORT/VOLATILE/KEEP_LAST depth 100，兼容常见传感器 QoS；逐 Publisher 执行 `qos_check_compatible`。这仍可能与特殊 durability/deadline/liveliness 等策略不兼容。无消息不能自动断言发布器故障。

一次请求最多两个 Topic，同时创建订阅并在同一窗口采集。每条保留 Header ns 和 `time.monotonic_ns()` callback 时间。消息本体、图像像素和环境变量不进入 IPC。样本上限后继续统计 callback 数，但不增加缓存；结果明确 `truncated`，所保留序列仅覆盖窗口前部。

观察频率 `received_count / observation_duration` 与 Header span rate `(n-1)/(last-first)` 不同。异常间隔表示观测异常或疑似缺样，没有硬件计数器时不声称具体物理丢样数。

标准 ROS 2 Header **没有 seq**。在线比较支持 exact/tolerance；`analysis.correlation.compare(...strategy='event_id')` 可供有经过验证共同事件编号的适配器使用，不能从 frame_id 构造通用事件编号。

## ROS Time

只读查询逐节点 `GetParameters(use_sim_time)`，Humble/Jazzy 共用此服务接口；不依赖 Humble 缺失的 AsyncParameterClient。服务未暴露、超时、节点过多等结果保留 null。Bridge 自身的参数不能代表发布者。

直接订阅 `/clock` 观察推进、重复、倒退和疑似暂停；无数据返回未知。暂停阈值 500 ms 是工程启发式，低频 `/clock` 可能表现类似暂停。Header-to-ROS-clock 的关系在来源未确认时保持 unknown；不计算 Header-to-UTC 延迟。

## 实际 DDS 合成测试

```bash
env -u PYTHONPATH uv run pytest -m ros -v
```

测试使用发行版系统 Python 启动 Publisher 和 Bridge，再由核心通过 UDS 采样。包含 Synthetic 30 Hz 双相机、400 Hz IMU、50 ppm 漂移、5 ms 偏移、跳变、无 Header 和 `use_sim_time`。没有匹配 ROS 时测试 skip；CI ROS job 要求实际 ROS 可用，缺失应失败。

原始 Publisher 可手动运行：

```bash
/usr/bin/python3 tests/integration/ros_publisher.py --sim-time --jump
```

用户必须在隔离 DDS 环境操作该测试 Publisher，避免将合成 Topic 当成机器人数据。此程序设置的是自身测试节点参数，不修改现有机器人节点。

IPC 方法白名单：ping、list_topics、sample、inspect_clock；无任意命令、发布消息、参数写入或运动控制接口。
