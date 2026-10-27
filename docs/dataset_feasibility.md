# LCORE-D 数据集可行性调查

调查日期：2026-10-26  
目标版本：LCORE-D v2  
页面：https://data.mendeley.com/datasets/77sztrg5ks/2  
DOI：https://doi.org/10.17632/77sztrg5ks.2

## 已验证信息

- **可访问性**：Mendeley Data 的 v2 页面可访问，公开页面及匿名文件清单接口均能返回结果；调查期间无需登录即可读取元数据和 R1 文件。
- **数据来源**：页面说明该数据来自用 GNS3 搭建的大规模仿真 ISP 网络，是受控、带故障标注的网络监控数据；它不是校园真实生产网数据。
- **时间规模**：发布页明确说明总计 407 小时监控数据。
- **文件格式与体量**：v2 根目录列出 7 个 CSV 文件（`LCORE-D R1.csv` 至 `LCORE-D R7.csv`），文件大小依次为 3,910,061、2,931,887、4,416,768、3,752,804、3,615,230、4,125,834、3,918,009 字节，合计 26,670,593 字节（约 25.44 MiB）。接口报告 MIME 类型均为 `text/csv`。
- **R1 实际结构**：实际读取 `LCORE-D R1.csv`，得到 24,240 行、42 列。字段为：

  `timestamp`, `ICMP loss`, `ICMP ping`, `ICMP response time`, `U_ Bits_ received`, `U_ Bits_ sent`, `U_ Duplex_ status`, `U_Inbound_ packets_ discarded`, `U_ Inbound_ packets_ with _errors`, `U_Interface_ type`, `U_ Operational_ status`, `U_Outbound_ packets_ with_ errors`, `U_Outbound_ packets_ discarded`, `U_ Speed`, `B1_Bits_ received`, `B1_Bits_ sent`, `B1_ Duplex _status`, `B1_ Inbound_ packets_ discarded`, `B1_Inbound_ packets_ with_ errors`, `B1_ Interface_ type`, `B1_Operational_ status`, `B1_Outbound_ packets_ with_ errors`, `B1_ Outbound_ packets_ discarded`, `B1_Speed`, `P1_ Bits_ received`, `P1_Bits _sent`, `P1_ Duplex_ status`, `P1_ Inbound_ packets_ discarded`, `P1_Inbound _packets_ with_ errors`, `P1_ Interface_ type`, `P1_Operational _status`, `P1_ Outbound_ packets_ discarded`, `P1_ Outbound _packets_ with_ errors`, `P1_Speed`, `SNMP agent availability`, `Uptime (network)`, `class`, `Device_name`, `Hop_to_server`, `Hop_to_core`, `downstream_dependents`, `path_up`。
- **标签字段**：发布页说明数据包含健康状态、人工注入硬故障和自然出现的瞬态故障；故障包括单/多链路故障、节点故障、路由错误配置和线卡故障。R1 的 `class` 字段实际含 `H`（23,811 行）和 `F`（429 行），但字母对应含义尚未由官方说明明确确认，不能仅凭名称当作健康/故障真值。
- **许可**：页面标注 Creative Commons Attribution 4.0 International（CC BY 4.0）；允许在署名、附许可链接并注明修改的条件下共享和改编。
- **版本信息**：v2 发布于 2025-12-17，DOI 为 `10.17632/77sztrg5ks.2`。

## 未确认信息

- **第5D阶段复核补充（2026-10-28）**：已重新下载R1并核验官方SHA-256，读取官方FAULT_LOG.csv用于检查标签定义；未分析R2–R7。根目录7个CSV外还有Fault Log目录及其附录CSV。H/F对应含义仍未找到官方明确映射，不得将本文件早期的健康/故障分类讨论视为已确认编码。详见 `docs/experiments/experiment_5_lcore_validation.md`。

- 因文件接口在批量读取其余文件时响应不稳定，本次没有完整下载 R2–R7，也没有验证它们是否全部与 R1 使用完全相同的 42 列结构。
- 尚未确认 R2–R7 的准确行数、各类标签分布，以及 7 个文件合并后的总行数。
- 公开页面没有提供字段数据字典；`U`、`B1`、`P1` 等接口前缀的准确拓扑语义、单位和缺失值编码规则尚未确认。
- 已确认 `class` 有 H/F 二分类，但尚未发现可直接区分链路故障、节点故障、路由错误配置、线卡故障和瞬态故障的细粒度故障类型字段或独立事件表。
- `timestamp` 的单位、时区和采样间隔尚未由官方文档确认。

## 适用性判断

- **异常检测：较适合。** 数据有时间戳、ICMP/SNMP 指标以及健康/故障标签，可用于监督二分类、时间序列异常检测和误报分析。H/F 明显不均衡，评价时不应只报告准确率，应关注精确率、召回率、F1、PR-AUC，并按时间或设备划分训练/测试集以减少泄漏。
- **故障诊断：有条件适合。** 发布说明覆盖多种故障，指标还包含设备名、拓扑跳数、下游依赖和路径状态，具备根因定位潜力；但当前仅验证到 H/F 标签。若没有细粒度故障类型、注入时间与受影响设备的对应关系，数据更适合“检测是否故障”，不足以单独训练多类别根因诊断模型。
- **校园网络迁移：只能作为基准或预训练数据。** 数据来自 GNS3 仿真 ISP 网络，与校园网的设备类型、流量结构和运维流程存在域差异，不能直接宣称模型在真实校园网络有效。

## 后续建议

1. 经人工确认许可署名方式后，将 v2 原始文件下载到 `data/raw/`；仓库默认忽略该目录中的大文件。
2. 对 7 个文件计算 SHA-256，并与公开接口给出的哈希核对，记录下载日期、版本和 DOI。
3. 编写一次性数据审计脚本，逐文件输出行数、字段、类型、缺失率、重复率、时间范围和 H/F 分布，确认是否可安全合并。
4. 查找作者论文、README 或数据字典，重点确认接口前缀、单位、时间戳、故障事件边界和细粒度根因标签。
5. 后续实验采用设备/时间分组切分，建立简单统计基线，并将 LCORE-D 结果明确描述为仿真 ISP 场景结果。
6. 在取得脱敏且授权的校园网络样本后，再评估域适配和真实场景效果；不得把本项目模拟数据或 LCORE-D 描述成真实校园网络数据。

## 第二阶段 R1 最小验证

本节只验证 `LCORE-D R1.csv`，没有扩展到其余 6 个文件。

- 再次读取结果为 24,240 行、42 列；`class` 标签为 `H=23,811`、`F=429`。
- 网络指标统计工具识别出 39 个原生数值列，包括 `timestamp`、`ICMP loss`、`ICMP response time`、接口收发量与状态、`SNMP agent availability`、`Uptime (network)`、拓扑跳数和 `path_up` 等。
- `ICMP ping` 被 Pandas 识别为混合类型，不在上述 39 列中。该列有 24,239 个可转换为数值的值和 1 个异常字符串 `` `1 ``，后续清洗时必须显式记录转换规则，不能直接静默丢弃。
- 使用统计工具得到的代表性结果：`ICMP loss` 的 count=24,240、mean=9.4259、min=-1、max=100、median=0、p95=100；`ICMP response time` 的 count=24,240、mean=0.0351、min=-1、max=0.996、median=0.0268、p95=0.0496；`SNMP agent availability` 的 mean=0.9975、min=0、max=1。
- `-1` 很可能是缺失、不可达或采集失败的特殊编码，但尚无官方字段字典确认，因此当前统计保留原值，不把它擅自改成缺失值。
- 当前异常检测器只配置 `latency_ms`、`packet_loss_pct`、`cpu_usage_pct` 和 `temperature_c`。R1 没有这些同名字段，实际运行结果为 0 个已分析指标和 0 个异常；系统没有强行套用阈值。
- 后续字段适配器至少需要定义：原字段到统一指标名的映射、单位换算、特殊缺失编码、合法值范围、设备/接口层级，以及每项阈值的来源。确认这些语义后，才能为 `ICMP loss`、`ICMP response time` 等字段建立独立规则。
