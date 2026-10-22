# 机器人时间同步中的观测含义

本页用于解释工具输出，不为具体设备承诺未测量的精度。设备专有结论需要型号、固件、驱动和厂商文档，以及必要的实验验证。

## PTP 与 NTP

PTP/IEEE 1588 通过网络时间戳和路径延迟估计同步时钟，可利用网卡硬件时间戳减少主机软件路径引入的误差。NTP/Chrony 以网络参考估计时间和频率；部署拓扑、参考品质、硬件时间戳与路径非对称决定实际性能，不能仅凭协议名称保证精度。

LinuxPTP `master_offset` / `offsetFromMaster` 为本地减 master，正值本地超前。pmc 的 CURRENT_DATA_SET 文本已输出 ns，不应再次除以 65536。TIME_STATUS_NP 是 LinuxPTP 扩展，未返回不能假设零偏差。

Chrony System time 原始 CSV 是 chronyd 虚拟 NTP clock 减 CLOCK_REALTIME，正值系统慢。Last offset 的正值则表示本地 NTP clock 相对来源超前。跟踪变量的符号不相同；每个 Measurement 标注约定。Normal/Insert second/Delete second 可能是同步状态，但 local reference 并不证明外部 UTC 可追溯。

依据：[LinuxPTP pmc](https://linuxptp.nwtime.org/documentation/pmc/)、[Chrony 4.5 tracking](https://chrony-project.org/doc/4.5/chronyc.html#tracking)。

## PHC、系统与 ROS 时间

Linux PHC 通过内核驱动导出独立硬件时钟；支持 PHC 不代表它已经同步，也不代表它与 CLOCK_REALTIME 有已测映射。PTP 时间尺度和 UTC 的偏移必须有实际来源证据，不能硬编码通用常数。

CLOCK_REALTIME 可被调整，monotonic 没有 Unix 原点。ROS Time 在 TimeSource 激活时由 `/clock` 驱动，可加速、暂停或倒退；尚未初始化时可为零。`header.stamp` 的语义由发布驱动决定，不是 DDS 自动提供的物理采样时间。

依据：[内核 PHC](https://docs.kernel.org/driver-api/ptp.html)、[ROS Clock and Time](https://design.ros2.org/articles/clock_and_time.html)。

## Clock Synchronization 与 Sample Synchronization

时钟同步是建立时间坐标之间的可信关系；采样同步是协调物理采样事件。两个 Header 同值，可能只是驱动使用同一粗分辨率时间戳，不能自动证明曝光或内部 ADC 采样同一时刻。

相机可区分 SOF、EOF、曝光开始/中点/结束、Frame Arrival、Driver Timestamp 和 ROS Header。USB UVC、MIPI CSI-2、GMSL、GigE 的传输方式不自动决定时间戳语义。FSYNC 可以协调触发，但 FSYNC 到曝光的延迟、rolling shutter 行时序与模式必须由设备资料或测量说明。

IMU 的 DRDY 通常表示数据准备好，不自动等于实际采样时刻。FSYNC/SYNC 的方向和事件含义依型号而异；FIFO、内部滤波 group delay、驱动缓存和 Host Receive Time 都可能引入未确定延迟。未知延迟应记录为未知，不能从 Host callback 周期扣出确定值。

LiDAR 的 Packet Receive Timestamp、Point Timestamp、Scan Header Timestamp 指向不同事件。不能把整帧时间戳赋给所有点后声称是每点实测采样时间。PTP/PPS 支持需核实具体设备。

EtherCAT Distributed Clocks 是独立同步机制；Reference Clock、SYNC0/SYNC1、应用时间映射需分别获得只读证据。SOEM/IgH 具有不同接口，本版本尚未接入。DC 与 PTP 或 ROS Time 之间的边必须另行测量。

## Offset、Drift、Jitter 与不确定度

Offset 是指定参考时刻和方向的时间差；Drift 是相对频率误差，ppm=(a−1)×10⁶；Jitter 需指明是哪类事件间隔的离散程度。Header interval、callback arrival interval、DDS delay、物理采样 jitter 是四类不同对象。

本项目标准差和方差使用总体定义；percentile 使用线性插值，MAD 是对中位数的绝对偏差中位数。少于 100 个间隔时 P95/P99 带小样本说明。异常大间隔阈值为 max(1.5×baseline, baseline+6×MAD)，是可解释的工程启发式，不是丢样计数或设备统一规范。

残差 RMS 不等于总测量不确定度，未知不确定度保持 null。整数 ns 表示坐标分辨率，不保证时钟读数或传感器时刻具有 1 ns 精度。跨时钟拟合采用中心化和 Decimal，避免直接将巨大 Unix ns 转成浮点。
