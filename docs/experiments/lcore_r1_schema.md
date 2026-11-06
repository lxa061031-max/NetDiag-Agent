# LCORE-D V2 R1 字段核实

来源：[Mendeley Data](https://data.mendeley.com/datasets/77sztrg5ks/2)；SHA-256：`e2382475949174506bff1bdb28b80b67f5208896fdaa0b43e9e64000d06f3b33`。
实际规模：24240行、42列、39个原生数值dtype字段。
原生数值类型不等于连续网络指标，状态编码、时间和标签不进入IQR。原始数据未改名、未改标签、未替换-1。

| 字段名 | dtype | 非空数 | 单个示例 | 类别 | 进入分析 | 说明 |
|---|---|---:|---|---|---|---|
| `timestamp` | int64 | 24240 | 1760264160 | 时间 | 否 | 原始数值保留；单位与时区未确认 |
| `ICMP loss` | float64 | 24240 | 0.0 | 数值 | 是 | ICMP监控或接口收发量候选指标；单位/采样口径未确认，原值统计及IQR |
| `ICMP ping` | object | 24240 | 0 | 暂不支持 | 否 | 混合类型，含1个`1异常字符串；不静默转换 |
| `ICMP response time` | float64 | 24240 | 0.0288 | 数值 | 是 | ICMP监控或接口收发量候选指标；单位/采样口径未确认，原值统计及IQR |
| `U_ Bits_ received` | int64 | 24240 | -1 | 数值 | 是 | ICMP监控或接口收发量候选指标；单位/采样口径未确认，原值统计及IQR |
| `U_ Bits_ sent` | int64 | 24240 | -1 | 数值 | 是 | ICMP监控或接口收发量候选指标；单位/采样口径未确认，原值统计及IQR |
| `U_ Duplex_ status` | int64 | 24240 | 2 | 类别/状态候选 | 否 | 按字段名识别；编码字典未确认 |
| `U_Inbound_ packets_ discarded` | int64 | 24240 | 0 | 数值 | 否 | 保留原量纲；未选字段留待语义核实 |
| `U_ Inbound_ packets_ with _errors` | int64 | 24240 | 0 | 数值 | 否 | 保留原量纲；未选字段留待语义核实 |
| `U_Interface_ type` | int64 | 24240 | 6 | 类别/状态候选 | 否 | 按字段名识别；编码字典未确认 |
| `U_ Operational_ status` | float64 | 24236 | 1.0 | 类别/状态候选 | 否 | 按字段名识别；编码字典未确认 |
| `U_Outbound_ packets_ with_ errors` | int64 | 24240 | 0 | 数值 | 否 | 保留原量纲；未选字段留待语义核实 |
| `U_Outbound_ packets_ discarded` | int64 | 24240 | 0 | 数值 | 否 | 保留原量纲；未选字段留待语义核实 |
| `U_ Speed` | int64 | 24240 | 10000000 | 数值 | 否 | 保留原量纲；未选字段留待语义核实 |
| `B1_Bits_ received` | int64 | 24240 | -1 | 数值 | 是 | ICMP监控或接口收发量候选指标；单位/采样口径未确认，原值统计及IQR |
| `B1_Bits_ sent` | int64 | 24240 | -1 | 数值 | 是 | ICMP监控或接口收发量候选指标；单位/采样口径未确认，原值统计及IQR |
| `B1_ Duplex _status` | int64 | 24240 | 2 | 类别/状态候选 | 否 | 按字段名识别；编码字典未确认 |
| `B1_ Inbound_ packets_ discarded` | int64 | 24240 | 0 | 数值 | 否 | 保留原量纲；未选字段留待语义核实 |
| `B1_Inbound_ packets_ with_ errors` | int64 | 24240 | 0 | 数值 | 否 | 保留原量纲；未选字段留待语义核实 |
| `B1_ Interface_ type` | int64 | 24240 | 6 | 类别/状态候选 | 否 | 按字段名识别；编码字典未确认 |
| `B1_Operational_ status` | float64 | 24236 | 1.0 | 类别/状态候选 | 否 | 按字段名识别；编码字典未确认 |
| `B1_Outbound_ packets_ with_ errors` | int64 | 24240 | 0 | 数值 | 否 | 保留原量纲；未选字段留待语义核实 |
| `B1_ Outbound_ packets_ discarded` | int64 | 24240 | 0 | 数值 | 否 | 保留原量纲；未选字段留待语义核实 |
| `B1_Speed` | int64 | 24240 | 10000000 | 数值 | 否 | 保留原量纲；未选字段留待语义核实 |
| `P1_ Bits_ received` | int64 | 24240 | -1 | 数值 | 是 | ICMP监控或接口收发量候选指标；单位/采样口径未确认，原值统计及IQR |
| `P1_Bits _sent` | int64 | 24240 | -1 | 数值 | 是 | ICMP监控或接口收发量候选指标；单位/采样口径未确认，原值统计及IQR |
| `P1_ Duplex_ status` | int64 | 24240 | 3 | 类别/状态候选 | 否 | 按字段名识别；编码字典未确认 |
| `P1_ Inbound_ packets_ discarded` | int64 | 24240 | 0 | 数值 | 否 | 保留原量纲；未选字段留待语义核实 |
| `P1_Inbound _packets_ with_ errors` | int64 | 24240 | 0 | 数值 | 否 | 保留原量纲；未选字段留待语义核实 |
| `P1_ Interface_ type` | int64 | 24240 | 6 | 类别/状态候选 | 否 | 按字段名识别；编码字典未确认 |
| `P1_Operational _status` | float64 | 24235 | 1.0 | 类别/状态候选 | 否 | 按字段名识别；编码字典未确认 |
| `P1_ Outbound_ packets_ discarded` | int64 | 24240 | 0 | 数值 | 否 | 保留原量纲；未选字段留待语义核实 |
| `P1_ Outbound _packets_ with_ errors` | int64 | 24240 | 0 | 数值 | 否 | 保留原量纲；未选字段留待语义核实 |
| `P1_Speed` | int64 | 24240 | 100000000 | 数值 | 否 | 保留原量纲；未选字段留待语义核实 |
| `SNMP agent availability` | int64 | 24240 | 1 | 类别/状态候选 | 否 | 按字段名识别；编码字典未确认 |
| `Uptime (network)` | int64 | 24240 | 121 | 数值 | 否 | 保留原量纲；未选字段留待语义核实 |
| `class` | object | 24240 | H | 标签 | 否 | H/F语义未确认，不用作真值 |
| `Device_name` | object | 24240 | CORE-R1 | 类别/状态候选 | 否 | 按字段名识别；编码字典未确认 |
| `Hop_to_server` | int64 | 24240 | 2 | 数值 | 否 | 保留原量纲；未选字段留待语义核实 |
| `Hop_to_core` | int64 | 24240 | 0 | 数值 | 否 | 保留原量纲；未选字段留待语义核实 |
| `downstream_dependents` | int64 | 24240 | 12 | 数值 | 否 | 保留原量纲；未选字段留待语义核实 |
| `path_up` | int64 | 24240 | 1 | 类别/状态候选 | 否 | 按字段名识别；编码字典未确认 |

分析选择依据：优先两个ICMP字段与U、B1、P1三个接口的收发字段，共8个；字段名提示监测意义，但不把前缀解释为已确认拓扑，不推断速率/累计口径或进行单位换算。

标签核实：官方说明确认数据包含healthy/faulty行为，但未明确class字母对应；根目录7个CSV，无README，custom_metadata和related_links为空。Fault Log附录包含故障事件、起止时间、类型、注入域，没有H/F编码定义。公开检索未找到可明确映射的作者论文说明。因此标签语义尚未由官方说明确认。
