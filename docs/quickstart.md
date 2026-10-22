# 运行第一次只读诊断

完成后你将获得一次本机环境检查，并通过真正的 MCP stdio 连接分析一组 Synthetic 400 Hz 时间戳。无需 ROS、PTP Grandmaster 或传感器；系统诊断不会改时钟或服务配置。

前提：Linux、Git、uv，以及可用的 Python 3.12。项目也支持核心 Python 3.11。

## 1. 安装项目

```bash
git clone https://github.com/tiansongyu/TimeSync-MCP.git timesync-mcp
cd timesync-mcp
uv sync --locked
```

预期：uv 创建 `.venv` 并安装 `timesync-mcp`，不会将 rclpy 装入核心环境。

## 2. 检查可用证据

```bash
env -u PYTHONPATH uv run timesync-mcp doctor
```

预期：输出 JSON，其中包含 Python/依赖、接口与时间戳能力、系统工具和 ROS Bridge 状态。缺少 pmc/chronyc/Bridge 时，对应项明确 unavailable，不会使其他检查失效。

## 3. 调用实际 MCP 工具

```bash
env -u PYTHONPATH uv run python examples/call_tool.py get_diagnostic_capabilities
```

该客户端启动 Server 子进程、协商协议并调用工具；不调用任何 LLM 或云端 API。预期结构包含 `status`、`source.collector="capabilities"` 和 `data.read_only=true`。

## 4. 分析 Synthetic 时间戳

```bash
env -u PYTHONPATH uv run python examples/call_tool.py analyze_timestamp_series \
  '{"timestamps_ns":[0,2500000,5000000],"expected_rate_hz":400,"synthetic":true}'
```

预期：sample_count=3、observed_span_rate_hz=400、interval mean=2500000 ns，同时有小样本警告。此例的原点是 Synthetic，相机曝光或 IMU 真实采样均没有被测量。

## 5. 恢复已知合成漂移

```bash
env -u PYTHONPATH uv run python examples/synthetic_drift.py
```

预期：明确标注 `synthetic=true`，估计接近注入的 20 ppm 和 5 ms，hardware_verified=false、uncertainty_ns=null。数值偏差范围由测试定义，不是机器人实机精度承诺。

需要 AI 客户端时，继续阅读[安装指南](installation.md)；理解不同时间轴时阅读[时钟域说明](clock-domains.md)。
