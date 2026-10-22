# 人工实机验收（当前未执行）

此清单只读检查既有系统，不指示更改系统时间、PTP/Chrony、EtherCAT、ROS 参数或机器人运动配置。任何配置修改都应另走设备既有审批流程。

## 记录前提

记录硬件型号、Ubuntu/内核、架构、JetPack/ROS/驱动版本、网卡、PHC、现有 PTP domain/拓扑与服务参数。明确每个 Header 的事件含义、时钟源和时间尺度。先确认实验可以安全增加被动订阅负载。

## Ubuntu x86 / PHC / Grandmaster

1. 运行 doctor，保存本地原始 JSON，确认预期接口及驱动。
2. 查询 timestamp capabilities，核对厂商支持的硬件 TX/RX 与 PHC index。
3. 使用 get_ptp_status 查询既有 socket/domain；人工将 responding portIdentity 与接口关联。
4. 核对 Grandmaster identity、gmPresent、Port State、CURRENT/TIME_STATUS 偏移符号。
5. 在多次独立观测中比较偏移与既定工程阈值；单次好结果不等于长期精度。
6. 读取已有服务状态与有限日志，确认 PHC→系统映射证据。Chrony 的本地源不能直接算外部 UTC。

## Jetson / 双目 / IMU

1. 启动发行版匹配 Bridge，确认 DDS domain 与现有机器人一致。
2. 检查 Topic 消息定义、QoS、Publisher 参数和时间戳来源。
3. 分别采样相机与 IMU，报告 count、窗口、缓存截断、Header 和 callback 两种间隔。
4. 在可信共同域下比较双目 Header，明确配对策略与未匹配比例；100 µs Header 目标仅对已配对观测成立，未匹配帧不能忽略。
5. 曝光/采样精度需独立逻辑分析仪、示波器、共同事件或可信硬件计时证据；本软件结果不能替代它们。
6. 对 IMU DRDY/FSYNC、FIFO 和滤波延迟逐项注明已知值及文档来源；未知值保持未知。

## 验收表

| 项目 | 目标/允许误差 | 实测记录 | 状态 |
| --- | --- | --- | --- |
| x86 Linux collector | 数据与系统只读工具一致 | 未执行 | UNVERIFIED |
| Jetson ARM64 安装 | core/bridge 可启动 | 未执行 | UNVERIFIED |
| PHC/PTP/GM 状态 | 身份、域、偏移可追溯 | 未执行 | UNVERIFIED |
| 双目曝光差 | 由用户设备规范定义 | 未执行 | UNVERIFIED |
| IMU 真实采样误差 | 由用户设备规范定义 | 未执行 | UNVERIFIED |
| UTC/PHC/ROS 映射 | 测量方法和不确定度完整 | 未执行 | UNVERIFIED |

合成 20 ppm/5 ms、实际 DDS Publisher 的零 Header 差等测试只能填入软件验证记录，不能填写此实机表。
